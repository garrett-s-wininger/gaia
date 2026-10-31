# Groovy startup through JVMTI

This experiment uses a bounded native diagnostic agent to find work worth removing. Loading the agent is not an optimization. Final candidate timings run without it.

The controls are ordinary fresh JVMs with normal shutdown and warm filesystem pages. `none` has no agent; `idle` loads the same library without optional capabilities; `classes` records class load/prepare; `cpu` adds 4ms platform-thread stack snapshots weighted by observed per-thread CPU deltas; `alloc` samples allocations at a 64KiB mean interval. CPU is attributed to the stack seen at the end of each interval, so short functions and transitions are approximate. Class preparation is not class initialization. Sampled object sizes are observations, not exact total allocated bytes. The first pre-live allocation events are explicitly skipped.

There is no MethodEntry, retransformation, ClassFileLoadHook, object tagging, or retained Java class/object graph. Maps have entry and string bounds. The process may still encounter safepoints, changed compiler decisions and sampling overhead. The agent's native callback duration does not measure all that overhead. Matched full-process controls do. Separate unified JVM class-load logs check actual archive sharing with each mode; intrusive logging is excluded from ordinary timings.

## Reproduce

Use Linux, a C++20 compiler, Python 3 and the pinned Java/Groovy/Picocli assets prepared by the [parent experiment](../README.md). Run its DGM baseline first; the profiler reads its `results.json` to locate the matching stock archive and fixture. `TOOLS` below is that experiment's reusable `_work` asset directory, not a machine-specific required location. Generated binaries, archives and logs belong in this directory's ignored `_work` on a volume with space.

From the repository root, select freshly prepared inputs and new output directories:

```sh
TOOLS=/path/to/framework-assets
BASELINE_RESULTS=/path/to/dgm-baseline/results.json
python3 -B experiments/java/startup/jvmti/profile.py \
  --tools "$TOOLS" --baseline-run "$BASELINE_RESULTS" \
  --output experiments/java/startup/jvmti/_work/profile --blocks 5
python3 -B experiments/java/startup/jvmti/benchmark.py \
  --jdk "$TOOLS/toolchain/jdk-25.0.5.0.3" --downloads "$TOOLS/downloads" \
  --output experiments/java/startup/jvmti/_work/module-results --trials 7
python3 -B experiments/java/startup/jvmti/validate.py --tools "$TOOLS" \
  --run experiments/java/startup/jvmti/_work/module-results/results.json
python3 -B experiments/java/startup/jvmti/confirm.py --tools "$TOOLS" \
  --run experiments/java/startup/jvmti/_work/module-results/results.json \
  --output experiments/java/startup/jvmti/_work/confirmation --blocks 7
```

The candidate indexes each freshly discovered system module descriptor's unqualified export/open package names once. It keeps the original package ownership selection and classifications, including qualified export/open exclusions, and does not serialize runtime identities. The source-rebuilt control changes the same class packaging without the algorithm change. Every variant has a matching static CDS archive. Unchanged jar entries and DGM data must remain byte-identical. `ModuleProbe.java` compares membership to upstream predicates across actual system descriptors and synthetic named, open, automatic, qualified/unqualified and absent-package cases, then compares complete resulting tables and checks runtime named/unnamed access. `validate.py` also checks descriptors, fresh child loaders, mutable metaclasses and extension addition/removal.

## Specification boundaries

The [JVMTI specification](https://docs.oracle.com/en/java/javase/25/docs/specs/jvmti.html) defines event capabilities, live-phase restrictions and sampled allocation semantics. In particular, [`GetAllStackTraces`](https://docs.oracle.com/en/java/javase/25/docs/specs/jvmti.html#GetAllStackTraces) covers live platform threads, not virtual threads; [`GetThreadCpuTime`](https://docs.oracle.com/en/java/javase/25/docs/specs/jvmti.html#GetThreadCpuTime) provides the CPU deltas; [`SampledObjectAlloc`](https://docs.oracle.com/en/java/javase/25/docs/specs/jvmti.html#SampledObjectAlloc) is probabilistic. This prototype is a single-threaded Groovy startup diagnostic, not a general virtual-thread profiler or a promise of JVMTI transparency.
