"""Correctness tests for the consumer and for measurements we rely on."""

from pathlib import Path
import subprocess
import tempfile
import unittest
import warnings
import zipfile

import benchmark
from persistent_zip_loader import PersistentZipProvider


class ConsumerTests(unittest.TestCase):
    def test_equivalent_loading_and_resources_in_all_layouts_and_modes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            manifest = benchmark.make_fixture(source, 16, rounds=2)
            manifest_path = root / "manifest.json"
            benchmark.write_json(manifest_path, manifest)
            bytecode = root / "bytecode"
            benchmark.precompile(source, bytecode)
            for mode, directory in (("source", source), ("bytecode", bytecode)):
                for layout in benchmark.LAYOUTS:
                    with self.subTest(mode=mode, layout=layout):
                        target = directory
                        if layout != "directory":
                            target = root / f"{mode}-{layout}.zip"
                            benchmark.pack(directory, target, zipfile.ZIP_STORED if layout.endswith("stored") or layout.startswith("access-")
                                           else zipfile.ZIP_DEFLATED)
                        output = benchmark.consume(benchmark.worker_command(
                            manifest_path, target, layout, mode))
                        self.assertTrue(output["correct"])
                        self.assertEqual(output["verified_modules"], 40)
                        self.assertEqual(output["verified_resources"], 32)
                        self.assertEqual(output["application_checksum"], manifest["application_checksum"])
                        self.assertEqual(output["peak_rss_source"], "/proc/self/status VmHWM")
                        self.assertGreater(output["peak_rss_bytes"], 0)
                        if layout.startswith(("shared-", "persistent-", "access-")):
                            self.assertEqual(output["shared_archive_opens"], 1)
                        if layout.startswith(("persistent-", "access-")):
                            self.assertEqual(output["persistent_module_reads"], 40)
            self.assertEqual(list(source.rglob("*.pyc")), [])

    def test_missing_fixture_does_not_fall_back_to_original_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = benchmark.make_fixture(root / "source", 16)
            benchmark.write_json(root / "manifest.json", manifest)
            archive = root / "empty.zip"
            with zipfile.ZipFile(archive, "w"):
                pass
            with self.assertRaises(subprocess.CalledProcessError) as failure:
                benchmark.consume(benchmark.worker_command(
                    root / "manifest.json", archive, "stored", "source"))
            self.assertIn("ModuleNotFoundError", failure.exception.stderr)

    def test_tampered_resource_fails_consumer_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            manifest = benchmark.make_fixture(source, 16)
            entry = manifest["resources"][0]
            (source / entry["package"].replace(".", "/") / entry["name"]).write_bytes(b"wrong")
            benchmark.write_json(root / "manifest.json", manifest)
            with self.assertRaises(subprocess.CalledProcessError) as failure:
                benchmark.consume(benchmark.worker_command(
                    root / "manifest.json", source, "directory", "source"))
            self.assertIn("resource mismatch", failure.exception.stderr)


class MeasurementTests(unittest.TestCase):
    def test_persistent_discovery_reads_no_code_and_reuses_one_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = benchmark.make_fixture(root / "source", 16)
            archive = root / "bundle.zip"
            benchmark.pack(root / "source", archive, zipfile.ZIP_STORED)
            provider = PersistentZipProvider(str(archive))
            try:
                name = manifest["modules"][0]
                spec = provider.find_spec(name)
                self.assertIsNotNone(spec)
                spec.loader.get_filename(name)
                provider.find_spec(manifest["modules"][-1])
                self.assertEqual(provider.archive_opens, 1)
                self.assertEqual(provider.module_reads, 0)
                spec.loader.get_code(name)
                self.assertEqual(provider.module_reads, 1)
                self.assertEqual(provider.archive_opens, 1)
            finally:
                provider.close()

    def test_persistent_bytecode_rejects_an_invalid_header(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "bundle.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("example/__init__.pyc", b"bad")
            provider = PersistentZipProvider(str(archive))
            try:
                spec = provider.find_spec("example")
                with self.assertRaisesRegex(ImportError, "incompatible bytecode"):
                    spec.loader.get_code("example")
            finally:
                provider.close()

    def test_archive_validation_rejects_collisions_paths_and_nonfiles(self):
        with tempfile.TemporaryDirectory() as temporary:
            for names in (("a.py", "a.py"), ("A.py", "a.py"), ("../escape",),
                          ("/absolute",), ("a", "a/b"), ("dir/",)):
                with self.subTest(names=names):
                    archive = Path(temporary) / "invalid.zip"
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", UserWarning)
                        with zipfile.ZipFile(archive, "w") as bundle:
                            for name in names:
                                bundle.writestr(name, b"x")
                    with self.assertRaises(ValueError):
                        benchmark.validate_archive(archive)
            with zipfile.ZipFile(archive, "w") as bundle:
                info = zipfile.ZipInfo("link")
                info.external_attr = 0o120777 << 16
                bundle.writestr(info, "outside")
            with self.assertRaises(ValueError):
                benchmark.validate_archive(archive)

    def test_trace_counts_only_bracketed_workload(self):
        trace = '''10 openat(AT_FDCWD, "/setup", O_RDONLY) = 3
10 write(2, "GAIA_WORKLOAD_BEGIN\\n", 20) = 20
10 newfstatat(AT_FDCWD, "/missing", 0x0, 0) = -1 ENOENT (No such file)
10 openat(AT_FDCWD, "/fixture", O_RDONLY) = 3
10 read(3, "hello", 5) = 5
10 read(3, "", 5) = 0
10 lseek(3, 0, SEEK_SET) = 0
10 write(2, "GAIA_WORKLOAD_END\\n", 18) = 18
10 openat(AT_FDCWD, "/validation", O_RDONLY) = 3
'''
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trace"
            path.write_text(trace)
            stats = benchmark.parse_trace(path)
            self.assertEqual(stats["open_calls"], 1)
            self.assertEqual(stats["metadata_calls"], 1)
            self.assertEqual(stats["read_calls"], 2)
            self.assertEqual(stats["read_bytes"], 5)
            self.assertEqual(stats["errors"], {"newfstatat": 1})
            path.write_text('write(2, "GAIA_WORKLOAD_BEGIN\\n", 20) = 20\n')
            with self.assertRaises(ValueError):
                benchmark.parse_trace(path)


if __name__ == "__main__":
    unittest.main()
