"""Equivalent whole-entry access over one immutable, plain stored ZIP.

This is an experimental input-access boundary, not a general ZIP implementation.
ZipFile parses the central directory for every backend. Indexed paths validate
local headers once, then read by offset. All reads verify payload CRCs, including
buffer views. Encryption, descriptors, compression and ZIP64 entries are rejected.
"""

from importlib.resources.abc import Traversable, TraversableResources
import io
import mmap
import os
from pathlib import PurePosixPath
import struct
import zipfile
import zlib


BACKENDS = ("zipfile", "pread", "mmap", "resident")
_HEADER = struct.Struct("<4s5H3I2H")


class BundleReader:
    def __init__(self, path, backend="zipfile", *, prefault="none"):
        if backend not in BACKENDS:
            raise ValueError(f"unknown backend: {backend}")
        if prefault not in ("none", "populate", "touch") or (prefault != "none" and backend != "mmap"):
            raise ValueError("prefault policy requires mmap: none, populate, or touch")
        self.backend = backend
        self.filename = str(path)
        self._raw = self._zip = self._mapping = self._resident = None
        self.entries, self.ranges = {}, {}
        try:
            self._raw = open(path, "rb")
            self.size = os.fstat(self._raw.fileno()).st_size
            self._zip = zipfile.ZipFile(self._raw)
            folded = set()
            for info in self._zip.infolist():
                name = info.filename
                if (not name or name.startswith("/") or "\\" in name or "\x00" in name
                        or any(p in ("", ".", "..") for p in name.split("/"))
                        or (len(name) > 1 and name[1] == ":")):
                    raise ValueError(f"unsupported entry name: {name!r}")
                if name in self.entries or name.casefold() in folded:
                    raise ValueError(f"duplicate/colliding name: {name}")
                if (info.is_dir() or info.compress_type != zipfile.ZIP_STORED
                        or info.flag_bits & ~0x800 or info.file_size >= 0xffffffff
                        or info.compress_size != info.file_size
                        or (info.external_attr >> 16) & 0o170000 not in (0, 0o100000)):
                    raise ValueError(f"only plain regular stored entries supported: {name}")
                self.entries[name] = info
                folded.add(name.casefold())
            self.directories = {""}
            for name in self.entries:
                for parent in PurePosixPath(name).parents:
                    if str(parent) != ".":
                        self.directories.add(str(parent) + "/")
            if any(d[:-1] in self.entries for d in self.directories if d):
                raise ValueError("file/directory name collision")
            if backend == "mmap":
                if prefault == "populate":
                    self._mapping = mmap.mmap(self._raw.fileno(), 0,
                                              flags=mmap.MAP_PRIVATE | mmap.MAP_POPULATE,
                                              prot=mmap.PROT_READ)
                else:
                    self._mapping = mmap.mmap(self._raw.fileno(), 0, access=mmap.ACCESS_READ)
                if prefault == "touch":
                    for offset in range(0, self.size, mmap.PAGESIZE):
                        self._mapping[offset]
            elif backend == "resident":
                self._raw.seek(0)
                self._resident = self._raw.read()
                if len(self._resident) != self.size:
                    raise zipfile.BadZipFile("short whole-bundle read")
            if backend != "zipfile":
                for info in self.entries.values():
                    self.ranges[info.filename] = self._entry_range(info)
                ordered = sorted((info.header_offset, self.ranges[info.filename][0] + info.file_size)
                                 for info in self.entries.values())
                if any(end > next_start for (_, end), (next_start, _) in zip(ordered, ordered[1:])):
                    raise zipfile.BadZipFile("overlapping member ranges")
        except BaseException:
            self.close()
            raise

    def _range(self, start, length):
        if start < 0 or length < 0 or start + length > self.size:
            raise zipfile.BadZipFile("range outside the immutable bundle")
        if self.backend == "mmap":
            data = self._mapping[start:start + length]
        elif self.backend == "resident":
            data = self._resident[start:start + length]
        else:
            data = os.pread(self._raw.fileno(), length, start)
        if len(data) != length:
            raise zipfile.BadZipFile("short positional read")
        return data

    def _entry_range(self, info):
        values = _HEADER.unpack(self._range(info.header_offset, _HEADER.size))
        signature, _, flags, method, _, _, crc, compressed, size, name_len, extra_len = values
        if (signature != b"PK\x03\x04" or flags != info.flag_bits or method != 0
                or crc != info.CRC or compressed != info.compress_size or size != info.file_size):
            raise zipfile.BadZipFile("local header differs from central directory")
        local_name = self._range(info.header_offset + _HEADER.size, name_len)
        expected = info.orig_filename.encode("utf-8" if flags & 0x800 else "cp437")
        if local_name != expected:
            raise zipfile.BadZipFile("local filename differs from central directory")
        start = info.header_offset + _HEADER.size + name_len + extra_len
        if start < 0 or start + size > self._zip.start_dir:
            raise zipfile.BadZipFile("member extends into/outside central directory")
        return start, size

    def infolist(self):
        return list(self.entries.values())

    def read(self, name):
        if self.backend == "zipfile":
            return self._zip.read(name)  # Standard header/name/CRC validation.
        if self.backend == "pread":
            start, length = self.ranges[name]
            data = self._range(start, length)
            if zlib.crc32(data) != self.entries[name].CRC:
                raise zipfile.BadZipFile(f"payload CRC mismatch: {name}")
            return data
        with self.view(name) as value:
            return value.tobytes()  # Same bytes-return contract as ZipFile.read.

    def view(self, name):
        if self.backend in ("zipfile", "pread"):
            return memoryview(self.read(name))  # These backends still allocate bytes.
        start, length = self.ranges[name]
        buffer = self._mapping if self.backend == "mmap" else self._resident
        value = memoryview(buffer)[start:start + length]
        if zlib.crc32(value) != self.entries[name].CRC:
            value.release()
            raise zipfile.BadZipFile(f"payload CRC mismatch: {name}")
        return value  # Caller must release before closing the reader/mapping.

    def close(self):
        if self._mapping is not None:
            self._mapping.close()  # Outstanding views fail explicitly with BufferError.
            self._mapping = None
        self._resident = None
        if self._zip is not None:
            self._zip.close()
            self._zip = None
        if self._raw is not None:
            self._raw.close()
            self._raw = None


class BundlePath(Traversable):
    """Common resource wrapper for ALL four backends in the controlled comparison."""

    def __init__(self, reader, path=""):
        self.reader = reader
        self.path = path

    @property
    def name(self):
        return self.path.rstrip("/").rsplit("/", 1)[-1]

    def is_file(self):
        return self.path in self.reader.entries

    def is_dir(self):
        return self.path.rstrip("/") + "/" in self.reader.directories if self.path else True

    def iterdir(self):
        if not self.is_dir():
            raise NotADirectoryError(self.path)
        prefix = self.path.rstrip("/") + "/" if self.path else ""
        if getattr(self.reader,'native_provider',False):
            return iter(BundlePath(self.reader,prefix+name) for name in self.reader.iter_resource_children(prefix))
        names = {name[len(prefix):].split("/", 1)[0] for name in self.reader.entries
                 if name.startswith(prefix)}
        return iter(BundlePath(self.reader, prefix + name) for name in sorted(names))

    def joinpath(self, *descendants):
        path = self.path.rstrip("/")
        for name in descendants:
            parts = str(name).split("/")
            if any(p in ("", ".", "..") for p in parts) or "\\" in str(name):
                raise ValueError("invalid bundle resource path")
            path = path + "/" + str(name) if path else str(name)
        return BundlePath(self.reader, path)

    def open(self, mode="r", *args, **kwargs):
        if mode not in ("r", "rb"):
            raise ValueError("bundle resources are read-only")
        if not self.is_file():
            raise FileNotFoundError(self.path)
        stream = io.BytesIO(self.reader.read(self.path))
        return stream if mode == "rb" else io.TextIOWrapper(stream, *args, **kwargs)


class BundleResources(TraversableResources):
    def __init__(self, provider, prefix):
        self.provider = provider
        self.prefix = prefix

    def files(self):
        return BundlePath(self.provider.open_archive(), self.prefix)
