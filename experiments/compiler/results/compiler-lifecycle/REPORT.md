# Compiler process lifetime and phase attribution

Run `20261029T210117.876902Z`; **complete**; seven randomized blocks, four complete zlib builds per observation.

Fresh4 launches four processes; repeat4 launches once and performs four independent complete builds. Each iteration admits requests, starts/joins workers, creates/disposes compiler state and objects, and links again. No completed-object or AST reuse. This is an in-process batch, not a daemon/IPC protocol. Same executable and immutable inputs for all controls.

| Mode | Per-build process ms | CPU per build ms | Launch → main ms per launch | After main ms per exit |
| --- | ---: | ---: | ---: | ---: |
| file-fresh4 | 506.816 | 2461.727 | 22.698 | 10.233 |
| file-repeat4 | 472.111 | 2324.393 | 24.700 | 12.720 |
| direct-fresh4 | 502.826 | 2362.274 | 24.262 | 10.125 |
| direct-repeat4 | 466.460 | 2285.947 | 23.712 | 9.626 |

| Paired change | Median per-build delta ms | Wins |
| --- | ---: | ---: |
| file: fresh → repeat | -35.759 | 7/7 |
| direct: fresh → repeat | -36.366 | 6/7 |

Per-build process time is the sum of measured subprocess intervals divided by four; parent artifact verification between fresh processes is excluded. Group wall time including those checks is retained separately. Launch-to-main includes process creation, loader/runtime initialization and scheduling; after-main includes reporting/exit/teardown and parent completion observation. These are observed clock boundaries, not exclusively loader/destructor CPU. Child clocks use C++ steady_clock; nonnegative alignment with parent Linux perf_counter is checked.

Every iteration reports 15 fresh compilations and one link. Every captured object identity matches; every process output library matches. File-mode objects are verified after each process (only the final iteration of repeat4 is externally inspectable). Direct mode creates no object files. Warmups and timed runs use normal cleanup. Phase profiles are separate instrumented runs and never included in these latency observations.

## Separate instrumented compiler phases

| Workers | Sum job spans ms | Frontend ms | Backend ms | Optimizer ms | CodeGenPasses ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 1777.626 | 328.427 | 1397.937 | 779.585 | 596.989 |
| 8 | 2607.149 | 608.946 | 1899.783 | 1128.092 | 744.696 |

These are sums of trace event durations across jobs, not CPU-time samples. Eight-worker spans overlap and include descheduling. Backend contains optimizer/codegen subphases; those columns must not be added together. Trace instrumentation adds overhead and is never used to infer whole-build speedups. Full traces and all event totals are retained.
