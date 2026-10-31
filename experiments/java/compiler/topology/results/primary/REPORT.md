# Sharing a compiler JVM improves throughput; memory savings are mixed

One JVM with private compiler workers beats the same foreground worker count spread across JVMs on this pinned Picocli workload. At four slots, the eight-target late batch falls from **1.391 to 0.794 seconds**; at eight slots, **1.985 to 0.939 seconds**. All three paired blocks improve at two, four and eight slots, for both first and late batches. Four slots in one JVM give the best primary median; adding workers is not automatically faster.

There is **no general memory win** in this short run. Four workers in one JVM use more endpoint PSS than four separate JVMs in two of three blocks. Aggregate RSS alone would overcount shared pages across processes; PSS and private memory remain separate. These are endpoint observations, not memory quotas or exact peaks.

| Slots | JVMs | Startup ms | First 8-target batch s | Late batch s | After-late PSS MiB | Private MiB | Java heap used / committed MiB |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 96 | 4.167 | 1.733 | 684 | 683 | 420 / 498 |
| 2 | 1 | 109 | 3.151 | 1.078 | 1029 | 1022 | 502 / 834 |
| 2 | 2 | 102 | 3.961 | 1.438 | 1187 | 1150 | 674 / 899 |
| 4 | 1 | 98 | 2.895 | 0.794 | 1570 | 1563 | 952 / 1376 |
| 4 | 4 | 132 | 4.484 | 1.391 | 1479 | 1442 | 649 / 1068 |
| 8 | 1 | 95 | 2.925 | 0.939 | 1857 | 1850 | 926 / 1662 |
| 8 | 8 | 205 | 6.448 | 1.985 | 1895 | 1858 | 671 / 1180 |

Values are medians across three independently launched, shuffled blocks. Each case has first, excluded warmup and two late batches. For the late column, first take the median of the two batches within each case, then the median across three cases. The two late batches are not evidence of convergence. PSS comparison is paired within block: one JVM is lower in 3/3 blocks at two slots, **1/3 at four**, and 3/3 at eight. The [longer memory trace](../long-memory/REPORT.md) keeps sampling and requested GC separate.

## What the comparison holds fixed

Every batch recompiles eight complete targets from three Picocli Java source files each, alternating original 4.7.7 and a public-constant-edited 4.7.7-gaia-probe. There is no compiled-output reuse. Both variants emit 227 classes per target, matched byte-for-byte by a deterministic SHA-256 aggregate against independent CLI compilations. The final eight outputs are consumed through fresh class loaders: argument parsing must return 7 and versions must match the current variant. Each worker owns its compiler, file manager and diagnostics; immutable runtime/compiler implementation can be shared within a JVM.

All processes inherit the same eight-CPU affinity set and share a 3,072 MiB maximum Java heap budget. Each JVM gets Xmx3072/J MiB, G1, ActiveProcessorCount8/J, and forced default CDS sharing. Aggregate initial heap is 64 MiB. `-XX:-UsePerfData` applies equally to all groups. ActiveProcessorCount is an ergonomic input, not a disjoint CPU pin or a hard thread cap. GC/JIT ergonomics, per-JVM heap sizes and queue/source-cache locality change with topology and are part of this comparison. A heap cap is not an RSS limit.

The batch clock includes target dispatch, compilation, class-byte copying, digest calculation, replies and controller JSON parsing. Startup and normal shutdown are retained separately; class-loader consumers and command-boundary memory probes occur outside batch clocks. `whole_session_seconds` includes those probes and consumer checks. Setup/CLI reference creation is outside a newly launched pool's request clock and is recorded in provenance. No claim is made that runtime acquisition or harness construction is free.

## Correctness and evidence

Run `20261031T050038.762680Z` completes 21 sessions and 84 batches including warmups: **672 target compilations, 152,544 class outputs and 168 actual-byte consumer checks**, with normal shutdowns. A separate [five-test regression run](correctness-tests.txt) covers invalid/missing outputs and memory fields plus real worker failure/drain/retry, same-path/mtime-preserving source edits against a fresh CLI oracle, requested-GC output retention and restoration. The selected application jar, target compiler/modules, runtime image java/modules/libjvm/CDS and listed source files are pinned before execution and rehashed afterwards. Four measured controller/harness sources are frozen and match publication. This protects the listed admitted inputs and outputs, not every OS library or possible runtime input.

[Compact observations and paired blocks](summary.json), [validation](validation.json), [portable provenance](provenance.json). Full raw observations remain ignored local evidence; their byte count and SHA-256 are pinned in provenance. The [earlier incomplete run](../failed-perfdata/REPORT.md) is excluded from all statistics.

## Interpretation and next work

A shared JVM avoids repeated compiler/JIT/runtime work, while private worker state still scales with concurrency. This experiment supports a bounded multi-worker compiler service. It does not establish annotation-processor safety, arbitrary source-graph partitioning, long-lived memory bounds, cancellation or isolation for untrusted tasks. Next compare capacity under a real aggregate RSS/PSS constraint and a longer workload with mixed targets; do not infer lower memory merely from shared runtime code.

Use the [driver instructions](../../README.md) to reproduce. `python3 -B experiments/java/compiler/topology/publish_topology.py` validates completed local raw runs and regenerates compact summaries. The [long trace](../long-memory/REPORT.md) shows why heap-used counters do not substitute for observed process memory.
