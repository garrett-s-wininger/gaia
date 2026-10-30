# Zstandard object-buffer handoff

Run `20261029T205610.494160Z`; **complete**; 7 randomized blocks; warm cache.

Zstandard 1.5.7, upstream dynamic-library C sources, legacy support off and upstream ZSTD_NO_ASM=1. Upstream release -O3 flags are retained; debug adds -g. This is the library target, not the entire Zstd repository. All controls share compile flags, ordered objects and single-threaded LLD. Native file/direct use the same binary. Fresh process per complete build, normal teardown. The CLI control uses a generated makefile containing the same admitted compile commands and external LLD; it is not a measurement of upstream makefile configuration overhead.

| Configuration | Whole build ms | CPU ms | Compile wall ms | LLD ms | Object MiB | Peak RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| release-cli | 5065.24 | 22896.88 | — | — | 0.874 | — |
| release-file | 4960.26 | 21362.52 | 4914.21 | 6.24 | 0.874 | 211.88 |
| release-direct | 4919.88 | 21135.70 | 4848.32 | 6.26 | 0.874 | 212.07 |
| debug-cli | 6906.12 | 31232.70 | — | — | 3.738 | — |
| debug-file | 6620.02 | 29686.25 | 6557.83 | 14.72 | 3.738 | 318.79 |
| debug-direct | 6738.58 | 29702.22 | 6652.49 | 15.01 | 3.738 | 333.95 |

| Paired comparison | Median delta ms | Wins |
| --- | ---: | ---: |
| release: file → direct | -4.18 | 4/7 |
| release: cli → file | -57.33 | 4/7 |
| release: cli → direct | -114.49 | 4/7 |
| debug: file → direct | -22.35 | 4/7 |
| debug: cli → file | -207.06 | 5/7 |
| debug: cli → direct | -162.53 | 4/7 |

Direct mode must record one borrowed buffer hit per TU, zero missing-object lookups and zero object files. Every timed object SHA-256 and shared ELF must match the matching CLI warmup. Direct object hashing occurs inside the child after its native workload clock and remains in whole-process time; file hashes are checked after timing. No output cache, PCH or compiler option changes between modes. Native peak RSS includes loaded toolchain and retained object buffers, and is not an aggregate process-tree measure for CLI.

Before timings, upstream simple and streaming compression/decompression examples exercise each library on empty, small and 1 MiB deterministic data; round-trip bytes must match. Loader resolution is checked against the measured library. This is a focused public-API check, not the full upstream fuzzer/test suite. Source pins and host identity are checked. Prior zlib diagnostic/failure tests cover this same native adapter; this run does not extend crash isolation guarantees.
