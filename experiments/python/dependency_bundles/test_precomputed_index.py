import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import benchmark
import binary_index
from bundle_access import BundlePath
from precomputed_index import build_index, IndexedBundleReader


class IndexTests(unittest.TestCase):
    encoding = "json"

    def fixture(self, root):
        archive, index = root / "bundle.zip", root / "bundle.index"
        contents = {"pkg/__init__.py": b"value = 1\n", "pkg/data": bytes(range(256)) * 16,
                    "pkg/empty": b"", "pkg/sub/π": "hello π".encode(),
                    "root": b"root-level", "π/β": b"unicode-directory"}
        with zipfile.ZipFile(archive, "w") as bundle:
            for name, value in contents.items():
                bundle.writestr(name, value)
        return archive, index, contents, build_index(archive, index, encoding=self.encoding)

    def test_equivalence_without_zip_parsing_and_view_lifetime(self):
        with tempfile.TemporaryDirectory() as temp:
            archive, index, contents, built = self.fixture(Path(temp))
            for mode in ("hash", "local"):
                with patch("zipfile.ZipFile", side_effect=AssertionError("consumer parsed ZIP")):
                    reader = IndexedBundleReader(archive, index, index_sha256=built["index_sha256"], verify=mode)
                try:
                    for name, value in contents.items():
                        self.assertEqual(reader.read(name), value)
                        with reader.view(name) as view:
                            self.assertEqual(view, value)
                    self.assertEqual(BundlePath(reader, "pkg").joinpath("sub/π").read_bytes(), contents["pkg/sub/π"])
                    view = reader.view("pkg/data")
                    with self.assertRaises(BufferError):
                        reader.close()
                    view.release()
                finally:
                    reader.close()

    def test_index_pin_version_and_ranges(self):
        with tempfile.TemporaryDirectory() as temp:
            archive, index, _, built = self.fixture(Path(temp))
            original = index.read_bytes()
            index.write_bytes(original + b" ")
            with self.assertRaisesRegex(ValueError, "index digest"):
                IndexedBundleReader(archive, index, index_sha256=built["index_sha256"])
            for change in ("version", "range", "duplicate"):
                document = json.loads(original)
                if change == "version":
                    document["version"] = 2
                elif change == "range":
                    document["entries"][0][1] = document["archive_size"] + 1
                else:
                    document["entries"].append(document["entries"][0])
                encoded = json.dumps(document).encode()
                index.write_bytes(encoded)
                with self.assertRaises(ValueError):
                    IndexedBundleReader(archive, index, index_sha256=hashlib.sha256(encoded).hexdigest())

    def test_archive_binding_changes_and_portable_hash_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive, index, _, built = self.fixture(root)
            copy = root / "copy.zip"
            shutil.copyfile(archive, copy)
            reader = IndexedBundleReader(copy, index, index_sha256=built["index_sha256"])
            reader.close()
            with self.assertRaisesRegex(ValueError, "local admission"):
                IndexedBundleReader(copy, index, index_sha256=built["index_sha256"], verify="local")
            stat = archive.stat()
            contents = bytearray(archive.read_bytes())
            contents[0] ^= 1  # Even a metadata-only change invalidates the admitted bundle.
            archive.write_bytes(contents)
            os.utime(archive, ns=(stat.st_atime_ns, stat.st_mtime_ns))
            for mode in ("hash", "local"):
                with self.assertRaises(ValueError):
                    IndexedBundleReader(archive, index, index_sha256=built["index_sha256"], verify=mode)

    def test_payload_crc_and_admission_reject_corruption(self):
        with tempfile.TemporaryDirectory() as temp:
            archive, index, _, built = self.fixture(Path(temp))
            reader = IndexedBundleReader(archive, index, index_sha256=built["index_sha256"], verify="local")
            start, _ = reader.ranges["pkg/data"]
            # Deliberately violate immutability to exercise the retained per-read CRC.
            with archive.open("r+b") as stream:
                stream.seek(start)
                stream.write(b"\xff")
            try:
                with self.assertRaises(zipfile.BadZipFile):
                    reader.read("pkg/data")
            finally:
                reader.close()
            with self.assertRaises(zipfile.BadZipFile):
                build_index(archive, index, encoding=self.encoding)

    def test_source_bytecode_resources_and_origins_through_real_loader(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            manifest = benchmark.make_fixture(source, 16)
            manifest_path = root / "manifest.json"
            benchmark.write_json(manifest_path, manifest)
            bytecode = root / "bytecode"
            benchmark.precompile(source, bytecode)
            for mode, directory in (("source", source), ("bytecode", bytecode)):
                archive, index = root / (mode + ".zip"), root / (mode + ".index")
                benchmark.pack(directory, archive, zipfile.ZIP_STORED)
                built = build_index(archive, index, encoding=self.encoding)
                for verification in ("hash", "local"):
                    command = benchmark.worker_command(manifest_path, archive, "access-mmap", mode)
                    command += ["--index", str(index), "--index-sha256", built["index_sha256"],
                                "--index-verification", verification]
                    result = benchmark.consume(command)
                    self.assertTrue(result["correct"])
                    self.assertEqual(result["shared_archive_opens"], 1)
                    self.assertEqual(result["persistent_module_reads"], 40)


class BinaryIndexTests(IndexTests):
    encoding = "binary"

    def test_index_pin_version_and_ranges(self):
        with tempfile.TemporaryDirectory() as temp:
            archive, index, _, built = self.fixture(Path(temp))
            original = index.read_bytes()
            index.write_bytes(original + b" ")
            with self.assertRaisesRegex(ValueError, "index digest"):
                IndexedBundleReader(archive, index, index_sha256=built["index_sha256"])
            for change in ("version", "flags", "pool", "range", "directory", "name", "utf8", "truncated"):
                with self.subTest(change=change):
                    encoded = bytearray(original)
                    header = list(binary_index.HEADER.unpack_from(encoded))
                    record = list(binary_index.ENTRY.unpack_from(encoded, binary_index.HEADER.size))
                    if change in ("version", "flags", "pool"):
                        header[{"version": 1, "flags": 2, "pool": -1}[change]] += 1
                        binary_index.HEADER.pack_into(encoded, 0, *header)
                    elif change in ("range", "directory", "name"):
                        if change == "range":
                            record[0] = archive.stat().st_size + 1
                        elif change == "directory":
                            record[3] = header[-2]
                        else:
                            record[4] = len(encoded) + 1
                        binary_index.ENTRY.pack_into(encoded, binary_index.HEADER.size, *record)
                    elif change == "utf8":
                        encoded[-1] = 0xff
                    else:
                        encoded = encoded[:binary_index.HEADER.size - 1]
                    index.write_bytes(encoded)
                    with self.assertRaises(ValueError):
                        IndexedBundleReader(archive, index, index_sha256=hashlib.sha256(encoded).hexdigest())

    def test_json_and_binary_have_identical_logical_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            archive, index, _, _ = self.fixture(Path(temp))
            json_path = Path(temp) / "index.json"
            build_index(archive, json_path)
            binary = binary_index.decode(index.read_bytes())
            binary["entries"] = [list(row) for row in binary["entries"]]
            self.assertEqual(binary, json.loads(json_path.read_bytes()))
            self.assertEqual(binary_index.HEADER.size, 128)
            self.assertEqual(binary_index.ENTRY.size, 28)


if __name__ == "__main__":
    unittest.main()
