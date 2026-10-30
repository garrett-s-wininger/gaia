# Dependency-bundle experiment results

Run: 20261028T203402.062015Z

Controlled synthetic pure-Python fixtures; no dependency downloads. Fresh process per trial, reused/warm filesystem cache. These results describe the recorded execution environment, not a verified physical developer-laptop baseline.

Interpreter: `3.14.8 (main, Oct  2 2026, 10:23:31) [GCC 16.2.1 20260810]`. Trials: 15 per case after 1 warmup(s). Case order is deterministically shuffled within each repetition. Shared-reader cases use the same ZIP bytes as stock cases, with a path hook that retains one resource archive handle; module loading remains standard.

## Load timing

Medians in milliseconds; parent-observed process wall includes interpreter/setup/validation. Workload timing covers imports + resource reads + a small application loop. All modules/resources/origins/output and missing-input behavior are checked. Peak RSS uses executed-address-space VmHWM; if a separate memory pass is present it is one additional untraced process per case, not a timing-sample median.

| Leaf modules | Inputs | Layout | Import ms | Resource ms | App ms | Workload ms | Process ms | Process p95 ms | Peak RSS MiB |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 64 | source | directory | 11.63 | 1.91 | 0.22 | 14.14 | 90.01 | 116.61 | 21.21 |
| 64 | source | stored | 13.98 | 21.40 | 0.26 | 36.20 | 116.51 | 142.59 | 21.50 |
| 64 | source | deflated | 13.69 | 21.41 | 0.27 | 36.80 | 116.25 | 147.49 | 21.35 |
| 64 | source | shared-stored | 15.23 | 2.52 | 0.21 | 18.01 | 96.58 | 115.78 | 21.37 |
| 64 | source | shared-deflated | 13.39 | 2.38 | 0.21 | 15.91 | 91.78 | 114.12 | 21.34 |
| 64 | bytecode | directory | 5.91 | 1.79 | 0.21 | 8.41 | 86.79 | 100.64 | 21.27 |
| 64 | bytecode | stored | 6.84 | 21.21 | 0.24 | 28.60 | 104.39 | 119.54 | 21.44 |
| 64 | bytecode | deflated | 6.71 | 21.95 | 0.25 | 28.69 | 108.93 | 132.52 | 21.41 |
| 64 | bytecode | shared-stored | 7.70 | 2.24 | 0.20 | 9.95 | 84.71 | 101.84 | 21.43 |
| 64 | bytecode | shared-deflated | 7.11 | 2.26 | 0.20 | 9.72 | 82.50 | 106.13 | 21.30 |
| 512 | source | directory | 65.41 | 2.11 | 1.91 | 69.10 | 146.55 | 157.49 | 22.40 |
| 512 | source | stored | 82.14 | 78.15 | 1.99 | 164.25 | 246.51 | 299.28 | 23.03 |
| 512 | source | deflated | 89.85 | 78.70 | 2.12 | 172.57 | 250.50 | 290.11 | 23.03 |
| 512 | source | shared-stored | 89.36 | 4.26 | 1.83 | 96.34 | 176.00 | 216.14 | 23.00 |
| 512 | source | shared-deflated | 95.64 | 4.75 | 1.93 | 103.12 | 178.34 | 193.17 | 22.98 |
| 512 | bytecode | directory | 32.16 | 1.87 | 1.77 | 35.65 | 112.49 | 152.66 | 22.36 |
| 512 | bytecode | stored | 46.98 | 79.87 | 1.95 | 132.10 | 212.06 | 241.99 | 22.99 |
| 512 | bytecode | deflated | 45.64 | 77.39 | 1.88 | 124.29 | 213.30 | 242.18 | 22.94 |
| 512 | bytecode | shared-stored | 46.02 | 4.46 | 1.84 | 53.03 | 130.07 | 159.65 | 22.87 |
| 512 | bytecode | shared-deflated | 47.01 | 4.51 | 1.73 | 53.52 | 130.09 | 161.89 | 22.93 |
| 2048 | source | directory | 241.58 | 2.18 | 10.49 | 256.63 | 357.70 | 405.54 | 26.90 |
| 2048 | source | stored | 354.40 | 296.72 | 9.87 | 672.45 | 774.62 | 812.00 | 28.60 |
| 2048 | source | deflated | 383.04 | 295.68 | 9.88 | 693.69 | 794.30 | 832.88 | 28.51 |
| 2048 | source | shared-stored | 357.27 | 12.28 | 9.90 | 381.46 | 468.68 | 514.84 | 28.55 |
| 2048 | source | shared-deflated | 373.45 | 11.56 | 9.76 | 395.73 | 486.72 | 537.67 | 28.51 |
| 2048 | bytecode | directory | 111.26 | 2.25 | 9.54 | 122.77 | 213.63 | 325.43 | 26.62 |
| 2048 | bytecode | stored | 164.28 | 304.23 | 8.71 | 474.06 | 571.07 | 632.08 | 28.53 |
| 2048 | bytecode | deflated | 186.41 | 296.38 | 8.50 | 492.98 | 591.68 | 690.96 | 28.53 |
| 2048 | bytecode | shared-stored | 171.28 | 12.70 | 9.61 | 197.95 | 289.67 | 316.91 | 28.40 |
| 2048 | bytecode | shared-deflated | 198.43 | 13.02 | 9.45 | 221.01 | 313.26 | 343.15 | 28.38 |

## Preparation and storage

Packing and compatibility export are single observed runs, not trial medians. Pack/export correctness validation is outside their reported timings. Directory allocation includes directory blocks; ZIP allocation counts its container. Values depend on this filesystem. Bytecode input construction is separate.

| Leaf modules | Inputs | Layout | Files | Logical KiB | Allocated KiB | Pack ms | Export ms | One-shot pack + process ms |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 64 | source | directory | 120 | 76.55 | 564.00 | 0.00 | — | 90.01 |
| 64 | source | stored | 1 | 93.78 | 96.00 | 16.03 | 111.01 | 132.54 |
| 64 | source | deflated | 1 | 28.47 | 32.00 | 39.16 | 92.40 | 155.41 |
| 64 | source | shared-stored | 1 | 93.78 | 96.00 | 16.03 | 111.01 | 112.61 |
| 64 | source | shared-deflated | 1 | 28.47 | 32.00 | 39.16 | 92.40 | 130.93 |
| 64 | bytecode | directory | 120 | 101.05 | 564.00 | 0.00 | — | 86.79 |
| 64 | bytecode | stored | 1 | 118.45 | 120.00 | 15.92 | 102.00 | 120.31 |
| 64 | bytecode | deflated | 1 | 45.81 | 48.00 | 32.51 | 94.77 | 141.44 |
| 64 | bytecode | shared-stored | 1 | 118.45 | 120.00 | 15.92 | 102.00 | 100.63 |
| 64 | bytecode | shared-deflated | 1 | 45.81 | 48.00 | 32.51 | 94.77 | 115.00 |
| 512 | source | directory | 568 | 153.48 | 2356.00 | 0.00 | — | 146.55 |
| 512 | source | stored | 1 | 236.33 | 240.00 | 38.65 | 163.40 | 285.16 |
| 512 | source | deflated | 1 | 153.42 | 156.00 | 44.62 | 131.42 | 295.12 |
| 512 | source | shared-stored | 1 | 236.33 | 240.00 | 38.65 | 163.40 | 214.65 |
| 512 | source | shared-deflated | 1 | 153.42 | 156.00 | 44.62 | 131.42 | 222.96 |
| 512 | bytecode | directory | 568 | 321.46 | 2356.00 | 0.00 | — | 112.49 |
| 512 | bytecode | stored | 1 | 405.35 | 408.00 | 36.15 | 151.09 | 248.21 |
| 512 | bytecode | deflated | 1 | 271.45 | 272.00 | 67.15 | 128.36 | 280.46 |
| 512 | bytecode | shared-stored | 1 | 405.35 | 408.00 | 36.15 | 151.09 | 166.22 |
| 512 | bytecode | shared-deflated | 1 | 271.45 | 272.00 | 67.15 | 128.36 | 197.24 |
| 2048 | source | directory | 2104 | 419.53 | 8500.00 | 0.00 | — | 357.70 |
| 2048 | source | stored | 1 | 727.38 | 728.00 | 144.33 | 406.58 | 918.95 |
| 2048 | source | deflated | 1 | 583.09 | 584.00 | 166.85 | 445.90 | 961.15 |
| 2048 | source | shared-stored | 1 | 727.38 | 728.00 | 144.33 | 406.58 | 613.01 |
| 2048 | source | shared-deflated | 1 | 583.09 | 584.00 | 166.85 | 445.90 | 653.57 |
| 2048 | bytecode | directory | 2104 | 1081.48 | 8500.00 | 0.00 | — | 213.63 |
| 2048 | bytecode | stored | 1 | 1393.38 | 1396.00 | 189.30 | 422.81 | 760.37 |
| 2048 | bytecode | deflated | 1 | 1048.12 | 1052.00 | 323.46 | 478.31 | 915.14 |
| 2048 | bytecode | shared-stored | 1 | 1393.38 | 1396.00 | 189.30 | 422.81 | 478.97 |
| 2048 | bytecode | shared-deflated | 1 | 1048.12 | 1052.00 | 323.46 | 478.31 | 636.72 |

Source generation and bytecode compilation costs are recorded in `results.json`. One-shot above starts from already prepared mode-specific directory inputs, not from dependency resolution. Compatibility use additionally pays the listed export cost. These columns are pack + process, not complete validation-inclusive preparation or registry-install benchmarks.

## Filesystem activity

Separate strace runs count calls only between worker markers, excluding interpreter setup and correctness validation. Counts cover all activity in that workload, including lazy stdlib loading; they are not dependency-only path attribution. Read bytes are returned syscall bytes, not physical disk traffic or unique file content. Traced timings are excluded from timing statistics.

| Leaf modules | Inputs | Layout | Metadata calls | Opens | Reads | Read KiB | Counted calls |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 64 | source | directory | 533 | 239 | 260 | 122.50 | 1323 |
| 64 | source | stored | 296 | 221 | 331 | 11713.80 | 1760 |
| 64 | source | deflated | 296 | 221 | 332 | 4440.89 | 1761 |
| 64 | source | shared-stored | 245 | 182 | 192 | 9929.09 | 1267 |
| 64 | source | shared-deflated | 245 | 182 | 193 | 3571.97 | 1268 |
| 64 | bytecode | directory | 465 | 151 | 260 | 147.00 | 1167 |
| 64 | bytecode | stored | 296 | 221 | 331 | 14308.92 | 1760 |
| 64 | bytecode | deflated | 296 | 221 | 332 | 6283.97 | 1761 |
| 64 | bytecode | shared-stored | 245 | 182 | 192 | 12200.80 | 1267 |
| 64 | bytecode | shared-deflated | 245 | 182 | 193 | 5186.61 | 1268 |
| 512 | source | directory | 2325 | 1135 | 1156 | 199.43 | 5805 |
| 512 | source | stored | 1192 | 1117 | 1227 | 124551.26 | 7138 |
| 512 | source | deflated | 1192 | 1117 | 1227 | 108606.43 | 7138 |
| 512 | source | shared-stored | 1141 | 1078 | 1090 | 120066.97 | 6649 |
| 512 | source | shared-deflated | 1141 | 1078 | 1088 | 104393.70 | 6645 |
| 512 | bytecode | directory | 1809 | 599 | 1156 | 367.40 | 4752 |
| 512 | bytecode | stored | 1192 | 1117 | 1227 | 133434.55 | 7138 |
| 512 | bytecode | deflated | 1192 | 1117 | 1227 | 126899.99 | 7138 |
| 512 | bytecode | shared-stored | 1141 | 1078 | 1092 | 128977.04 | 6653 |
| 512 | bytecode | shared-deflated | 1141 | 1078 | 1090 | 122376.71 | 6649 |
| 2048 | source | directory | 8469 | 4207 | 4228 | 465.47 | 21168 |
| 2048 | source | stored | 4264 | 4189 | 4332 | 540307.71 | 25607 |
| 2048 | source | deflated | 4264 | 4189 | 4332 | 540307.71 | 25607 |
| 2048 | source | shared-stored | 4213 | 4150 | 4168 | 531920.36 | 25095 |
| 2048 | source | shared-deflated | 4213 | 4150 | 4168 | 531920.36 | 25095 |
| 2048 | bytecode | directory | 6417 | 2135 | 4228 | 1127.42 | 17043 |
| 2048 | bytecode | stored | 4264 | 4189 | 4332 | 540374.49 | 25607 |
| 2048 | bytecode | deflated | 4264 | 4189 | 4332 | 540374.49 | 25607 |
| 2048 | bytecode | shared-stored | 4213 | 4150 | 4176 | 532948.40 | 25111 |
| 2048 | bytecode | shared-deflated | 4213 | 4150 | 4172 | 532436.40 | 25103 |

## Interpretation limits

- Synthetic import-heavy packages are not evidence of a real ecosystem-wide speedup.
- A fresh interpreter resets module caches, not filesystem caches. Cold storage was not controlled.
- Source-only and precompiled-input results must not be conflated. ZIP cannot generate its own bytecode cache.
- Fewer metadata calls may coexist with more archive reads/seeks or higher CPU/memory.
- Single-run preparation/export costs, compression policy, cache warming and process noise limit precision.
- The shared-reader hook is experimental Python code, not a new native loader or bundle format.
- A programmatic compiler integration and a pinned real-package follow-up remain untested.
