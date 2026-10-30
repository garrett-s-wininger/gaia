# Dependency-bundle experiment results

Run: 20261028T212433.570836Z

Controlled synthetic pure-Python fixtures; no dependency downloads. Fresh process per trial, reused/warm filesystem cache. These results describe the recorded execution environment, not a verified physical developer-laptop baseline.

Interpreter: `3.14.8 (main, Oct  2 2026, 10:23:31) [GCC 16.2.1 20260810]`. Trials: 15 per case after 1 warmup(s). Case order is deterministically shuffled within each repetition. Shared-reader cases use the same ZIP bytes as stock cases, with a path hook that retains one resource archive handle; module loading remains standard. Persistent cases keep one archive/index for BOTH modules and resources, discover names without loading code and read each module once. Access cases use a common reader/resource interface with ZipFile, indexed positional reads, mmap or resident bytes over the same stored container; header/range validation is paid at index creation for direct readers and CRC remains checked on every read. Loader integration returns copied bytes in every backend, without changing compilation.

## Load timing

Medians in milliseconds; parent-observed process wall includes interpreter/setup/validation. Workload timing covers imports + resource reads + a small application loop. All modules/resources/origins/output and missing-input behavior are checked. Peak RSS uses executed-address-space VmHWM; if a separate memory pass is present it is one additional untraced process per case, not a timing-sample median.

| Leaf modules | Inputs | Layout | Import ms | Resource ms | App ms | Workload ms | Process ms | Process p95 ms | Peak RSS MiB |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2048 | source | directory | 248.57 | 2.26 | 10.41 | 261.38 | 356.47 | 419.48 | 27.29 |
| 2048 | source | persistent-stored | 178.38 | 6.38 | 10.18 | 194.68 | 306.48 | 367.57 | 30.31 |
| 2048 | source | access-zipfile | 191.30 | 1.73 | 9.72 | 201.83 | 310.83 | 373.66 | 30.21 |
| 2048 | source | access-pread | 162.57 | 1.28 | 9.38 | 174.32 | 285.12 | 348.38 | 30.57 |
| 2048 | source | access-mmap | 155.46 | 1.19 | 9.38 | 165.86 | 281.29 | 310.87 | 30.96 |
| 2048 | source | access-resident | 154.92 | 1.19 | 9.42 | 164.70 | 271.43 | 338.64 | 31.08 |
| 2048 | bytecode | directory | 107.24 | 2.20 | 8.96 | 118.26 | 215.50 | 290.04 | 26.94 |
| 2048 | bytecode | persistent-stored | 84.94 | 5.68 | 9.24 | 98.38 | 207.02 | 228.13 | 29.84 |
| 2048 | bytecode | access-zipfile | 101.92 | 1.84 | 9.41 | 113.89 | 225.83 | 307.74 | 29.74 |
| 2048 | bytecode | access-pread | 89.26 | 1.18 | 8.79 | 99.74 | 208.90 | 225.04 | 30.16 |
| 2048 | bytecode | access-mmap | 74.50 | 1.17 | 8.47 | 85.55 | 192.57 | 213.89 | 31.25 |
| 2048 | bytecode | access-resident | 75.56 | 1.13 | 8.64 | 86.38 | 194.07 | 206.16 | 31.32 |

## Preparation and storage

Packing and compatibility export are single observed runs, not trial medians. Pack/export correctness validation is outside their reported timings. Directory allocation includes directory blocks; ZIP allocation counts its container. Values depend on this filesystem. Bytecode input construction is separate.

| Leaf modules | Inputs | Layout | Files | Logical KiB | Allocated KiB | Pack ms | Export ms | One-shot pack + process ms |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2048 | source | directory | 2104 | 419.53 | 8500.00 | 0.00 | — | 356.47 |
| 2048 | source | persistent-stored | 1 | 727.38 | 728.00 | 158.27 | 452.54 | 464.75 |
| 2048 | source | access-zipfile | 1 | 727.38 | 728.00 | 158.27 | 452.54 | 469.10 |
| 2048 | source | access-pread | 1 | 727.38 | 728.00 | 158.27 | 452.54 | 443.39 |
| 2048 | source | access-mmap | 1 | 727.38 | 728.00 | 158.27 | 452.54 | 439.56 |
| 2048 | source | access-resident | 1 | 727.38 | 728.00 | 158.27 | 452.54 | 429.70 |
| 2048 | bytecode | directory | 2104 | 1081.48 | 8500.00 | 0.00 | — | 215.50 |
| 2048 | bytecode | persistent-stored | 1 | 1393.38 | 1396.00 | 137.47 | 428.09 | 344.49 |
| 2048 | bytecode | access-zipfile | 1 | 1393.38 | 1396.00 | 137.47 | 428.09 | 363.30 |
| 2048 | bytecode | access-pread | 1 | 1393.38 | 1396.00 | 137.47 | 428.09 | 346.36 |
| 2048 | bytecode | access-mmap | 1 | 1393.38 | 1396.00 | 137.47 | 428.09 | 330.04 |
| 2048 | bytecode | access-resident | 1 | 1393.38 | 1396.00 | 137.47 | 428.09 | 331.54 |

Source generation and bytecode compilation costs are recorded in `results.json`. One-shot above starts from already prepared mode-specific directory inputs, not from dependency resolution. Compatibility use additionally pays the listed export cost. These columns are pack + process, not complete validation-inclusive preparation or registry-install benchmarks.

## Filesystem activity

Separate strace runs count calls only between worker markers, excluding interpreter setup and correctness validation. Counts cover all activity in that workload, including lazy stdlib loading; they are not dependency-only path attribution. Read bytes are returned syscall bytes, not physical disk traffic or unique file content. Traced timings are excluded from timing statistics.

No syscall observations are attached to this timing run. The access-only experiment reports separately scoped index/read-loop counts where collected. The generated trace plan can be used to add observations without changing timing samples.

## Interpretation limits

- Synthetic import-heavy packages are not evidence of a real ecosystem-wide speedup.
- A fresh interpreter resets module caches, not filesystem caches. Cold storage was not controlled.
- Source-only and precompiled-input results must not be conflated. ZIP cannot generate its own bytecode cache.
- Fewer metadata calls may coexist with more archive reads/seeks or higher CPU/memory.
- Single-run preparation/export costs, compression policy, cache warming and process noise limit precision.
- Shared-resource and persistent-provider hooks are experimental Python code, not a new native loader or bundle format.
- mmap/resident access can avoid per-entry read syscalls but still pays setup, copying/CRC and page-fault costs. This is not a native hardware floor.
- A programmatic compiler integration and a pinned real-package follow-up remain untested.
