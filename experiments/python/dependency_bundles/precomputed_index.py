"""Prototype producer-validated ZIP sidecar; this is not a standardized format.

The caller supplies a trusted SHA-256 for the index. Hash mode binds it to bundle
bytes on every open. Local mode uses the original file's stat identity as a cache
invalidation check, assuming a trusted immutable local store, not hostile writers.
Admission does all ZIP/name/header/CRC checks once. Consumers never parse ZIP.
"""

import hashlib
import json
import mmap
import os
from pathlib import Path
import time
import zipfile

from bundle_access import BundleReader
import binary_index


def file_identity(stat):
    return [stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns]


def digest_file(stream):
    stream.seek(0)
    return hashlib.file_digest(stream, "sha256").hexdigest()


def build_index(archive_path, index_path, *, encoding="json"):
    """Validate/admit one immutable archive and write its reusable range index."""
    if encoding not in ("json", "binary"):
        raise ValueError("index encoding must be json or binary")
    begin = time.perf_counter()
    reader = BundleReader(archive_path, "mmap")
    try:
        before = file_identity(os.fstat(reader._raw.fileno()))
        for name in reader.entries:
            with reader.view(name):
                pass  # Admission verifies every payload CRC as well as ZIP metadata.
        archive_digest = digest_file(reader._raw)
        if file_identity(os.fstat(reader._raw.fileno())) != before:
            raise ValueError("bundle changed during index construction")
        entries = sorted(([name, *reader.ranges[name], info.CRC]
                          for name, info in reader.entries.items()), key=lambda row: row[1])
        document = {"format": "gaia-zip-index", "version": 1, "archive_sha256": archive_digest,
                    "archive_size": reader.size, "local_identity": before,
                    "payload_end": reader._zip.start_dir, "entries": entries,
                    "directories": sorted(reader.directories)}
        encoded = (binary_index.encode(document) if encoding == "binary" else
                   json.dumps(document, ensure_ascii=True, separators=(",", ":")).encode("ascii"))
        Path(index_path).write_bytes(encoded)
    finally:
        reader.close()
    return {"build_seconds": time.perf_counter() - begin, "index_bytes": len(encoded),
            "index_sha256": hashlib.sha256(encoded).hexdigest(), "archive_sha256": archive_digest}


class Entry:
    __slots__ = ("filename", "CRC")

    def __init__(self, name, crc):
        self.filename, self.CRC = name, crc

    def is_dir(self):
        return False


class IndexedBundleReader(BundleReader):
    """Same mapped read/view/resource API with a pinned producer-built index."""

    def __init__(self, path, index_path, *, index_sha256, verify="hash"):
        if verify not in ("hash", "local"):
            raise ValueError("index verification must be hash or local")
        self.backend = "mmap"
        self.filename = str(path)
        self._raw = self._zip = self._mapping = self._resident = None
        self.entries, self.ranges = {}, {}
        try:
            encoded = Path(index_path).read_bytes()
            if hashlib.sha256(encoded).hexdigest() != index_sha256:
                raise ValueError("index digest mismatch")
            document = binary_index.decode(encoded) if encoded.startswith(binary_index.MAGIC) else json.loads(encoded)
            if document["format"] != "gaia-zip-index" or document["version"] != 1:
                raise ValueError("unsupported index format/version")
            self._raw = open(path, "rb")
            before = file_identity(os.fstat(self._raw.fileno()))
            self.size = before[2]
            if self.size != document["archive_size"]:
                raise ValueError("bundle size differs from index")
            if verify == "local":
                if before != document["local_identity"]:
                    raise ValueError("bundle changed since local admission")
            elif digest_file(self._raw) != document["archive_sha256"]:
                raise ValueError("bundle digest differs from index")
            end = document["payload_end"]
            if type(end) is not int or not 0 <= end <= self.size:
                raise ValueError("invalid indexed payload boundary")
            previous_end = 0
            for name, start, length, crc in document["entries"]:
                if (not isinstance(name, str) or name in self.entries
                        or any(type(n) is not int for n in (start, length, crc))
                        or start < previous_end or length < 0 or start + length > end
                        or not 0 <= crc <= 0xffffffff):
                    raise ValueError("invalid indexed entry/range")
                self.entries[name] = Entry(name, crc)
                self.ranges[name] = (start, length)
                previous_end = start + length
            # Namespace validation happened at admission; the pinned index carries it.
            self.directories = set(document["directories"])
            self._mapping = mmap.mmap(self._raw.fileno(), 0, access=mmap.ACCESS_READ)
            if file_identity(os.fstat(self._raw.fileno())) != before:
                raise ValueError("bundle changed while opening index")
        except BaseException:
            self.close()
            raise
