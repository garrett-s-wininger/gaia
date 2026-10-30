"""Native cross-language correctness and fail-closed input checks (Linux)."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

import benchmark
import binary_index
from native_benchmark import compile_native
from precomputed_index import build_index


ODIN = shutil.which(os.environ.get("ODIN", "odin")) or os.environ.get("ODIN", "odin")


@unittest.skipUnless(sys.platform == "linux" and Path(ODIN).is_file() and shutil.which("cc"), "Linux Odin/C toolchain unavailable")
class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build_root = tempfile.TemporaryDirectory()
        cls.executable = Path(cls.build_root.name) / "reader"
        compile_native(cls.executable, ODIN)

    @classmethod
    def tearDownClass(cls):
        cls.build_root.cleanup()

    def fixture(self, root):
        archive, index, directory = root / "data.zip", root / "data.index", root / "files"
        contents = {"empty": b"", "pkg/data": bytes(range(256))*16,
                    "pkg/sub/text": b"hello", "root": b"root", "π/β": "unicode π".encode()}
        with zipfile.ZipFile(archive, "w") as bundle:
            for name, value in contents.items():
                bundle.writestr(name, value)
                target = directory / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(value)
        built = build_index(archive, index, encoding="binary")
        return archive, index, directory, contents, built

    def command(self, archive, index, directory, mode="index", policy="local", representation="bytes", lookup="named", pin=None):
        return [str(self.executable), str(index), pin or hashlib.sha256(index.read_bytes()).hexdigest(),
                str(archive), str(directory), mode, policy, representation, lookup]

    def test_every_native_access_path_matches_all_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            archive, index, directory, contents, built = self.fixture(Path(temp))
            expected = hashlib.sha256(b"".join(hashlib.sha256(v).digest() for v in contents.values())).hexdigest()
            token = sum(len(v)+(v[0]+v[-1] if v else 0) for v in contents.values())*4
            for mode in ("index", "zip", "directory"):
                for policy in ("hash", "local"):
                    for representation in (("bytes",) if mode == "directory" else ("bytes", "view")):
                        for lookup in ("named", "ordinal"):
                            with self.subTest(mode=mode, policy=policy, representation=representation, lookup=lookup):
                                result = benchmark.consume(self.command(archive,index,directory,mode,policy,representation,lookup))
                                self.assertEqual(result["validation_digest"], expected)
                                self.assertEqual(result["application_checksum"], token)
                                self.assertEqual(result["entries"], len(contents))
                                self.assertTrue(result["correct"])

    def test_pin_and_malformed_tables_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            archive, index, directory, _, built = self.fixture(Path(temp))
            original = index.read_bytes()
            index.write_bytes(original+b" ")
            result = subprocess.run(self.command(archive,index,directory,pin=built["index_sha256"]),capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("index digest",result.stderr)
            for change in ("truncated", "version", "flags", "counts", "pool", "range", "directory", "name", "utf8"):
                data = bytearray(original)
                header = list(binary_index.HEADER.unpack_from(data))
                row = list(binary_index.ENTRY.unpack_from(data,binary_index.HEADER.size))
                if change in ("version","flags","counts","pool"):
                    header[{"version":1,"flags":2,"counts":-3,"pool":-1}[change]] += 1
                    binary_index.HEADER.pack_into(data,0,*header)
                elif change in ("range","directory","name"):
                    row[{"range":0,"directory":3,"name":4}[change]] = len(data)+archive.stat().st_size
                    binary_index.ENTRY.pack_into(data,binary_index.HEADER.size,*row)
                elif change == "utf8":
                    data[-1]=0xff
                else:
                    data=data[:100]
                index.write_bytes(data)
                with self.subTest(change=change):
                    result=subprocess.run(self.command(archive,index,directory),capture_output=True,text=True)
                    self.assertNotEqual(result.returncode,0)
                    self.assertEqual(result.stdout,"")

    def test_archive_hash_and_local_identity_bindings(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            archive,index,directory,_,_=self.fixture(root)
            copy=root/"copy.zip"
            shutil.copyfile(archive,copy)
            self.assertTrue(benchmark.consume(self.command(copy,index,directory,policy="hash"))["correct"])
            result=subprocess.run(self.command(copy,index,directory),capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("local admission",result.stderr)
            data=bytearray(archive.read_bytes());data[0]^=1;archive.write_bytes(data)
            result=subprocess.run(self.command(archive,index,directory,policy="hash"),capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("bundle digest",result.stderr)

    def test_payload_crc_retained_independent_of_setup_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            archive,index,directory,_,_=self.fixture(Path(temp))
            encoded=bytearray(index.read_bytes())
            doc=binary_index.decode(encoded)
            rows=list(doc["entries"])
            start=next(row[1] for row in rows if row[0]=="pkg/data")
            data=bytearray(archive.read_bytes());data[start]^=1;archive.write_bytes(data)
            # Deliberately refresh local identity only to exercise CRC after setup.
            stat=archive.stat()
            header=list(binary_index.HEADER.unpack_from(encoded))
            header[6:11]=[stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns]
            binary_index.HEADER.pack_into(encoded,0,*header)
            index.write_bytes(encoded)
            result=subprocess.run(self.command(archive,index,directory),capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("payload CRC",result.stderr)

    def test_missing_and_corrupt_directory_files_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            archive,index,directory,_,_=self.fixture(Path(temp))
            target=directory/"root"
            target.write_bytes(b"xxxx")
            result=subprocess.run(self.command(archive,index,directory,mode="directory"),capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("payload CRC",result.stderr)
            target.unlink()
            result=subprocess.run(self.command(archive,index,directory,mode="directory"),capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)

    def test_zip_control_revalidates_local_headers(self):
        with tempfile.TemporaryDirectory() as temp:
            archive,index,directory,_,_=self.fixture(Path(temp))
            data=bytearray(archive.read_bytes())
            data[0]^=1
            archive.write_bytes(data)
            # Let the controlled test reach ZIP validation after local binding.
            encoded=bytearray(index.read_bytes())
            header=list(binary_index.HEADER.unpack_from(encoded))
            stat=archive.stat()
            header[6:11]=[stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns]
            binary_index.HEADER.pack_into(encoded,0,*header)
            index.write_bytes(encoded)
            result=subprocess.run(self.command(archive,index,directory,mode="zip"),capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("local header",result.stderr)


if __name__ == "__main__":
    unittest.main()
