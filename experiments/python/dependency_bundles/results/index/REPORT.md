# Precomputed ZIP index experiment

Run: `20261028T214926.016461Z`.

Warm/reused filesystem cache, fresh isolated process per trial, randomized case order. Every reader uses the exact same stored ZIP within a corpus, demand-paged mmap, and CRC on every payload read/view. Full SHA-256 member equivalence is checked after timing. The sidecar is experimental JSON, version 1; no container/protocol is standardized.

## Verification and timing boundaries

- `mmap`: reparse ZIP central directory and validate names/local headers/ranges on each open.
- `index-hash`: load/hash the pinned sidecar, verify whole-bundle SHA-256 on each open, check index structure/ranges, map bundle. ZIP validation occurred when building the index.
- `index-local`: same sidecar loading/validation, but compare the admitted bundle's device, inode, size, mtime and ctime rather than hash its bytes. Assumes a trusted immutable local store; stat checks are cache invalidation, not cryptographic verification. Transfer/replacement requires hash verification or readmission. Concurrent mutation/truncation is unsupported.
- The caller pins the sidecar's SHA-256 outside the index. This experiment's trusted harness supplies it on the command line. Index integrity is checked on every open; a self-reported bundle hash alone would not certify an index's name-to-range mapping.
- Producer admission parses/checks ZIP metadata, verifies all payload CRCs, hashes the bundle, builds names/ranges/directories, and serializes/writes the sidecar. Its cost is reported separately. Writes are buffered; durability/fsync, transfer and dependency resolution are not timed.
- Consumer open time includes sidecar I/O/hash/JSON decode, entry construction, range checks, bundle verification and mapping. Producer work is not charged to every consumer; one-use cost must add it back. Reader close and extra validation are outside access timing.

## Producer cost and storage

15 index builds per corpus. Index bytes include the range/name/directory table and identity metadata. ZIP bytes remain unchanged.

| Corpus | Entries | Payload bytes | ZIP bytes | Index bytes | Added storage | Build median ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| source | 2104 | 429,600 | 744,838 | 134,247 | 18.0% | 30.823 |
| bytecode | 2104 | 1,107,434 | 1,426,816 | 136,981 | 9.6% | 31.594 |
| 1 MiB entries | 64 | 67,108,864 | 67,115,670 | 3,217 | 0.0% | 74.270 |

## Byte access

15 trials per case; four lexical scans per process. Medians, ms. First use is index + first scan for each sample, then median; reused is mean of scans 2–4, then median. Bytes mode copies; view mode avoids payload copying.

| Corpus | Result | Reader | Open/index ms | First scan ms | Reused scan ms | First use ms | First use p95 ms | Peak RSS MiB |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| source | bytes | mmap | 27.070 | 1.699 | 1.640 | 28.769 | 31.700 | 25.94 |
| source | view | mmap | 26.854 | 1.616 | 1.534 | 28.389 | 31.393 | 25.98 |
| source | bytes | index-hash | 3.170 | 1.747 | 1.650 | 4.870 | 8.821 | 24.84 |
| source | view | index-hash | 3.305 | 1.641 | 1.528 | 5.006 | 6.986 | 24.83 |
| source | bytes | index-local | 2.418 | 2.068 | 1.667 | 4.449 | 5.274 | 24.89 |
| source | view | index-local | 2.426 | 1.707 | 1.495 | 4.216 | 6.020 | 24.88 |
| bytecode | bytes | mmap | 28.276 | 2.077 | 1.949 | 30.353 | 35.431 | 26.73 |
| bytecode | view | mmap | 30.380 | 1.930 | 1.787 | 32.403 | 37.920 | 26.76 |
| bytecode | bytes | index-hash | 3.975 | 2.171 | 1.997 | 6.118 | 7.709 | 25.54 |
| bytecode | view | index-hash | 3.884 | 2.635 | 2.033 | 6.479 | 10.649 | 25.53 |
| bytecode | bytes | index-local | 2.431 | 2.362 | 2.143 | 4.905 | 7.029 | 25.51 |
| bytecode | view | index-local | 2.755 | 2.098 | 1.933 | 4.792 | 8.383 | 25.54 |
| 1 MiB entries | bytes | mmap | 1.719 | 31.075 | 25.742 | 32.759 | 36.558 | 89.21 |
| 1 MiB entries | view | mmap | 1.613 | 25.578 | 22.850 | 27.710 | 31.418 | 88.28 |
| 1 MiB entries | bytes | index-hash | 48.712 | 32.407 | 25.930 | 79.060 | 99.604 | 89.20 |
| 1 MiB entries | view | index-hash | 47.122 | 24.947 | 22.517 | 72.597 | 80.750 | 88.33 |
| 1 MiB entries | bytes | index-local | 0.235 | 31.346 | 26.183 | 31.582 | 42.833 | 89.20 |
| 1 MiB entries | view | index-local | 0.264 | 25.412 | 23.033 | 25.748 | 32.805 | 88.30 |

## Fixed language loader

Same persistent module loader, compilation/bytecode behavior, resource wrapper and validation under every reader. Sidecars are loaded lazily inside the import phase. Adapter imports/setup are equal across cases and included in process wall time. Medians, ms.

| Input | Reader | Import ms | Resources ms | Workload ms | Process wall ms | Peak RSS MiB |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| source | mmap | 151.734 | 1.195 | 162.508 | 271.611 | 31.09 |
| source | index-hash | 124.261 | 1.164 | 134.659 | 242.343 | 30.33 |
| source | index-local | 120.898 | 1.168 | 130.990 | 246.202 | 30.34 |
| bytecode | mmap | 70.639 | 1.166 | 79.618 | 183.845 | 31.32 |
| bytecode | index-hash | 46.507 | 1.145 | 55.445 | 156.363 | 30.45 |
| bytecode | index-local | 46.731 | 1.191 | 56.339 | 159.932 | 30.44 |

## Limits

Synthetic regular source/sourceless-bytecode packages and stored entries only, no real package startup, cold storage, sparse requests, network transport or memory pressure. The larger corpus is 64 one-MiB payloads. Full bundle hashing touches every byte; local stat mode does not and has a different trust boundary. Neither mode permits mutable mapped files. The trusted producer must use the validated builder: consumer checks do not repeat ZIP/name-to-content certification. CRC detects accidental corruption and is not authentication. JSON and Python dictionaries still allocate per entry; this is not a native or hardware floor. The reader skips ZIP parsing; missing-module correctness probes can still invoke the standard ZIP fallback outside the timed workload, and process wall includes those probes. No syscall traces are claimed for this run. Raw commands, archive/index identities, timings, fault deltas and correctness are in results.json.
