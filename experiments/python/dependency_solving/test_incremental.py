"""Scheduling/rollback differential checks and a small exhaustive oracle."""
import itertools
from pathlib import Path
import random
import tempfile
import unittest

from fixtures import wheel
import solver
from incremental import IncrementalResolution
from trail import TrailResolution
from test_solver import target


def session(admission, engine):
    descriptor=admission["inputs"]["catalog"]
    return solver.Session(solver.Source(descriptor["path"],descriptor["sha256"],"catalog"),target(),
                          parsed_cache=True,match_cache=True,engine=engine)


class IncrementalTests(unittest.TestCase):
    def compare(self, admission, roots, constraints=(), max_rounds=1000):
        results=[session(admission,e).solve(roots,constraints,max_rounds=max_rounds) for e in ("baseline","incremental","trail")]
        self.assertEqual((results[0]["status"],results[0]["selected"]),(results[1]["status"],results[1]["selected"]))
        self.assertEqual((results[0]["status"],results[0]["selected"]),(results[2]["status"],results[2]["selected"]))
        return results

    def test_late_constraint_invalidates_pins_and_removes_old_dependencies(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);wheels=root/"wheels"
            wheel(wheels,"root","1.0",["alpha>=1","z-late==1"])
            wheel(wheels,"alpha","2.0",["bravo==2"])
            wheel(wheels,"alpha","1.0",["bravo==1"])
            wheel(wheels,"bravo","2.0",["orphan==1"])
            wheel(wheels,"bravo","1.0")
            wheel(wheels,"orphan","1.0")
            wheel(wheels,"z-late","1.0",["alpha<2"])
            admission=solver.admit(wheels,root/"snapshot")
            results=self.compare(admission,["root==1"])
            self.assertEqual({r[0]:r[1] for r in results[1]["selected"]},
                             {"root":"1.0","alpha":"1.0","bravo":"1.0","z-late":"1.0"})
            self.assertGreater(results[1]["engine_work"].get("information_pruning_scans",0),0)

    def test_failed_attempts_and_backjump_rebuild_do_not_publish_dirty_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);wheels=root/"wheels"
            wheel(wheels,"root","1.0",["alpha>=1","z-lock==1"])
            wheel(wheels,"alpha","2.0",["shared==2","would-be-orphan==1"])
            wheel(wheels,"alpha","1.0",["shared==1"])
            wheel(wheels,"shared","1.0");wheel(wheels,"shared","2.0")
            wheel(wheels,"would-be-orphan","1.0")
            wheel(wheels,"z-lock","1.0",["shared==1"])
            admission=solver.admit(wheels,root/"snapshot")
            baseline,incremental,trail=self.compare(admission,["root==1"])
            self.assertGreater(incremental["engine_work"].get("backjumps",0),0)
            self.assertGreater(incremental["engine_work"].get("queue_rebuilds",0),1)
            self.assertNotIn("would-be-orphan",{r[0] for r in incremental["selected"]})
            self.compare(admission,["root==1"],max_rounds=0)

    def test_work_tracks_changed_criteria_on_conflict_free_breadth(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);wheels=root/"wheels"
            count=40
            wheel(wheels,"root","1.0",[f"leaf-{i:02}==1" for i in range(count)])
            for i in range(count):wheel(wheels,f"leaf-{i:02}","1.0")
            admission=solver.admit(wheels,root/"snapshot")
            baseline,incremental,trail=self.compare(admission,["root==1"])
            self.assertEqual(incremental["provider"]["satisfaction_checks"],count+1)
            self.assertEqual(incremental["engine_work"]["queue_pops"],count+1)
            self.assertEqual(incremental["engine_work"]["queue_rebuilds"],1)
            self.assertLess(incremental["engine_work"]["criterion_checks"],2*(count+1))
            self.assertGreater(baseline["provider"]["satisfaction_checks"],count*count)

    def test_seeded_graphs_match_reference_and_finite_satisfiability_oracle(self):
        rng=random.Random(20261028)
        rollbacks=0
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)
            for case in range(80):
                root=base/str(case);wheels=root/"wheels"
                names=["alpha","bravo","charlie","delta"]
                for name in names:
                    for version in (1,2):
                        deps=[other+rng.choice([">=1","==1","==2","<2",">=2"])
                              for other in rng.sample(names,rng.randrange(3))]
                        wheel(wheels,name,f"{version}.0",deps)
                roots=[name+rng.choice([">=1","==1","==2"]) for name in rng.sample(names,rng.randrange(1,3))]
                admission=solver.admit(wheels,root/"snapshot")
                with self.subTest(case=case,roots=roots):
                    results=self.compare(admission,roots)
                    rollbacks+=results[2]["engine_work"].get("optimistic_rollbacks",0)
                    for resolution_type in (IncrementalResolution,TrailResolution):
                        audited=session(admission,"baseline")
                        resolution=resolution_type(solver.Provider(audited,{}),solver.Reporter(),audit=True)
                        try:
                            resolution.resolve([audited.requirement(r) for r in roots],1000)
                            status="solved"
                        except solver.ResolutionImpossible:status="unsatisfiable"
                        except solver.ResolutionTooDeep:status="round_limit"
                        self.assertEqual(status,results[1]["status"])
                    oracle=session(admission,"baseline")
                    valid=False
                    choices=[[None]+oracle.source.projects[name] for name in names]
                    for assignment in itertools.product(*choices):
                        mapping={name:solver.Candidate(name,row["id"],frozenset())
                                 for name,row in zip(names,assignment) if row is not None}
                        try:solver.validate_solution(oracle,mapping,[solver.parse_requirement(r) for r in roots],{})
                        except ValueError:continue
                        valid=True;break
                    self.assertEqual(results[1]["status"],"solved" if valid else "unsatisfiable")
        self.assertGreater(rollbacks,0,"seeded cases must exercise optimistic state restoration")


if __name__=="__main__":unittest.main()
