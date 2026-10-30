# Cost-aware compiler dispatch

Run `20261029T232949.779224Z`; **complete**; 7 randomized blocks, fresh processes, warm cache.

Same Zstandard 1.5.7 release/debug library requests, compiler flags and fixed ordered linker input as the preceding experiment. Eight Odin workers dispatch either FIFO or descending predicted cost; ties retain original job order. Predictions are frozen medians of per-job elapsed spans from seven earlier, unprofiled, file-handoff builds per configuration. They are historical scheduling hints, not intrinsic CPU costs or estimates learned from test outcomes. Both policies read and validate the same cost table. Native controls use one identical binary.

| Mode | Whole build ms | CPU ms | Compile wall ms | Predicted longest start ms | Final one-job tail ms | Peak RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| release-file-fifo | 4680.26 | 20511.56 | 4630.40 | 263.83 | 1854.53 | 211.51 |
| release-file-cost | 4511.06 | 20841.70 | 4464.56 | 0.00 | 2077.19 | 213.66 |
| release-direct-fifo | 4688.96 | 20199.39 | 4633.37 | 255.71 | 1894.79 | 213.18 |
| release-direct-cost | 4442.99 | 20653.14 | 4391.64 | 0.00 | 2049.37 | 213.67 |
| debug-file-fifo | 6323.69 | 28224.92 | 6262.47 | 335.09 | 2561.02 | 319.74 |
| debug-file-cost | 6180.76 | 28866.93 | 6121.93 | 0.00 | 2863.34 | 332.18 |
| debug-direct-fifo | 6347.38 | 27868.71 | 6251.00 | 320.63 | 2574.60 | 345.32 |
| debug-direct-cost | 6172.07 | 28679.29 | 6086.89 | 0.00 | 2817.22 | 332.79 |

| Paired FIFO → cost | Median wall delta ms | Wins |
| --- | ---: | ---: |
| release-file | -164.94 | 5/7 |
| release-direct | -190.25 | 6/7 |
| debug-file | -165.37 | 6/7 |
| debug-direct | -220.84 | 6/7 |

Prediction/training cost is outside consumer timing: this run reuses already measured historical spans. A first build has no such history; all-zero estimates retain FIFO. There is no claim that stale costs generalize across compiler/configuration/hardware changes. No optimizer flags, AST caches, object-result reuse, request contents or linker order change. The sort runs in Odin over at most 64 admitted jobs; worker concurrency remains bounded to eight.

Longest start is the predicted-longest job start relative to the first job start. Final one-job tail is the gap between the last two job completions. These are logical-job spans, not CPU utilization. Eight active jobs can contend for cores and memory; earlier dispatch does not imply equal wall-time savings. Complete process time includes normal teardown and, for direct mode, captured-object validation hashes after the native workload clock. File hashes are checked outside timing. Compare policies within the same handoff mode.

Every object identity and final shared ELF must match the prior CLI reference. Direct requires 30 buffer hits, zero misses and no object files. Every mode warmup exercises the upstream simple/streaming examples with six byte-exact round trips and checks dynamic loader resolution. Malformed cost records fail before compiler dispatch; existing outputs must remain intact. Ordinary compiler/linker failure behavior is inherited from the validated handoff adapter. This is one independent target batch, not a general build-DAG scheduler or persistent service.
