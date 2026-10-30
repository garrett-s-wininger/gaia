from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

import benchmark
from precomputed_index import build_index
from resolution_benchmark import profile_bucket, parse_profile


class ResolutionTests(unittest.TestCase):
    def test_discovery_never_reads_or_executes_target_code(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            source=root/"files"
            members=["pip/__init__.py","pip/child.py","pip/sub/__init__.py"]
            for member in members:
                target=source/member
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text("deliberately !!! invalid Python: discovery must not compile or execute this\n")
            archive,index=root/"input.zip",root/"input.index"
            benchmark.pack(source,archive,zipfile.ZIP_STORED)
            built=build_index(archive,index,encoding="binary")
            for reader in ("directory","mmap","python"):
                command=["--root",str(source if reader=="directory" else archive),"--reader",reader]
                command += ["--index",str(index),"--pin",built["index_sha256"],"--policy","local"]
                request=root/(reader+".json")
                benchmark.write_json(request,{"command":command,"mode":"source","members":members})
                result=benchmark.consume([sys.executable,"-I","-S","-B",str(benchmark.HERE/"resolution_benchmark.py"),
                                          "--worker","--requests",str(request)])
                self.assertTrue(result["correct"])
                self.assertEqual(result["hits"],3)
                self.assertEqual(result["misses"],3)
                self.assertEqual(result["pip_code_reads"],0)
                self.assertEqual(result["pip_imports"],0)

    def test_profile_buckets_are_disjoint_and_compilation_is_recognized(self):
        import cProfile
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"sample.pstats"
            profile=cProfile.Profile()
            profile.enable()
            compile("x=1\n","example.py","exec")
            profile.disable()
            profile.dump_stats(path)
            parsed=parse_profile(path)
            self.assertAlmostEqual(sum(parsed["buckets"].values()),parsed["total_self_seconds"])
            self.assertGreater(parsed["buckets"]["Source compilation"],0)
            self.assertEqual(profile_bucket("gaia-fixture:///pip/_vendor/resolvelib/resolvers/resolution.py","resolve"),
                             "Dependency solver/core integration")


if __name__=="__main__":
    unittest.main()
