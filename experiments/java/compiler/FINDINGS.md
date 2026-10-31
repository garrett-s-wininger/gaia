# JVM compiler experiment

For current conclusions and practical limits, start with the [research review](../../../research/compiler/jvm/findings.md). These notes retain the detailed experiment comparisons; measured reports remain under `results/`.

The [initial comparison](results/initial/REPORT.md) validates 30 measured operations over real Picocli sources. A jlink image alone is near the full CLI; training improves fresh API launch and initialized process reuse provides the largest latency reduction. Two private worker contexts improve throughput for independent complete compilation targets, while retaining Java's joint-compilation semantics within each target.

The minimal runtime still uses an external full target SDK. Memory delivery and physical class files are separate endpoints, startup is not free, and CPU cost was not measured in that initial comparison. The [variants continuation](results/variants/REPORT.md) adds compiler-phase thread CPU, process CPU, longer convergence and optimized Native Image. Read the [human findings](../../../research/compiler/jvm/findings.md) and [reproduction](README.md) for scope and limits.
