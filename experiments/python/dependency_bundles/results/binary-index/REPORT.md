# Precomputed ZIP index experiment

Run: `20261028T215942.023584Z`.

Warm/reused filesystem cache, fresh isolated process per trial, randomized case order. Every reader uses the exact same stored ZIP within a corpus, demand-paged mmap, and CRC on every payload read/view. Full SHA-256 member equivalence is checked after timing. Sidecar encodings are experimental version 1; no container/protocol is standardized.

## Verification and timing boundaries

- `mmap`: reparse ZIP central directory and validate names/local headers/ranges on each open.
- `index-hash`: load/hash the pinned sidecar, verify whole-bundle SHA-256 on each open, check index structure/ranges, map bundle. ZIP validation occurred when building the index.
- `index-local`: same sidecar loading/validation, but compare the admitted bundle's device, inode, size, mtime and ctime rather than hash its bytes. Assumes a trusted immutable local store; stat checks are cache invalidation, not cryptographic verification. Transfer/replacement requires hash verification or readmission. Concurrent mutation/truncation is unsupported.
- `index-*` uses JSON. Where present, `binary-*` uses a 128-byte little-endian header, 28-byte fixed entry records, directory lengths and a UTF-8 string pool. Directories are stored once; records reference a directory ID and basename. Reads still decode names and construct the same Python entry/range dictionaries. Sidecars are read into bytes in both cases, not directly queried in place. Binary rows are decoded one at a time without JSON's row lists.
- The caller pins the sidecar's SHA-256 outside the index. This experiment's trusted harness supplies it on the command line. Index integrity is checked on every open; a self-reported bundle hash alone would not certify an index's name-to-range mapping.
- Producer admission parses/checks ZIP metadata, verifies all payload CRCs, hashes the bundle, builds names/ranges/directories, and serializes/writes the sidecar. Its cost is reported separately. Writes are buffered; durability/fsync, transfer and dependency resolution are not timed.
- Consumer open time includes sidecar I/O/hash/decode, entry construction, range checks, bundle verification and mapping. Producer work is not charged to every consumer; one-use cost must add it back. Reader close and extra validation are outside access timing.

## Producer cost and storage

15 index builds per corpus. Index bytes include the range/name/directory table and identity metadata. ZIP bytes remain unchanged.

| Corpus | Encoding | Entries | Payload bytes | ZIP bytes | Index bytes | Added storage | Build median ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| source | json | 2104 | 429,600 | 744,838 | 134,247 | 18.024% | 31.774 |
| source | binary | 2104 | 429,600 | 744,838 | 88,872 | 11.932% | 31.616 |
| bytecode | json | 2104 | 1,107,434 | 1,426,816 | 136,981 | 9.600% | 33.893 |
| bytecode | binary | 2104 | 1,107,434 | 1,426,816 | 90,944 | 6.374% | 34.058 |
| 1 MiB entries | json | 64 | 67,108,864 | 67,115,670 | 3,217 | 0.005% | 75.918 |
| 1 MiB entries | binary | 64 | 67,108,864 | 67,115,670 | 2,636 | 0.004% | 77.050 |

## Byte access

15 trials per case; four lexical scans per process. Medians, ms. First use is index + first scan for each sample, then median; reused is mean of scans 2–4, then median. Bytes mode copies; view mode avoids payload copying.

| Corpus | Result | Reader | Open/index ms | First scan ms | Reused scan ms | First use ms | First use p95 ms | Peak RSS MiB |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| source | bytes | mmap | 28.607 | 1.957 | 1.858 | 30.650 | 39.190 | 25.91 |
| source | view | mmap | 28.503 | 1.568 | 1.612 | 30.348 | 37.232 | 26.00 |
| source | bytes | index-hash | 3.510 | 1.980 | 1.688 | 5.604 | 6.479 | 24.98 |
| source | view | index-hash | 3.398 | 1.608 | 1.554 | 4.989 | 7.390 | 24.98 |
| source | bytes | index-local | 2.709 | 1.870 | 1.639 | 4.787 | 6.446 | 25.04 |
| source | view | index-local | 2.783 | 1.962 | 1.660 | 5.118 | 6.059 | 25.03 |
| source | bytes | binary-hash | 3.949 | 1.818 | 1.771 | 5.677 | 8.391 | 24.67 |
| source | view | binary-hash | 4.203 | 1.764 | 1.689 | 6.023 | 8.877 | 24.67 |
| source | bytes | binary-local | 3.156 | 1.954 | 1.710 | 5.133 | 6.501 | 24.61 |
| source | view | binary-local | 3.011 | 1.825 | 1.534 | 5.103 | 7.847 | 24.64 |
| bytecode | bytes | mmap | 29.337 | 2.137 | 2.042 | 31.433 | 38.074 | 26.72 |
| bytecode | view | mmap | 28.807 | 2.003 | 1.971 | 30.944 | 38.884 | 26.75 |
| bytecode | bytes | index-hash | 3.943 | 2.217 | 2.171 | 6.534 | 8.308 | 25.66 |
| bytecode | view | index-hash | 4.325 | 2.132 | 1.956 | 6.564 | 13.718 | 25.72 |
| bytecode | bytes | index-local | 2.668 | 2.514 | 2.063 | 5.328 | 7.314 | 25.65 |
| bytecode | view | index-local | 2.825 | 2.500 | 1.901 | 5.450 | 7.015 | 25.64 |
| bytecode | bytes | binary-hash | 4.392 | 2.531 | 2.241 | 7.387 | 9.492 | 25.39 |
| bytecode | view | binary-hash | 4.386 | 2.100 | 1.966 | 6.555 | 10.719 | 25.43 |
| bytecode | bytes | binary-local | 3.477 | 2.868 | 2.054 | 6.518 | 8.306 | 25.38 |
| bytecode | view | binary-local | 2.996 | 2.154 | 2.005 | 5.305 | 9.695 | 25.39 |
| 1 MiB entries | bytes | mmap | 1.690 | 32.321 | 26.663 | 34.174 | 36.653 | 89.23 |
| 1 MiB entries | view | mmap | 1.911 | 26.298 | 23.552 | 28.466 | 35.204 | 88.30 |
| 1 MiB entries | bytes | index-hash | 47.859 | 34.197 | 27.189 | 81.777 | 88.316 | 89.22 |
| 1 MiB entries | view | index-hash | 47.817 | 27.854 | 24.336 | 76.291 | 87.216 | 88.34 |
| 1 MiB entries | bytes | index-local | 0.296 | 33.308 | 27.277 | 33.562 | 40.956 | 89.21 |
| 1 MiB entries | view | index-local | 0.238 | 27.441 | 23.519 | 27.675 | 35.483 | 88.29 |
| 1 MiB entries | bytes | binary-hash | 47.229 | 32.565 | 26.963 | 79.624 | 92.434 | 89.21 |
| 1 MiB entries | view | binary-hash | 47.042 | 27.461 | 23.752 | 74.603 | 80.590 | 88.34 |
| 1 MiB entries | bytes | binary-local | 0.332 | 32.534 | 26.373 | 32.887 | 44.672 | 89.22 |
| 1 MiB entries | view | binary-local | 0.321 | 27.269 | 23.436 | 27.541 | 35.773 | 88.31 |

## Fixed language loader

Same persistent module loader, compilation/bytecode behavior, resource wrapper and validation under every reader. Sidecars are loaded lazily inside the import phase. Adapter imports/setup are equal across cases and included in process wall time. Medians, ms.

| Input | Reader | Import ms | Resources ms | Workload ms | Process wall ms | Peak RSS MiB |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| source | mmap | 152.826 | 1.252 | 162.768 | 288.385 | 30.97 |
| source | index-hash | 127.094 | 1.165 | 138.473 | 259.144 | 30.32 |
| source | index-local | 131.096 | 1.151 | 141.503 | 258.180 | 30.29 |
| source | binary-hash | 126.336 | 1.229 | 137.957 | 247.171 | 30.20 |
| source | binary-local | 122.126 | 1.246 | 133.274 | 255.623 | 30.16 |
| bytecode | mmap | 77.256 | 1.267 | 88.975 | 204.585 | 31.32 |
| bytecode | index-hash | 48.303 | 1.192 | 57.988 | 172.126 | 30.43 |
| bytecode | index-local | 53.404 | 1.176 | 63.820 | 173.659 | 30.43 |
| bytecode | binary-hash | 50.183 | 1.273 | 60.279 | 173.380 | 30.42 |
| bytecode | binary-local | 51.414 | 1.274 | 61.422 | 169.002 | 30.43 |

## Limits

Synthetic regular source/sourceless-bytecode packages and stored entries only, no real package startup, cold storage, sparse requests, network transport or memory pressure. The larger corpus is 64 one-MiB payloads. Full bundle hashing touches every byte; local stat mode does not and has a different trust boundary. Neither mode permits mutable mapped files. The trusted producer must use the validated builder: consumer checks do not repeat ZIP/name-to-content certification. CRC detects accidental corruption and is not authentication. Decoding and Python dictionaries still allocate per entry; this is not a native or hardware floor. The reader skips ZIP parsing; missing-module correctness probes can still invoke the standard ZIP fallback outside the timed workload, and process wall includes those probes. No syscall traces are claimed for this run. Raw commands, archive/index identities, timings, fault deltas and correctness are in results.json.
