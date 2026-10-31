# What managed Java compilation buys us

On the pinned Picocli project, full CLI compilation takes about 1.49 seconds and a trained compiler AOT cache reduces a fresh API process to 1.13 seconds. The compact jlink CLI is near parity, not a dependable latency improvement by itself. Warm resident API compilation takes 415 ms with class-file delivery or 354 ms for owned memory bytes. All output bytes match an independent CLI reference.

A bounded two-worker pool compiles two independent complete targets in 448 ms versus 619 ms sequentially in one initialized service and 1.97 seconds for two concurrently launched CLIs. Each target jointly compiles all three source units. The second changes a public constant used by another source file, so treating files as independent tasks against an old project JAR would be an invalid generic strategy. Private task/file-manager contexts and whole-target grouping preserve the changed dependent outputs.

The compiler runtime is 66.7 MiB including its compatible default CDS archive; it still reads the same full target SDK through `--system`. Image construction and AOT training cost 2.63 and 2.96 seconds separately. The first resident request remains much slower than warm work. Post-request RSS is roughly 312–444 MiB across warm services, with no peak/RSS quota claim. CPU time was not measured.

A real in-process class loader consumes owned bytes and verifies Picocli parsing and both target versions. Those checks are outside the compile/delivery latency table. Three regressions also verify same-path/mtime-preserving edits, failure recovery, no loose class files for memory delivery and fresh target compilation under the trained cache.

All 30 timed operations pass. This remains one small source graph, three paired blocks and disabled annotation processing; it establishes no general compiler service or final floor. See the [report](../../../experiments/java/compiler/results/initial/REPORT.md), [prospects](prospects.md) and [reproduction](../../../experiments/java/compiler/README.md).
