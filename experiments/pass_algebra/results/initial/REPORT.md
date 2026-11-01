# Three formulations of SSA value liveness

These are measurements of an analysis pass on real Zstandard/zlib LLVM IR, not a complete compiler or development-session speedup. All formulations produce the same block-by-value live-in relation. Values below are milliseconds per module pass, medians of shuffled blocks.

| Input | Functions / blocks | Worklist kernel | Boolean sweeps kernel | Per-value kernel | Worklist full pass | Sweeps full pass | Per-value full pass |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| zstd-common-O1 | 6 / 6 | 0.0001 | 0.0001 | 0.0001 | 0.0160 | 0.0205 | 0.0216 |
| zstd-lazy-O1 | 89 / 5319 | 0.3620 | 1.9224 | 0.8325 | 409.1427 | 410.7841 | 400.0016 |
| zlib-deflate-O1 | 26 / 653 | 0.0208 | 0.1275 | 0.0403 | 43.8347 | 44.5624 | 44.3937 |

The full pass starts with an already parsed LLVM module. It extracts facts, constructs each formulation's layout and scratch space, solves liveness, consumes the complete output through a checksum, and destroys request state. IR parsing/verification and source-to-IR compilation are separate preparation measurements. The prepared kernel includes output reset and solving with caller-owned retained buffers; it excludes layout and full-output hashing.

All three kernels are native Odin compiled with the same flags. The ordinary row loops may auto-vectorize. The full-sweep formulation is an exact Boolean operation; no floating-point approximation or GPU/NPU execution is involved. Repeated timing batches amortize clock noise and do not establish a natural cache-reuse workload.

[Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), [reproduction and mathematical contract](../../README.md). Full observations remain in ignored `results.json`.
