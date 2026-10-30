# Bounded compiler queue and in-process ELF linking

Run `20261029T201012.673471Z`; **complete**. 15 randomized blocks; warm cache; fresh process per build.

Same admitted zlib source/configuration/system headers as the real-project run. This comparison produces a real shared ELF library, not the previous static archive. All controls use the same Clang and LLD versions/options, fixed object order and single-threaded linker. Make controls compile the 15 object targets and invoke external LLD; pool controls use a fixed Odin worker set draining at most 64 admitted jobs, then join all workers before one serialized link. Object files remain file-backed and are read by LLD.

| Mode | Complete build ms | Range ms | Aggregate child CPU ms | Native compile wall ms | Link stage ms | Native peak RSS MiB |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| make-1 | 2310.416 | 2154.5–2471.7 | 2293.338 | — | 24.457 | — |
| make-8 | 531.190 | 498.1–626.0 | 2947.525 | — | 25.530 | — |
| memory-1-internal | 1656.225 | 1547.7–1756.2 | 1654.834 | 1616.043 | 4.206 | 118.15 |
| memory-2-internal | 923.305 | 873.7–1024.9 | 1764.167 | 880.741 | 4.154 | 121.83 |
| memory-4-internal | 574.449 | 532.1–625.7 | 1995.254 | 534.728 | 4.281 | 126.34 |
| memory-8-internal | 498.292 | 455.0–611.1 | 2359.422 | 451.780 | 4.129 | 131.91 |
| memory-8-external | 515.349 | 469.1–581.1 | 2315.718 | 448.277 | 25.506 | 131.96 |
| physical-8-internal | 483.890 | 456.4–564.4 | 2338.845 | 446.754 | 4.231 | 134.02 |

## Paired complete-build comparisons

| Comparison | Median change ms | Wins / blocks |
| --- | ---: | ---: |
| make-8 → memory-1-internal | +1110.864 | 0/15 |
| make-8 → memory-2-internal | +389.429 | 0/15 |
| make-8 → memory-4-internal | +46.348 | 5/15 |
| make-8 → memory-8-internal | -31.566 | 10/15 |
| memory-8-external → memory-8-internal | -28.034 | 10/15 |
| physical-8-internal → memory-8-internal | +13.749 | 6/15 |

Link stage means the embedded LLD call (including context cleanup) or the complete external linker process, including startup/exit. These are intentionally different process boundaries; whole-build time remains decisive. Native peak RSS is the single multithreaded process VmHWM, including compiler/linker libraries. Make/child-process aggregate peak memory is not available here, so no memory comparison with make is implied. Worker counts bound concurrent frontend instances, not compiler memory in bytes. Native job intervals and peak active job count are retained. Each worker has private VFS metadata/current directory; every request has private compiler, LLVMContext and diagnostics. Only immutable payload bytes/argument vectors share. No PCH, AST/result cache, output-memory shortcut or successful fast exit is used.

A compile error stops new dispatch, drains/joins active workers and suppresses linking. The final link uses declared object order, not completion order. LLD is never invoked concurrently, and canRunAgain is checked. An unrecoverable linker context retires the process. Ordinary linker failure/reuse and compile-error publication suppression are tested separately. This is one finite target batch, not a persistent daemon or general build DAG/service protocol.
