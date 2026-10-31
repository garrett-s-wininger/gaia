# What managed Java compilation buys us

Retaining initialized compiler processes improves repeated compilation. Native Image also makes the first real compilation cheaper, but the JVM performs better in the longer compiler-body trace. Collector choice, JIT warm-up and retained memory need separate measurements.

All studies compile complete Picocli source targets rather than splitting mutually dependent files against old binaries. A public-constant edit must update dependent class files. Annotation processing is disabled; arbitrary plugins and larger projects remain untested.

## First use and repeated compilation favor different choices

The execution-variants study uses one instrumented endpoint, the same target SDK representation and independent bytecode references. Its compiler timer includes task creation, source/type loading, analysis, generation and file-manager flush. Delivery and hashing are separate.

| Operation | Native Image O2 / Serial | Leyden EA2 compiled-method cache |
| --- | ---: | ---: |
| Fresh complete process | 346 ms | 873 ms |
| First actual compilation | 307 ms | 737 ms |
| Later compilation, primary twelve-request window | 288 ms | 275 ms |
| Last eight compilations of a separate 32-request trace | 281 ms | 255 ms |

The native first-use gain extends beyond process launch. It does not establish better repeated compiler-body throughput. Oracle JDK Parallel GC reaches 206 ms in the longer trace, versus G1's 235 ms. Named compiler threads remain active in all JVM traces; none is declared peak steady state. Compiler implementations differ across distributions, so the within-toolchain controls carry the causal comparison. [Execution report](../../../experiments/java/compiler/results/variants/REPORT.md).

## Collector and tiering changes have workload-dependent costs

The matched Oracle JDK 25 comparison holds heap, CPU affinity, target and output checks fixed. These are its primary late-window values, not the longer trace above.

| Configuration | Fresh complete process | Later compilation |
| --- | ---: | ---: |
| G1, normal tiering | 1,642 ms | 306 ms |
| Parallel GC | 1,468 ms | 267 ms |
| Serial GC | 1,596 ms | 397 ms |
| ZGC | 1,753 ms | 325 ms |
| C1 only, level 1 | 1,238 ms | 406 ms |
| Profiling C1 only, level 3 | 1,735 ms | 810 ms |
| C2 only, tiering disabled | 2,516 ms | 330 ms |

C1-only improves a short-lived command while slowing later compiler work. Profiling without enabling C2 performs poorly here. Disabling tiered compilation selects C2-only behavior; it does not disable C2.

Shenandoah requires a separate same-Graal-binary C2 control because that distribution's default Graal JIT rejects it. It takes 335 ms versus its matched G1 control's 275 ms. These results support bounded configuration choices and further convergence work, not a universal collector ranking.

Native Epsilon also loses its matched two-compilation test: the second compile takes 369 ms versus native Serial's 275 ms, with greater RSS. A growth diagnostic completes four targets before attempt five exhausts the same 768 MiB heap. No heap increase hides the failure. [Flags, CPU attribution and Epsilon evidence](../../../experiments/java/compiler/results/variants/REPORT.md).

## A shared JVM improves batch time without guaranteeing lower memory

The topology study recompiles eight targets per batch with private compiler/file-manager contexts. One JVM and many JVMs share the same foreground worker count, aggregate 3,072 MiB heap cap and eight-CPU affinity set.

| Worker slots | One JVM, late batch | Separate JVMs, late batch |
| --- | ---: | ---: |
| 2 | 1.078 s | 1.438 s |
| 4 | 0.794 s | 1.391 s |
| 8 | 0.939 s | 1.985 s |

All three paired blocks improve at each concurrency. Four slots give the best primary median; more threads are not automatically faster. The initial two-target proof also favored a warm pool over parallel cold CLIs, but used a different timing and lifetime contract.

Memory results are mixed. At four slots, one JVM has higher endpoint PSS in two of three blocks. A longer trace records about 1,706 versus 1,580 MiB before requested GC. Java heap-used/committed counters can fall while PSS remains large; the resident remainder is unresolved. Sequentially read memory totals are not atomic peak measurements. Per-JVM heap splits, GC/JIT ergonomics and queue/cache locality are part of this topology comparison. [Primary report](../../../experiments/java/compiler/topology/results/primary/REPORT.md), [memory trace](../../../experiments/java/compiler/topology/results/long-memory/REPORT.md).

## Preparation and compatibility remain part of the tool

The initial jlink image is 66.7 MiB including default CDS, but its CLI latency is near the full JDK's. It still needs an explicit target SDK. Programmatic memory delivery works: an independent class loader consumes returned bytes without loose class files. Those consumer checks are outside the delivery timer. [Initial report](../../../experiments/java/compiler/results/initial/REPORT.md).

The earlier JDK 25 AOT cache already uses Leyden loading/linking and profiling. The EA2 continuation adds cached compiled methods, with 5,527 entries proven admitted. Its metadata-only cache can be faster later; the compiled-method cache primarily helps first use in this workload.

Native Image needs an SDK adapter because its default runtime resource filesystem cannot expose the full target platform. Public file-manager module locations supply all 77 modules, with readability/export checks. SDK extraction costs 7.31 seconds and 161.1 MiB of class files. The optimized native Serial image costs 75.54 seconds to build and occupies 38.93 MB. These costs are separate from the execution tables.

## Confidence and follow-up

The initial study validates 30 operations. The topology studies validate 1,056 target compilations and 200 actual-byte consumers. Execution variants validate 51 primary cases, 654 target outputs and 45 deliberate failure/recovery checks, plus 128 convergence compilations. Same-path/size/mtime edits, SDK/module behavior and current target versions have focused checks. Each report retains its own source identities and validation.

Short traces, post-request RSS and Java heap caps do not establish a long-lived memory bound. Read the [prospects](prospects.md) for larger targets, resident-memory attribution, packed SDK access and native code-generation follow-ups.
