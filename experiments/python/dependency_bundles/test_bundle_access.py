from pathlib import Path
import tempfile
import mmap
import unittest
import zipfile

from bundle_access import BACKENDS, BundleReader, BundlePath


class AccessTests(unittest.TestCase):
    def test_prefault_preserves_bytes_views_and_crc(self):
        policies = ("none", "touch", "populate") if hasattr(mmap, "MAP_POPULATE") else ("none", "touch")
        with tempfile.TemporaryDirectory() as temp:
            path, contents = self.make_archive(temp)
            for policy in policies:
                reader = BundleReader(path, "mmap", prefault=policy)
                start, _ = reader.ranges["pkg/data.bin"]
                try:
                    for name, expected in contents.items():
                        self.assertEqual(reader.read(name), expected)
                        with reader.view(name) as view:
                            self.assertEqual(view, expected)
                finally:
                    reader.close()
            data = bytearray(path.read_bytes())
            data[start] ^= 1
            path.write_bytes(data)
            for policy in policies:
                reader = BundleReader(path, "mmap", prefault=policy)
                try:
                    with self.assertRaises(zipfile.BadZipFile):
                        reader.read("pkg/data.bin")
                finally:
                    reader.close()

    def make_archive(self, root):
        path = Path(root)/"bundle.zip"
        contents = {"pkg/__init__.py": b"value=1\n", "pkg/data.bin": bytes(range(256))*16,
                    "pkg/empty": b"", "pkg/sub/text.txt": "hello π".encode()}
        with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_STORED) as archive:
            for name,value in contents.items():archive.writestr(name,value)
        return path,contents

    def test_all_backends_bytes_views_and_resources_match(self):
        with tempfile.TemporaryDirectory() as temp:
            path,contents=self.make_archive(temp)
            for backend in BACKENDS:
                with self.subTest(backend=backend):
                    reader=BundleReader(path,backend)
                    try:
                        for _ in range(2):
                            for name,value in reversed(list(contents.items())):
                                self.assertEqual(reader.read(name),value)
                                with reader.view(name) as view:self.assertEqual(view,value)
                        package=BundlePath(reader,"pkg")
                        self.assertTrue(package.is_dir())
                        self.assertEqual({p.name for p in package.iterdir()}, {"__init__.py","data.bin","empty","sub"})
                        self.assertEqual(package.joinpath("sub/text.txt").read_text(encoding="utf-8"),"hello π")
                        with self.assertRaises(FileNotFoundError):package.joinpath("missing").read_bytes()
                        with self.assertRaises(ValueError):package.joinpath("../escape")
                    finally:reader.close()

    def test_corrupt_payload_rejected_by_every_backend(self):
        with tempfile.TemporaryDirectory() as temp:
            path,_=self.make_archive(temp)
            reader=BundleReader(path,"pread")
            start,_=reader.ranges["pkg/data.bin"]
            reader.close()
            data=bytearray(path.read_bytes());data[start]^=1;path.write_bytes(data)
            for backend in BACKENDS:
                reader=BundleReader(path,backend)
                try:
                    with self.assertRaises(zipfile.BadZipFile):reader.read("pkg/data.bin")
                finally:reader.close()

    def test_header_name_and_bounds_are_validated(self):
        with tempfile.TemporaryDirectory() as temp:
            path,_=self.make_archive(temp)
            original=path.read_bytes()
            for change in ("name","length"):
                data=bytearray(original)
                if change=="name":data[30]^=1
                else:data[26:28]=b"\xff\xff"
                path.write_bytes(data)
                for backend in BACKENDS:
                    with self.subTest(backend=backend,change=change):
                        def load():
                            reader=BundleReader(path,backend)
                            try:reader.read("pkg/__init__.py")
                            finally:reader.close()
                        with self.assertRaises(zipfile.BadZipFile):load()

    def test_compressed_input_is_explicitly_outside_this_comparison(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"compressed.zip"
            with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED) as archive:archive.writestr("x",b"hello")
            for backend in BACKENDS:
                with self.assertRaisesRegex(ValueError,"stored entries"):BundleReader(path,backend)

    def test_mapping_close_requires_releasing_live_views(self):
        with tempfile.TemporaryDirectory() as temp:
            path,_=self.make_archive(temp)
            reader=BundleReader(path,"mmap")
            view=reader.view("pkg/data.bin")
            with self.assertRaises(BufferError):reader.close()
            view.release()
            reader.close()


if __name__=="__main__":unittest.main()
