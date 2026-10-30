# Dependency-bundle experiment results

Run: 20261028T205055.233700Z

Controlled synthetic pure-Python fixtures; no dependency downloads. Fresh process per trial, reused/warm filesystem cache. These results describe the recorded execution environment, not a verified physical developer-laptop baseline.

Interpreter: `3.14.8 (main, Oct  2 2026, 10:23:31) [GCC 16.2.1 20260810]`. Trials: 15 per case after 1 warmup(s). Case order is deterministically shuffled within each repetition. Shared-reader cases use the same ZIP bytes as stock cases, with a path hook that retains one resource archive handle; module loading remains standard. Persistent cases keep one archive/index for BOTH modules and resources, discover names without loading code and read each module once.

## Load timing

Medians in milliseconds; parent-observed process wall includes interpreter/setup/validation. Workload timing covers imports + resource reads + a small application loop. All modules/resources/origins/output and missing-input behavior are checked. Peak RSS uses executed-address-space VmHWM; if a separate memory pass is present it is one additional untraced process per case, not a timing-sample median.

| Leaf modules | Inputs | Layout | Import ms | Resource ms | App ms | Workload ms | Process ms | Process p95 ms | Peak RSS MiB |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2048 | source | directory | 236.23 | 2.13 | 10.12 | 248.12 | 345.47 | 368.30 | 27.10 |
| 2048 | source | stored | 348.07 | 291.53 | 10.04 | 651.91 | 750.23 | 815.92 | 28.82 |
| 2048 | source | deflated | 386.58 | 288.60 | 9.78 | 689.49 | 789.20 | 855.15 | 28.79 |
| 2048 | source | shared-stored | 348.16 | 12.74 | 9.72 | 376.45 | 476.71 | 511.23 | 28.65 |
| 2048 | source | shared-deflated | 364.12 | 11.64 | 10.06 | 387.81 | 485.17 | 573.02 | 28.65 |
| 2048 | source | persistent-stored | 175.51 | 5.44 | 9.05 | 189.60 | 298.23 | 338.60 | 30.15 |
| 2048 | source | persistent-deflated | 188.56 | 5.56 | 9.36 | 203.74 | 300.36 | 377.67 | 30.12 |
| 2048 | bytecode | directory | 107.39 | 2.10 | 8.75 | 118.92 | 211.06 | 239.45 | 26.76 |
| 2048 | bytecode | stored | 164.85 | 290.12 | 8.75 | 470.96 | 576.96 | 614.23 | 28.63 |
| 2048 | bytecode | deflated | 180.86 | 287.50 | 9.94 | 481.58 | 579.25 | 643.96 | 28.68 |
| 2048 | bytecode | shared-stored | 162.72 | 12.15 | 8.87 | 185.69 | 282.52 | 311.35 | 28.54 |
| 2048 | bytecode | shared-deflated | 176.48 | 11.42 | 8.13 | 198.60 | 288.10 | 331.10 | 28.57 |
| 2048 | bytecode | persistent-stored | 78.41 | 5.38 | 9.64 | 95.41 | 199.17 | 228.12 | 29.68 |
| 2048 | bytecode | persistent-deflated | 86.19 | 5.39 | 8.55 | 100.89 | 206.46 | 222.25 | 29.66 |

## Preparation and storage

Packing and compatibility export are single observed runs, not trial medians. Pack/export correctness validation is outside their reported timings. Directory allocation includes directory blocks; ZIP allocation counts its container. Values depend on this filesystem. Bytecode input construction is separate.

| Leaf modules | Inputs | Layout | Files | Logical KiB | Allocated KiB | Pack ms | Export ms | One-shot pack + process ms |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2048 | source | directory | 2104 | 419.53 | 8500.00 | 0.00 | — | 345.47 |
| 2048 | source | stored | 1 | 727.38 | 728.00 | 170.33 | 433.31 | 920.56 |
| 2048 | source | deflated | 1 | 583.09 | 584.00 | 155.84 | 467.18 | 945.04 |
| 2048 | source | shared-stored | 1 | 727.38 | 728.00 | 170.33 | 433.31 | 647.03 |
| 2048 | source | shared-deflated | 1 | 583.09 | 584.00 | 155.84 | 467.18 | 641.01 |
| 2048 | source | persistent-stored | 1 | 727.38 | 728.00 | 170.33 | 433.31 | 468.56 |
| 2048 | source | persistent-deflated | 1 | 583.09 | 584.00 | 155.84 | 467.18 | 456.20 |
| 2048 | bytecode | directory | 2104 | 1081.48 | 8500.00 | 0.00 | — | 211.06 |
| 2048 | bytecode | stored | 1 | 1393.38 | 1396.00 | 113.28 | 428.16 | 690.24 |
| 2048 | bytecode | deflated | 1 | 1048.12 | 1052.00 | 287.99 | 455.64 | 867.25 |
| 2048 | bytecode | shared-stored | 1 | 1393.38 | 1396.00 | 113.28 | 428.16 | 395.80 |
| 2048 | bytecode | shared-deflated | 1 | 1048.12 | 1052.00 | 287.99 | 455.64 | 576.09 |
| 2048 | bytecode | persistent-stored | 1 | 1393.38 | 1396.00 | 113.28 | 428.16 | 312.45 |
| 2048 | bytecode | persistent-deflated | 1 | 1048.12 | 1052.00 | 287.99 | 455.64 | 494.46 |

Source generation and bytecode compilation costs are recorded in `results.json`. One-shot above starts from already prepared mode-specific directory inputs, not from dependency resolution. Compatibility use additionally pays the listed export cost. These columns are pack + process, not complete validation-inclusive preparation or registry-install benchmarks.

## Filesystem activity

Separate strace runs count calls only between worker markers, excluding interpreter setup and correctness validation. Counts cover all activity in that workload, including lazy stdlib loading; they are not dependency-only path attribution. Read bytes are returned syscall bytes, not physical disk traffic or unique file content. Traced timings are excluded from timing statistics.

| Leaf modules | Inputs | Layout | Metadata calls | Opens | Reads | Read KiB | Counted calls |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 2048 | source | directory | 8469 | 4207 | 4228 | 465.47 | 21168 |
| 2048 | source | stored | 4264 | 4189 | 4332 | 540307.71 | 25607 |
| 2048 | source | deflated | 4264 | 4189 | 4332 | 540307.71 | 25607 |
| 2048 | source | shared-stored | 4213 | 4150 | 4168 | 531920.36 | 25095 |
| 2048 | source | shared-deflated | 4213 | 4150 | 4168 | 531920.36 | 25095 |
| 2048 | source | persistent-stored | 11 | 5 | 25 | 1893.89 | 6382 |
| 2048 | source | persistent-deflated | 11 | 5 | 24 | 1765.89 | 6381 |
| 2048 | bytecode | directory | 6417 | 2135 | 4228 | 1127.42 | 17043 |
| 2048 | bytecode | stored | 4264 | 4189 | 4332 | 540374.49 | 25607 |
| 2048 | bytecode | deflated | 4264 | 4189 | 4332 | 540374.49 | 25607 |
| 2048 | bytecode | shared-stored | 4213 | 4150 | 4176 | 532948.40 | 25111 |
| 2048 | bytecode | shared-deflated | 4213 | 4150 | 4172 | 532436.40 | 25103 |
| 2048 | bytecode | persistent-stored | 11 | 5 | 38 | 3559.91 | 6403 |
| 2048 | bytecode | persistent-deflated | 11 | 5 | 31 | 2663.91 | 6392 |

## Interpretation limits

- Synthetic import-heavy packages are not evidence of a real ecosystem-wide speedup.
- A fresh interpreter resets module caches, not filesystem caches. Cold storage was not controlled.
- Source-only and precompiled-input results must not be conflated. ZIP cannot generate its own bytecode cache.
- Fewer metadata calls may coexist with more archive reads/seeks or higher CPU/memory.
- Single-run preparation/export costs, compression policy, cache warming and process noise limit precision.
- Shared-resource and persistent-provider hooks are experimental Python code, not a new native loader or bundle format.
- A programmatic compiler integration and a pinned real-package follow-up remain untested.
