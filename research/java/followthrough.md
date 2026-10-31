# Longer compiler lifetimes and prepared runtime discovery

This follow-up joins three questions: how much useful compilation fits in a resident-memory admission budget, whether a prepared runtime-image class index improves a complete Groovy command, and whether native compiler profile-guided optimization improves useful compilation.

## Shared compiler runtime helps this bounded queue

The queue uses four compiler slots and eight alternating whole Picocli targets per batch. With a requested 1,536 MiB aggregate Java heap and an 1,800 MiB sampled PSS admission gate:

| Arrangement | Completed batches / targets | Median of last eight batch times | Maximum sampled PSS |
| --- | ---: | ---: | ---: |
| One G1 JVM | 24 / 192 | 981 ms | 1,252 MiB |
| One Parallel-GC JVM | 24 / 192 | 960 ms | 1,765 MiB |
| Four Parallel-GC JVMs | 21 / 168 | 1,289 ms | 1,863 MiB |

Four JVMs crossed the sampled admission budget and stopped before batch 22. This demonstrates a soft admission decision, not enforcement of a resident-memory quota: within-batch growth already overshot the budget. All completed class outputs matched the independent CLI references and retained classes executed successfully. The last-eight windows are different positions when admission stops, and completed total work differs; the table is not an equal-total-work session speedup.

There is one trace per arrangement, mostly warm filesystem pages, and no statistical confidence or proven JIT convergence. Whole-process CPU is recorded; separate JIT/GC attribution remains unresolved. The same whole-source targets repeat with new javac tasks; compiled-result caching does not substitute for actual compilation.

Requested GC left about 867 / 972 / 1,808 MiB PSS in the one-G1 / one-Parallel / four-Parallel arrangements, with about 23 / 20 / 30 MiB reported heap used. These counters establish that heap-used is an inadequate resident-memory budget, not that the remainder is a leak or entirely caused by a collector. Sequential smaps samples are not atomic simultaneous peaks. A separate NMT diagnostic records broader allocation categories; NMT committed/reserved bytes cannot simply be subtracted from PSS to identify a cause.

The first queue harness saved all three primary cases, then rejected NMT's exit report because the inherited line protocol prohibited stdout after shutdown. That diagnostic failure is retained in [the summary](../../experiments/java/followthrough/results/queue/summary.json). The published implementation captures NMT stdout and reruns that diagnostic separately; primary timing loops were not rerun solely for this protocol fix.

## Mixed retention exercises admission and cache eviction, not OS pressure

A separate short paired configuration uses the same one-JVM Parallel collector and a 900 MiB soft PSS gate. Solo and compound traces both stop before their third batch, after sixteen successful compilations. Their sampled aggregate maxima are 988 and 1,049 MiB: the budget detects overshoot and stops further work; it does not prevent it.

The compound trace holds 665,075 bytes of real source generations plus roughly 16 MB of verified artifact chunks under a 16 MiB logical admission budget. While compilation runs, it replays actual Django artifact access ranges. The cache records 81,313 evictions and about 5.33 GB of repeated warm-host reads across 109 loops; retained admitted bytes stay at 16,721,395. This is genuine bounded application-cache pressure with additional consumer work. It is not a host-memory shortage, cgroup limit, physical disk stress test, or proof of one unified allocator across components. The one-block timings are not an equal-work speed comparison.

The corrected NMT diagnostic runs two batches separately from primary timing. It reports about 20 MB heap used versus about 802 MB heap committed immediately after requested GC, with about 995 MB anonymous PSS in the subsequent smaps sample. Exit NMT reports about 895 MB heap committed after the later consumer/shutdown work. Those observations identify retained heap commitment as a candidate contributor. They occur at different instants; committed bytes are not resident bytes, and mapping-level attribution remains necessary. The first diagnostic's stdout-protocol failure remains preserved rather than silently replacing its evidence.

## Prepared discovery helps lookup without a complete-command win

The Groovy prototype replaces only `java.base` class discovery beneath `java` with a producer-built immutable map. The producer executes the exact original ClassFinder query against an admitted runtime image. Its table has 1,557 simple names in 60,418 bytes. Producer compilation/scan takes 1.73 seconds; rebuilding source-control and indexed variants takes 3.68 / 3.40 seconds. Those costs are outside request clocks and remain charged preparation.

Five paired blocks of ordinary JVM processes, with only default CDS and no diagnostic agent, give:

| Operation | Source-rebuilt control | Prepared index | Paired wins |
| --- | ---: | ---: | ---: |
| Three import-map queries | 625 ms | 481 ms | 5 / 5 |
| Registry initialization | 492 ms | 524 ms | 1 / 5 |
| Basic dynamic script, complete process | 1,684 ms | 1,695 ms | 3 / 5 |

The index improves the isolated lookup operation but establishes no complete-command startup improvement. A separate class-load diagnostic confirms that the new index helper does load during the basic command; those instrumented runs are excluded from timing claims. These numbers use a different archive/preparation policy from earlier custom-CDS studies and should not be compared across studies as regressions or additive gains.

Import results remain identical across standard and additional Java packages, and callers receive fresh mutable result maps. All 2,007 DGM descriptors match; fresh classloaders, mutable metaclasses and extension-module addition/removal remain live. The harness verifies the exact runtime-image digest before/after the run. Runtime version is checked by the reader but is not a sufficient identity by itself. This externally admitted prototype is not a general persistent index cache or framework snapshot.

## Native optimization levels account for part of the apparent PGO gain

A real instrumented compiler image was built in 163.18 seconds, trained for 6.99 seconds on five successful compilations and one invalid request, then rebuilt from a 9.04 MB user profile in 121.89 seconds. The builder promotes the user-profiled build to effective O3 despite an explicit `-O2`. An additional O3 control without a user profile took 270.73 seconds to build. Both the original O2 and the new O3 control report **ML-inferred PGO**, so neither should be called PGO-off.

That is 562.8 seconds of incremental preparation measured here, reusing the earlier admitted SDK, reachability configuration and O2 image. The instrumented executable is 87.76 MB. The O2 / ML-inferred executable is 38.93 MB, O3 / ML-inferred is 54.46 MB, and O3 / user-profile is 31.92 MB. Builder time and code size tradeoffs remain visible rather than being folded into request latency.

The final three-way comparison uses three paired blocks. Each session performs nineteen successful compilations, one rejected invalid request and normal shutdown. All successful class-output identities match the independent compiler reference, and a valid request after the failure succeeds.

| Native endpoint | Complete session median | First compiler-body median | Later compiler-body median |
| --- | ---: | ---: | ---: |
| O2 / ML-inferred | 16.072 s | 772 ms | 599 ms |
| O3 / ML-inferred | 12.152 s | 645 ms | 594 ms |
| O3 / user profile | 12.048 s | 519 ms | 580 ms |

The user profile wins the complete-session comparison against O3 in three of three paired blocks, but the aggregate medians differ by less than one percent. Session ranges overlap substantially: O2 11.53–16.15 seconds, O3 / ML 11.70–13.97 seconds, and O3 / user profile 10.31–13.04 seconds. Compiler-thread CPU medians for the later requests are 599 / 592 / 579 ms, respectively. This small study does not establish a large sustained-throughput gain. The smaller image and faster first actual compilation are clearer benefits in this fixture.

The [original two-way run](../../experiments/java/followthrough/results/pgo/summary.json) is retained. It compared a combined optimization-level/profile change and must not supply an isolated PGO claim. The [three-way control](../../experiments/java/followthrough/results/o3-control/summary.json) is the appropriate attribution evidence. The profile includes both source fixtures; generalization to unseen production targets remains untested. These are matched observations within their own runs, not a universal native-versus-JVM ranking.

## Evidence and reproduction

The [implementation guide](../../experiments/java/followthrough/README.md) defines admission, companion, NMT and PGO boundaries. [Queue](../../experiments/java/followthrough/results/queue/summary.json) and [runtime discovery](../../experiments/java/followthrough/results/groovy-index/summary.json) summaries preserve the raw hashes. Full ignored observations remain local evidence; the repository evidence manifest registers their identities.
