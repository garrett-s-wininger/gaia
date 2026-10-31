# What should follow the first JVM compiler proof

## Measure varied complete targets and service lifetimes

Extend the existing full CLI and two-target controls to projects with more sources, dependencies, modules and different target SDKs. Count startup, first requests, every actual compilation, publication and normal shutdown. Measure CPU time and peak/idle/proportional memory before claiming efficiency; the current proof captures wall time and sampled RSS only. Test longer sequences, source removal, classpath changes and quota pressure.

Keep complete Java compilation targets as the queue unit until dependency/SCC grouping or a genuine incremental compiler provides a stronger contract. A file compiled against old binaries can emit stale constants or wrong source API bindings. Source content, SDK, module graph, processors and options all belong in input identity.

## Separate framework preparation from compiled-result caching

The trained cache accelerates the compiler JVM; it does not replace executing a new compilation task. Compare declared compiler-only class knowledge, constrained training and longer profiles on a fresh-process basis. Record artifact sizes and generation costs. Retain matching default CDS archives for image/CLI controls so a disabled baseline does not create a false gain.

## Make direct data access useful to a real consumer

The memory file manager and fresh class-loader consumer establish a delivery path without loose class files. Measure one complete compile-and-consume clock next, including name mapping, ownership/borrowing, verification and consumer lifetime. The current tables stop at validated class delivery and time consumer checks separately.

A JavaFileManager backed by admitted source/dependency collections is a concrete future integration with the artifact/input research. Preserve package/module/resource lookup and failed lookup semantics. A compact compiler runtime is separate from target SDK contents; count both acquisition and admission.

## Establish managed worker guarantees

Each worker owns mutable compiler/file-manager state and reuses it sequentially. Before treating this as a product service, define cancellation, diagnostic forwarding, task failure recovery, processor/plugin execution, long-lived classpath admission, shutdown and memory limits. The current heap cap and short RSS observations are not a service-wide bound. Processor execution is explicitly disabled in the first fixture.

Read the [findings](findings.md) and [complete report](../../../experiments/java/compiler/results/initial/REPORT.md) before selecting a next optimization.
