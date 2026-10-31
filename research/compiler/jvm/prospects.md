# What should follow the JVM compiler studies

The evidence supports initialized compiler workers and faster native first use. The remaining questions concern longer lifetimes, memory composition, input access and broader compatibility.

## Compare useful capacity under a resident-memory budget

The [topology study](../../../experiments/java/compiler/topology/results/primary/REPORT.md) improves batch time but does not guarantee lower PSS. The [longer follow-up](../../java/followthrough.md) now applies a sampled soft admission gate; it detects overshoot and stops further batches, rather than enforcing a quota. Extend to genuinely varied production targets and an explicit resource policy. Keep worker count, actual compilations and retained outputs comparable; a maximum Java heap is not a process memory quota.

Characterize the large resident remainder after requested GC with native-memory tracking, full smaps/LazyFree observations and allocator/release diagnostics. A small heap-used counter is not a complete live footprint, and sequential process samples do not establish an exact peak. Keep requested-GC diagnostics outside ordinary latency claims.

## Establish the useful JIT and collector lifetime

The [execution variants](../../../experiments/java/compiler/results/variants/REPORT.md) still show named JIT activity after 32 requests. Later 24-batch traces broaden memory/lifetime observations but do not establish convergence or separate JIT/GC time. Compare a small finalist set on genuinely varied targets before selecting a persistent-pool policy. Retain compile-thread CPU, whole-process CPU and heuristic worker attribution separately.

C1-only helps first use but hurts repeated compilation here. Parallel GC is promising for this fixture; collector behavior should be retested under memory pressure and different target sizes. Keep Shenandoah's same-binary C2 control and explicit effective flags. Epsilon's same-budget growth/failure makes it unsuitable as an unbounded pool default in this study.

## Test native code generation against a mature JVM control

Native Image improves first use in the earlier trace. The [profile study](../../java/followthrough.md#native-optimization-levels-account-for-part-of-the-apparent-pgo-gain) now compares effective O2/inferred, O3/inferred and O3/user-profile controls. Supplied profiles improve first compilation and image size, while sustained gains over ordinary O3 are small and noisy. Test unseen targets and amortization before a pool/image policy. Charge profile collection, image construction, SDK preparation and invalidation; effective flags matter because supplied profiles promote the builder to O3.

Keep metadata/profile caches distinct from cached machine code and from compiled-result caching. A fresh target must still execute a real compilation and emit the current class bytes. Record compatibility failures explicitly and preserve existing default-CDS controls.

## Admit SDK data through a measured interface

The native SDK adapter demonstrates public module locations with exact platform class bytes. A packed SDK or admitted source/dependency collection is a useful next JavaFileManager provider. Measure lookup, decoding, verification and ownership with real package/module/resource and failed-lookup behavior.

Platform metadata repeats across tasks, but javac symbol objects are mutable and context-bound. Separate immutable data from fresh task bindings instead of sharing those objects blindly. Count both compiler runtime and target SDK acquisition; a compact executable is not the complete toolchain.

## Broaden targets and worker guarantees

Use projects with more sources, dependencies, modules and target SDKs. Keep whole Java targets as queue items until a genuine incremental compiler establishes a stronger grouping contract. Files compiled independently against old binaries can preserve stale constants.

Annotation processors/plugins, cancellation, diagnostics, changed classpaths, source removal, long-lived failure recovery and shutdown need explicit tests. The current output consumers are correctness checks outside compilation clocks; add a complete compile-and-consume operation before claiming an end-to-end delivery win. Read the [findings](findings.md) and [reproduction guide](../../../experiments/java/compiler/README.md) before extending the service contract.
