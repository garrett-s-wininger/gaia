# Batch physical condition verification in Odin

One Odin call replaces the retained producer's per-file Python verification loop. It reduces condition export by roughly 0.7–1.2 ms in this comparison, while reading and hashing every required backing file. Moving final metadata/index emission into that call adds a smaller improvement. The exact `GAIACQ01` output remains unchanged.

## Matched complete operations

Run `20261031T013922.798684Z`: seven randomized paired blocks, Zstandard 1.5.7 portable C plus a probe, 31 objects and eight workers. Same admitted inputs, commands, source edits, cache policies and resident compiler/checker workers. Filesystem pages and retained producer state are warm. Every actual retained/native export is compared against the original reference index outside timing.

| Operation | Python retained ms | Odin verification ms | Odin verification + emission ms | Ninja ms | Ninja + ccache ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Unchanged | 2.63 | 2.57 | 2.55 | 3.24 | 3.19 |
| Implementation | 58.11 | 54.87 | 54.69 | 70.25 | 101.42 |
| Shared audit header | 35.54 | 33.31 | 32.75 | 45.03 | 67.86 |
| Generated audit header | 34.92 | 32.89 | 32.77 | 43.54 | 65.22 |
| Unused header | 2.64 | 2.64 | 2.59 | 3.17 | 3.09 |
| Edit/revert | 10.24 | 9.67 | 10.12 | 66.84 | 25.35 |

Native verification wins 7/7, 5/7 and 6/7 source/shared/generated blocks against the Python retained producer. Verification plus emission wins 6/7, 6/7 and 7/7. Both native paths beat both Ninja controls in all seven source/header blocks. No-op, unused-header and whole-result revert paths bypass export; their differences are not native-verifier gains.

Complete-operation differences are larger than exporter differences and include compilation and other stage variation. Do not attribute the whole 2–3 ms improvement to moving this loop. The directly observed exporter result is narrower:

| Export | Python retained ms | Odin verification ms | Odin verification + emission ms |
| --- | ---: | ---: | ---: |
| Implementation | 5.40 | 4.73 | 4.58 |
| Shared header | 5.28 | 4.50 | 4.45 |
| Generated header | 5.65 | 4.45 | 4.41 |

See [summary](summary.json) for paired differences, stage medians and representative counters; [validation](validation.json) covers complete artifacts/runtime probes/work counts. This remains one admitted C target, not a general build-system floor.

## What still costs time

The native pass handles 187 positive files, about 3 MiB, in roughly 3.0 ms. Its internal counters show about 0.44–0.46 ms in read syscalls and 1.24–1.30 ms in SHA-256 updates. The remainder includes stat/open/close, stability checks, parsing, hash initialization/finalization and instrumentation. It is not all filesystem time. Metadata stores and final index hashing cost about 0.02 ms in emission mode.

The measured difference between FFI-call duration and native duration is about 17 microseconds. Caller buffer preparation/result handling and Python template construction are also inside export; crossing the ABI is not the dominant remaining cost. Verification-only mode returns stat rows and lets Python patch/hash the index; emission mode patches/hashes the complete index in Odin. The gap between them is small, so a wider rewrite of Python bookkeeping has no demonstrated large payoff here.

The caller still creates row prefixes and logical SHA-256 identities, reusing exact immutable body identities under the prior policy. Odin verifies physical bytes using OpenSSL SHA-256, the same algorithm/provider family as the Python control. No digest identities change. Fragment serialization/publication, index writes, receipt recording and linked-result retention remain inside the full-operation clock.

## Interface, checks and bounds

The [Odin helper](../../condition_verify.odin) is a shared library with one caller-owned bounded request/output interface. A `GAIACQ01` template supplies prefixes, expected lengths and logical digests; stat fields and the checksum are placeholders. The helper checks framing/extent bounds, follows regular-file symlinks, reads every positive body through a 64 KiB scratch buffer and compares SHA-256. It additionally compares file-descriptor/path identity, size, mode, mtime and ctime before/after reading. Nonregular inputs are rejected before a potentially blocking read. Existing outer native receipt/stability guards remain.

This is a trusted in-process ABI, not a new authenticated wire protocol. Callers supply valid pointer extents and discard partial outputs on failure; template checksum placeholders are intentional. The independent reference/native checker still owns query/condition semantics. The helper retains no request state, frees its EVP context and closes files on all handled returns. Shared runtime/crypto initialization is warm; no total process-RSS or cold-first-call claim is made.

Limits are 8 MiB input/output, 65,536 rows, 4,096 path bytes and 64 MiB per physical file. The file cap and regular-file admission narrow the optional native mode; unsupported inputs fail rather than silently skip verification. The Python control remains available. Retained namespace/fragment limits and existing worker/result-cache limitations from the [prior report](../retained-conditions/REPORT.md) continue to apply.

## Correctness and reproduction

All [181 tests](correctness-tests.txt) pass with the optional native providers enabled. The new 46 tests extend both retained differential and native invalidation suites across both modes, plus malformed/truncated framing, capacity/count/identity failures, empty/chunked files, Unicode, permissions, pre-epoch timestamps, symlinks, changed/missing backing and directories. Existing mutation-during-build tests verify outer receipt stability. They are not an exhaustive adversarial race model.

All 210 main builds and nine [boundary builds](boundary/summary.json) pass: 219 libraries and 6,789 object checks against independent CLI references, runtime probes and expected work counts. High-fanout edits recompile 26 objects; flags and clean builds compile 31. Clean resets producer state and reconstructs plans. Boundary single observations establish correctness, not speed rankings. See [boundary validation](boundary/validation.json).

Build using [build_condition_verifier.py](../../build_condition_verifier.py), then follow the [reproduction instructions](../../README.md#batched-odin-condition-verification). The [build record](build.json) pins source, library, crypto and Odin version. The native compiler/checker binaries themselves are unchanged; only the optional shared verifier and caller are new. Raw `results.json` and `boundary/results.json` are ignored local evidence registered in the [manifest](../../../../research/evidence.json); raw runs retain frozen sources, tool/library hashes and observations.

The next generic representation experiment is sharing an explicitly admitted immutable collection and edit overlay between compiler and validator, charging admission/update costs. That could remove redundant loose-file accesses; native emission alone cannot remove the remaining read/hash/metadata work safely.
