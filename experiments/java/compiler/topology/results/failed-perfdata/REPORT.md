# Incomplete JVM environment attempt

The first main attempt stopped after 14 recorded cases when concurrent JVMs encountered an hsperfdata PID-namespace collision. It is retained as environment/failure evidence and contributes **no averages, medians or wins** to the final comparison. The replacement primary and longer diagnostic disable JVM perf-data files equally with `-XX:-UsePerfData`.

The [raw identity and failure](provenance.json) preserve the incomplete status. Read the [complete primary report](../primary/REPORT.md) for results.
