# Longer compiler sessions and prepared runtime discovery

This directory extends the earlier JVM compiler topology/variant and Groovy JVMTI studies. Disposable builds live under caller-selected work paths; `_work` may point to a separate volume. Sources and reports are versioned; full `results.json` observations remain ignored.

## JVM queue and resident-memory admission

`run_budget.py` uses the existing whole-target compiler harness: eight targets alternating between the two pinned Picocli source variants, four worker slots, shared or separate JVMs. It compares one G1 JVM, one Parallel-GC JVM and four Parallel-GC JVMs. The targets remain whole; no unsafe source-file-level incremental javac is introduced.

A soft admission gate checks aggregate sampled PSS before starting each batch. It can stop further admission after a completed batch exceeds the requested budget. It is **not** a kernel-enforced memory quota, cannot prevent within-batch growth, and does not establish peak RSS. Sequential `/proc` process samples are not atomic simultaneous totals. `-Xmx` is also recorded separately from resident memory; Parallel GC can report a smaller effective `maxMemory` because of survivor-space accounting.

Every successful target must match the independent CLI class-output identity, and retained classes are executed outside compilation clocks. A separate short NMT run requests GC and records pre/post `smaps` plus JVM exit statistics. NMT changes runtime behavior and is excluded from primary latency comparisons. NMT committed/reserved counters are not resident-memory attribution, and its coverage is incomplete.

```sh
python3 experiments/java/followthrough/run_budget.py \
  --prepared "$BASE_PREPARED" --work "$WORK/queue" \
  --output experiments/java/followthrough/results/queue \
  --batches 24 --budget-mib 1800 --heap-mib 1536 --cpus 8
```

An optional `--companion-command` accepts JSON argv for the artifact/workspace retention companion. The child emits a JSON `READY` event, remains live during compilation, and handles SIGTERM cooperatively. Its PID is included in sampled totals; its logical allocation budget is distinct from process PSS. Replaying reads adds useful concurrent consumer work and must not be described as an equal-work latency comparison against the no-companion trace.

## Groovy runtime-image index

`groovy_index.py` records exactly the `ClassFinder` mapping for the `java` subtree in `java.base`, then rebuilds the same `Java9.java` source with and without using that producer index. Other Groovy locations still use their original discovery path. Consumers filter an immutable table into fresh maps/sets. Only ordinary JVM bytecode and the default CDS archive are used; no diagnostic agent or custom framework archive is present in timed runs.

The harness admits the exact runtime-image hash before execution and verifies it afterwards. The reader checks runtime version, bounds, duplicates and trailing data; version alone is not an exact image identity. This is an externally admitted fixed-runtime experiment, not a generally safe index cache keyed only by JDK version. Preparation includes the producer scan and variant compilation. Dynamic metaclasses, fresh loaders, DGM records and extension addition/removal remain correctness controls.

```sh
python3 experiments/java/followthrough/groovy_index.py \
  --jdk "$JDK" --tools "$JAVA_STARTUP_TOOLS" \
  --work "$WORK/groovy-index" \
  --output experiments/java/followthrough/results/groovy-index --trials 5
```

## Native profile-guided optimization

`pgo.py` attempts a real instrumented compiler image, profile collection through successful/current/invalid targets, and an optimized image. Both images retain the existing reachability configuration and target-SDK adapter. Preparation and measurements are recorded separately. Native Image may promote a user-profiled build to effective O3 even when `-O2` is supplied; record the effective build output and use an O3 control without a supplied profile before isolating its effect. Such a control may still use inferred profiles. If a toolchain cannot produce the profile/image, the exact failure is preserved rather than interpreted as a performance result.

```sh
python3 experiments/java/followthrough/pgo.py \
  --native-image "$NATIVE_IMAGE" --prepared "$NATIVE_PREPARED" \
  --baseline "$O2_COMPILER" --references "$ENDPOINT_REFERENCES" \
  --modules "$PLATFORM_SDK" --work "$WORK/pgo" \
  --output experiments/java/followthrough/results/pgo --trials 3
```

`control_o3.py` adds a separate `-O3` build without a user profile and remeasures O2, O3 and user-profiled O3 in the same paired blocks. The measured Oracle toolchain reports ML-inferred PGO for both ordinary controls; effective build output is authoritative. It reuses the same prepared endpoint, SDK, reachability configuration and failure/recovery checks. Provide `--native-image`, `--prepared`, `--o2`, `--pgo`, `--prior-results`, `--references`, `--modules`, `--work` and `--output` paths as in the PGO invocation.

References: [NMT coverage and overhead](https://docs.oracle.com/en/java/javase/25/vm/native-memory-tracking.html), [existing topology study](../compiler/topology/README.md), [execution variants](../compiler/variants/README.md), [JVMTI study](../startup/jvmti/README.md).
