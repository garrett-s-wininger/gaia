# Longer compiler trace separates heap counters from process memory

Sharing one JVM still gives shorter late batches in this one-block diagnostic: **0.677 versus 1.142 seconds** at four slots and **0.695 versus 1.336 seconds** at eight. Four-slot PSS remains higher for one JVM before the requested GC endpoint. After requesting GC, reported heap-used bytes fall sharply in every topology while observed PSS often stays high. Remaining PSS cannot be labelled purely shared-runtime overhead or an exact live set. Even after the request reduces reported aggregate heap-committed bytes to about 114–192 MiB, process PSS remains roughly 1.5–2.25 GiB. Its composition is unresolved: native-memory tracking, full mapping/LazyFree accounting and allocator/release diagnostics would be needed to explain it.

| Slots | JVMs | Median of 10 late batches s | PSS before / after requested GC MiB | Heap used before / after MiB | Heap committed before / after MiB | Largest sampled sequential PSS MiB | Mean actual sampling interval ms |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 1 | 0.677 | 1706 / 1588 | 1222.8 / 24.9 | 1498 / 114 | 1706 | 81 |
| 4 | 4 | 1.142 | 1580 / 1586 | 656.9 / 32.9 | 1245 / 124 | 1875 | 96 |
| 8 | 1 | 0.695 | 1786 / 1528 | 1003.8 / 41.1 | 1428 / 160 | 2169 | 99 |
| 8 | 8 | 1.336 | 2241 / 2255 | 946.4 / 51.9 | 1450 / 192 | 2282 | 153 |

The 50 ms setting is a wait **after** sequential memory reads, not a 50 ms actual cadence. Reading all processes costs roughly 30–100 ms per sample on average here. Sampling runs alongside the ten late batches and can perturb their wall time. These results are a separate diagnostic, not additional independent primary blocks.

## The full late-window trace

Each value is seconds for another eight-target batch, with no compiled-result cache. Latency still changes substantially in parts of the trace, so even this longer run does not prove convergence.

| Slots | JVMs | Ten consecutive batch times, seconds |
|---:|---:|---|
| 4 | 1 | 1.133 → 0.833 → 0.812 → 0.841 → 0.617 → 0.713 → 0.641 → 0.494 → 0.495 → 0.564 |
| 4 | 4 | 1.420 → 1.219 → 1.144 → 1.278 → 1.140 → 0.986 → 1.025 → 0.948 → 1.086 → 1.400 |
| 8 | 1 | 1.016 → 0.912 → 0.714 → 0.676 → 0.928 → 0.730 → 0.605 → 0.625 → 0.622 → 0.667 |
| 8 | 8 | 2.236 → 1.939 → 1.718 → 1.474 → 1.367 → 1.275 → 1.238 → 1.304 → 1.274 → 1.099 |

Before these ten batches, every session also executes a first batch and one excluded warmup. The optional GC request happens only after all timed batches; the subsequent memory snapshot is not timed as compilation. It requests GC, observes the reply and immediately reads process memory. It is not a guarantee of full collection, released resident pages or exact minimal footprint. Consumer checks happen afterwards. Reported sampled maxima are componentwise maxima of sequential process sums, not one atomic simultaneous group snapshot: they can overstate or understate true group memory and are not a guaranteed bound.

## Validation and scope

Run `20261031T050609.348992Z` completes four sessions, 48 batches, **384 complete target compilations, 87,168 class outputs and 32 fresh-loader consumer checks**. All targets match the same independent CLI references as the [primary comparison](../primary/REPORT.md), flags/heap caps match, all sessions shut down normally and admitted inputs pass final hashes. This diagnostic uses exactly the same four frozen measured sources as the primary run.

[Portable per-batch/memory samples](summary.json), [validation](validation.json), [provenance and raw hash](provenance.json). Run with `--workers 4 8 --trials 1 --steady-batches 10 --sample-interval 0.05 --gc-after` and fresh output. The primary run has three shuffled blocks and no continuous sampler or requested GC; keep its latency estimates separate.
