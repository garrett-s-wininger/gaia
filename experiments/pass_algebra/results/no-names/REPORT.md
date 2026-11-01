# Three formulations of SSA value liveness

These are measurements of an analysis pass on real Zstandard/zlib LLVM IR, not a complete compiler or development-session speedup. All formulations produce the same block-by-value live-in relation. Values below are milliseconds per module pass, medians of shuffled blocks.

| Input | Functions / blocks | Worklist kernel | Boolean sweeps kernel | Per-value kernel | Worklist full pass | Sweeps full pass | Per-value full pass |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| zstd-common-O1 | 6 / 6 | 0.0001 | 0.0002 | 0.0001 | 0.0078 | 0.0055 | 0.0076 |
| zstd-lazy-O1 | 89 / 5319 | 0.2997 | 1.9872 | 0.8837 | 11.5206 | 12.5606 | 12.6395 |
| zlib-deflate-O1 | 26 / 653 | 0.0196 | 0.1397 | 0.0351 | 0.9266 | 1.0361 | 0.9672 |

The full pass starts with an already parsed LLVM module. It extracts facts, constructs each formulation's layout and scratch space, solves liveness, consumes the complete output through a checksum, and destroys request state. IR parsing/verification and source-to-IR compilation are separate preparation measurements. The prepared kernel includes output reset and solving with caller-owned retained buffers; it excludes layout and full-output hashing.

All three kernels are native Odin compiled with the same flags. The ordinary row loops may auto-vectorize. The full-sweep formulation is an exact Boolean operation; no floating-point approximation or GPU/NPU execution is involved. Repeated timing batches amortize clock noise and do not establish a natural cache-reuse workload.

[Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), [reproduction and mathematical contract](../../README.md). Full observations remain in ignored `results.json`.
