"""Experimental little-endian index: fixed records plus UTF-8 string pool.

128-byte header: magic, version, reserved, bundle size, payload boundary,
bundle SHA-256, five local stat fields, entry/directory counts, pool size.
28-byte entry: payload offset/length (u64), CRC/directory ID/name length (u32).
Directory lengths (u32) follow entries. Pool holds directories then basenames.
No native struct layout, pickle, compression, or pointer/address serialization.
"""

import struct


MAGIC = b"GAIAIDX\0"
HEADER = struct.Struct("<8sIIQQ32s5Q3Q")
ENTRY = struct.Struct("<QQIII")
LENGTH = struct.Struct("<I")


def encode(document):
    directories = document["directories"]
    ids = {name: i for i, name in enumerate(directories)}
    strings = [name.encode("utf-8") for name in directories]
    records = bytearray()
    for name, start, length, crc in document["entries"]:
        parent, separator, basename = name.rpartition("/")
        prefix = parent + separator
        encoded = basename.encode("utf-8")
        strings.append(encoded)
        records.extend(ENTRY.pack(start, length, crc, ids[prefix], len(encoded)))
    pool = b"".join(strings)
    header = HEADER.pack(MAGIC, 1, 0, document["archive_size"], document["payload_end"],
                         bytes.fromhex(document["archive_sha256"]), *document["local_identity"],
                         len(document["entries"]), len(directories), len(pool))
    lengths = b"".join(LENGTH.pack(len(name.encode("utf-8"))) for name in directories)
    return header + records + lengths + pool


def decode(encoded):
    if len(encoded) < HEADER.size:
        raise ValueError("truncated binary index header")
    values = HEADER.unpack_from(encoded)
    magic, version, reserved, size, payload_end, digest = values[:6]
    if magic != MAGIC or version != 1 or reserved != 0:
        raise ValueError("unsupported binary index format/version/flags")
    identity = list(values[6:11])
    entries, directory_count, pool_size = values[11:]
    lengths_start = HEADER.size + entries * ENTRY.size
    pool_start = lengths_start + directory_count * LENGTH.size
    if directory_count < 1 or pool_start + pool_size != len(encoded):
        raise ValueError("invalid binary index table/pool size")
    directories = []
    cursor = pool_start
    for i in range(directory_count):
        length, = LENGTH.unpack_from(encoded, lengths_start + i * LENGTH.size)
        end = cursor + length
        if end > len(encoded):
            raise ValueError("binary directory outside string pool")
        directories.append(encoded[cursor:end].decode("utf-8"))
        cursor = end
    if directories[0] != "" or len(set(directories)) != directory_count:
        raise ValueError("invalid binary directories")

    def rows():
        nonlocal cursor
        for i in range(entries):
            start, length, crc, directory_id, name_length = ENTRY.unpack_from(encoded, HEADER.size + i * ENTRY.size)
            end = cursor + name_length
            if directory_id >= directory_count or not name_length or end > len(encoded):
                raise ValueError("invalid binary entry name/directory")
            name = directories[directory_id] + encoded[cursor:end].decode("utf-8")
            cursor = end
            yield name, start, length, crc
        if cursor != len(encoded):
            raise ValueError("unused binary string-pool bytes")

    return {"format": "gaia-zip-index", "version": 1, "archive_size": size,
            "payload_end": payload_end, "archive_sha256": digest.hex(), "local_identity": identity,
            "directories": directories, "entries": rows()}
