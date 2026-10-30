import hashlib
import itertools
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

from fixtures import wheel
import solver


VARIANTS=[("files",False,False,False),("cached",True,False,False),("catalog",True,False,False),
          ("catalog",True,True,False),("catalog",True,True,True),("catalog",True,True,False,"incremental"),("catalog",True,True,False,"trail")]


def target(version="3.14.8",platform="linux",tags=("py3-none-any",)):
    environment=solver.default_environment()
    environment.update(python_full_version=version,python_version=".".join(version.split(".")[:2]),
                       sys_platform=platform,platform_system="Windows" if platform=="win32" else "Linux")
    return {"environment":environment,"tags":list(tags)}


class SolverTests(unittest.TestCase):
    def make_session(self,admission,variant,**kwargs):
        backend,parsed,matching,heuristic,*engine=variant
        key="catalog" if backend=="catalog" else "inventory"
        source=solver.Source(**dict(path=admission["inputs"][key]["path"],pin=admission["inputs"][key]["sha256"],backend=backend))
        return solver.Session(source,kwargs.pop("target",target()),parsed_cache=parsed,match_cache=matching,heuristic=heuristic,
                              engine=engine[0] if engine else "baseline",**kwargs)

    def solve_all(self,admission,roots,**kwargs):
        results=[]
        for variant in VARIANTS:
            session=self.make_session(admission,variant,target=kwargs.get("target",target()),prereleases=kwargs.get("prereleases",False))
            result=session.solve(roots,kwargs.get("constraints",()))
            repeated=session.solve(roots,kwargs.get("constraints",()))
            self.assertEqual((result["status"],result["selected"]),(repeated["status"],repeated["selected"]))
            results.append(result)
        self.assertTrue(all((r["status"],r["selected"])==(results[0]["status"],results[0]["selected"]) for r in results))
        return results

    def test_backtracking_and_unsat_match_finite_oracle(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);wheels=root/"wheels"
            wheel(wheels,"alpha","2.0",["bravo>=2"])
            wheel(wheels,"alpha","1.0",["bravo<2"])
            wheel(wheels,"bravo","1.0");wheel(wheels,"bravo","2.0")
            wheel(wheels,"charlie","1.0",["bravo<2"])
            admission=solver.admit(wheels,root/"snapshot")
            for roots in (["alpha>=1","charlie==1"],["alpha>=2","charlie==1"]):
                session=self.make_session(admission,VARIANTS[2])
                names=sorted(session.source.projects)
                valid=[]
                for choices in itertools.product(*[[None]+list(session.source.projects[n]) for n in names]):
                    mapping={n:solver.Candidate(n,r["id"],frozenset()) for n,r in zip(names,choices) if r}
                    try:
                        solver.validate_solution(session,mapping,[solver.parse_requirement(r) for r in roots],{})
                    except ValueError:continue
                    valid.append({n:session.source.rows[c.artifact_id]["version"] for n,c in mapping.items()})
                results=self.solve_all(admission,roots)
                if valid:
                    self.assertEqual({r[0]:r[1] for r in results[0]["selected"]},valid[0])
                    self.assertGreater(results[0]["solver"].get("rejections",0),0)
                else:self.assertEqual(results[0]["status"],"unsatisfiable")

    def test_markers_extras_and_extra_expansion_cycle(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);wheels=root/"wheels"
            wheel(wheels,"project","1.0",["leaf<2; extra == 'fast'","project[other]==1; extra=='fast'",
                                             "other==1; extra=='other'","linux-only==1; sys_platform=='linux'"],extras=["fast","other"])
            wheel(wheels,"leaf","1.0");wheel(wheels,"leaf","2.0")
            wheel(wheels,"other","1.0");wheel(wheels,"linux-only","1.0")
            admission=solver.admit(wheels,root/"snapshot")
            result=self.solve_all(admission,["project[fast]==1"])[0]
            self.assertEqual({r[0]:r[1] for r in result["selected"]},
                             {"project":"1.0","leaf":"1.0","other":"1.0","linux-only":"1.0"})
            self.assertEqual(next(r[3] for r in result["selected"] if r[0]=="project"),["fast","other"])
            windows=self.solve_all(admission,["project[unknown]==1"],target=target(platform="win32"))[0]
            self.assertEqual([r[0] for r in windows["selected"]],["project"])

    def test_python_tags_constraints_and_prerelease_policy(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);wheels=root/"wheels"
            wheel(wheels,"library","1.0")
            wheel(wheels,"library","2.0",requires_python=">=3.14")
            wheel(wheels,"library","3.0rc1",requires_python=">=3.14")
            wheel(wheels,"library","9.0",tag="cp314-cp314-win_amd64")
            admission=solver.admit(wheels,root/"snapshot")
            self.assertEqual(self.solve_all(admission,["library>=1"])[0]["selected"][0][1],"2.0")
            self.assertEqual(self.solve_all(admission,["library>=1"],target=target(version="3.10.1"))[0]["selected"][0][1],"1.0")
            self.assertEqual(self.solve_all(admission,["library>=1"],constraints=["library<2"])[0]["selected"][0][1],"1.0")
            self.assertEqual(self.solve_all(admission,["library>=1"],prereleases=True)[0]["selected"][0][1],"3.0rc1")
            self.assertEqual(self.solve_all(admission,["library==3.0rc1"])[0]["selected"][0][1],"3.0rc1")
            self.assertEqual(self.solve_all(admission,["library>=1"],target=target(tags=("cp314-cp314-win_amd64","py3-none-any")))[0]["selected"][0][1],"9.0")

    def test_cache_does_not_reuse_roots_constraints_or_incompatibilities(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);wheels=root/"wheels"
            for version in ("1.0","2.0"):wheel(wheels,"library",version)
            admission=solver.admit(wheels,root/"snapshot")
            session=self.make_session(admission,VARIANTS[3])
            self.assertEqual(session.solve(["library>=1"])["selected"][0][1],"2.0")
            self.assertEqual(session.solve(["library>=1"],["library<2"])["selected"][0][1],"1.0")
            self.assertEqual(session.solve(["library>9"])["status"],"unsatisfiable")
            source=session.source
            newest=max(source.rows,key=lambda i:source.versions[i])
            provider=solver.Provider(session,{})
            req=session.requirement("library>=1")
            good=provider.find_matches("library",{"library":[req]},{"library":[]})
            changed=provider.find_matches("library",{"library":[req]},{"library":[solver.Candidate("library",newest,frozenset())]})
            self.assertEqual(len(good),2);self.assertEqual(len(changed),1)
            # Satisfaction cache retains requirement objects, avoiding id reuse.
            self.assertTrue(provider.is_satisfied_by(solver.parse_requirement("library>=1"),good[0]))
            self.assertFalse(provider.is_satisfied_by(solver.parse_requirement("library>9"),good[0]))

    def test_identity_relocation_pin_and_metadata_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);wheels=root/"wheels"
            path=wheel(wheels,"library","1.0")
            first=solver.admit(wheels,root/"one")
            shutil.copytree(wheels,root/"copied")
            second=solver.admit(root/"copied",root/"two")
            self.assertEqual(first["snapshot"],second["snapshot"])
            with self.assertRaises(ValueError):solver.Source(first["inputs"]["catalog"]["path"],"0"*64,"catalog")
            wheel(wheels,"library","1.0",["injected>=1"])
            with self.assertRaisesRegex(ValueError,"differs"):
                self.make_session(first,VARIANTS[0]).solve(["library"])
            # The admitted catalog remains the old immutable metadata snapshot;
            # later artifact delivery must independently verify its old byte ID.
            self.assertEqual(self.make_session(first,VARIANTS[2]).solve(["library"])["status"],"solved")
            changed=solver.admit(wheels,root/"changed")
            self.assertNotEqual(first["snapshot"],changed["snapshot"])
            self.assertEqual(self.make_session(changed,VARIANTS[3]).solve(["library"])["status"],"unsatisfiable")

    def test_same_version_artifacts_use_target_tag_and_artifact_scoped_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);wheels=root/"wheels"
            wheel(wheels,"library","1.0",["common==1"])
            wheel(wheels,"library","1.0",["platform-leaf==1"],tag="cp314-cp314-win_amd64")
            wheel(wheels,"common","1.0");wheel(wheels,"platform-leaf","1.0")
            admission=solver.admit(wheels,root/"snapshot")
            ordinary=self.solve_all(admission,["library==1"])[0]
            self.assertEqual({r[0] for r in ordinary["selected"]},{"library","common"})
            windows=self.solve_all(admission,["library==1"],target=target(platform="win32",tags=("cp314-cp314-win_amd64","py3-none-any")))[0]
            self.assertEqual({r[0] for r in windows["selected"]},{"library","platform-leaf"})

    def test_empty_missing_cycles_and_round_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);wheels=root/"wheels";wheels.mkdir()
            admission=solver.admit(wheels,root/"empty")
            self.assertEqual(self.solve_all(admission,["missing"])[0]["status"],"unsatisfiable")
            self.assertEqual(self.solve_all(admission,["missing;python_version<'1'"])[0]["selected"],[])
            wheel(wheels,"alpha","1.0",["bravo==1"]);wheel(wheels,"bravo","1.0",["alpha==1"])
            admission=solver.admit(wheels,root/"cycle")
            self.assertEqual(len(self.solve_all(admission,["alpha"])[0]["selected"]),2)
            session=self.make_session(admission,VARIANTS[3])
            self.assertEqual(session.solve(["alpha"],max_rounds=0)["status"],"round_limit")

    def test_equivalent_version_metadata_and_unsupported_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);wheels=root/"wheels"
            original=wheel(wheels,"library","1")
            original.rename(wheels/"library-1.0-py3-none-any.whl")
            admission=solver.admit(wheels,root/"snapshot")
            self.assertEqual(self.solve_all(admission,["library==1"])[0]["selected"][0][1],"1.0")
            with self.assertRaises(solver.UnsupportedInput):solver.parse_requirement("library @ https://example.invalid/a.whl")
            bad=wheel(root/"bad","bad","1.0",["other @ https://example.invalid/a.whl"])
            with self.assertRaises(solver.UnsupportedInput):solver.admit(bad.parent,root/"bad-snapshot")
            session=self.make_session(admission,VARIANTS[3])
            with self.assertRaises(solver.UnsupportedInput):session.solve(["library"],["library[extra]<2"])
            with self.assertRaises(ValueError):self.make_session(admission,VARIANTS[2],target={"environment":{},"tags":["py3-none-any"]})

    def test_cli_accepts_other_local_wheel_sets_requirements_and_unsat(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);wheels=root/"packages"
            wheel(wheels,"custom-root","1.0",["shared>=1;extra=='feature'"],extras=["feature"])
            wheel(wheels,"shared","1.0");wheel(wheels,"shared","2.0")
            requirements=root/"requirements.txt"
            requirements.write_text("# Local custom input\ncustom-root[feature]==1\n")
            for constraint,status in (("shared<2","solved"),("shared>9","unsatisfiable")):
                output=root/status
                command=[sys.executable,"-B",str(Path(__file__).with_name("benchmark.py")),"--wheelhouse",str(wheels),
                         "--requirements",str(requirements),"--constraint",constraint,"--trials","1","--passes","2","--output",str(output)]
                child=subprocess.run(command,text=True,capture_output=True)
                self.assertEqual(child.returncode,0,child.stderr)
                result=json.loads((output/"results.json").read_text())
                self.assertEqual(len(result["cases"]),7)
                for case in result["cases"]:
                    sample=case["samples"][0]
                    self.assertEqual(sample["status"],status)
                    self.assertTrue(sample["complete"])
                    if status=="solved":
                        self.assertEqual({r[0]:r[1] for r in sample["passes"][0]["selected"]},
                                         {"custom-root":"1.0","shared":"1.0"})
                reused=root/(status+"-reused")
                command=[sys.executable,"-B",str(Path(__file__).with_name("benchmark.py")),"--inputs",str(output/"results.json"),
                         "--variants","catalog-filter-cache","catalog-incremental","catalog-trail","--trials","1","--passes","2","--output",str(reused)]
                child=subprocess.run(command,text=True,capture_output=True)
                self.assertEqual(child.returncode,0,child.stderr)
                again=json.loads((reused/"results.json").read_text())
                for case in again["cases"]:
                    sample=case["samples"][0]
                    self.assertEqual(sample["status"],status)
                    self.assertEqual(sample["selection_sha256"],result["cases"][0]["samples"][0]["selection_sha256"])


if __name__=="__main__":unittest.main()
