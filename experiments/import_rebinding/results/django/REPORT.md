# Namespace observation indexing removes full rescans; full reference retention is optional here

The producer experiment finds a useful architectural improvement: retain the names that import resolution observes, including absent names, and invalidate only files affected by module membership changes. This reduces the complete tested trace by a paired median **41.61%** against the previous full-rescan policy. Retaining complete parsed references and rebinding them also works correctly, but does **not** establish a further overall latency improvement against scoped native reparsing.

This changes source-tool internals rather than compiler settings. It measures dependency navigation and diagnostics, not compilation speed. The [implementation](../../README.md) explains the native parser patch, response contract, controls, exact resolution rule and reproduction procedure.

## Comparison

Seven shuffled blocks run three arms over an 18-event Django trace. The first 16 events reproduce the prior experiment; two additional events introduce/remove a module that shadows a popular imported name. All arms use the same locally built native scanner, native graph and cached native consumers. A fresh unmodified Grimp wheel supplies the graph oracle, and the unmodified full Import Linter contract checks the diagnostic decisions and minimum explanation lengths.

Milliseconds below are medians of per-trace event-span sums. Rows overlap and should not be added together.

| Operation | Full rescan | Scoped native parsing | Retained references |
| --- | ---: | ---: | ---: |
| Complete trace, initialization included (18 events) | 338.515 | 196.944 | 194.938 |
| Original trace only (16 events) | 232.608 | 144.126 | 142.037 |
| After initialization (17 events) | 288.600 | 121.558 | 121.448 |
| Four local membership changes | 150.712 | 38.770 | 38.690 |
| Two popular-name membership changes | 106.260 | 52.752 | 51.665 |
| Eight edits preserving membership | 24.461 | 26.077 | 25.964 |
| Initial response | 51.515 | 72.963 | 73.489 |

The principal decisions use **paired block percentages**, whose median need not equal the ratio of the medians in the table:

- **Scoped native versus full rescan:** 41.61% less complete trace time, with reductions in every block (39.16–43.99%). On the original 16-event trace, the paired median reduction is 38.10%; the result does not depend on adding the popular-name stress case.
- **Local membership changes:** scoped native uses 74.28% less time, with block reductions of 71.92–75.13%.
- **Retained references versus full rescan:** 42.78% less complete trace time, with reductions in every block (38.46–46.28%).
- **Retained references versus scoped native:** paired median **0.11% more time**, with individual differences from 6.63% less to 2.71% more. On the original trace the median is 0.99% less, again with differences on both sides of zero. There is no established overall improvement over this stronger control.
- **Initial response:** both indexed arms pay roughly 22 ms more at their medians to expose references, bind them and construct the observation index. Ordinary fixed-membership edits also have some extra index-maintenance cost. The win requires subsequent membership changes or equivalent reuse; it is not a faster one-shot startup.

These are descriptive observations on one corpus and a designed edit trace, not confidence intervals or an estimate of general developer productivity. Absolute times should not be compared directly with the earlier experiment's matrix: this run uses a locally built scanner and a different measurement period. The controls here were remeasured together.

## Work avoided

| Event | Full rescan: files parsed | Scoped native: files parsed | Retained references: files parsed | Unchanged affected files |
| --- | ---: | ---: | ---: | ---: |
| Missing module appears | 908 | 2 | 1 | 1 |
| Module disappears | 908 | 1 | 0 | 1 |
| Popular name becomes a module | 908 | 63 | 1 | 62 |
| Popular module disappears | 907 | 62 | 0 | 62 |

The exact/parent observation index identifies affected sources without reparsing the repository. This is the large shared improvement. Full reference retention removes the remaining native parsing of those selected unchanged files, but parsing was already limited to a small subset.

When the missing probe module appears, the complete response medians are **35.206 / 10.034 / 9.053 ms** for full, scoped and rebinding. Around 6 ms remains in package discovery for all three. On removal the medians are **38.463 / 9.357 / 8.617 ms**. The rebinding path does no source parsing at all in that removal event, yet still pays discovery, graph/result updates and serialization.

The popular-name case inserts `django/utils/translation/gettext_lazy.py`. Grimp's current static rule then binds references from 62 unchanged files to the new exact module rather than its parent. This deliberately constructed shadowing case is not an upstream Django edit or an executable application benchmark. Rebinder medians are 16.628 ms to introduce the module and 29.115 ms to remove it, versus 21.626 and 31.305 ms for scoped parsing. The aggregate paired differences vary widely and cannot establish a reliable retained-reference advantage for that pair alone.

## Correctness and retained state

The native patch exposes Grimp's existing parsed absolute references. It leaves relative-name construction, syntax handling, source line/text extraction and lazy flags in the original parser. The bounded binder checks the exact name and its immediate parent, matching the pinned native internal-import resolver. Both candidate names enter the index even when absent. Unsupported context changes require a new producer; this is not general Python runtime name resolution.

All **378 measured responses** match fresh graph modules, edges and complete source metadata. Diagnostic sets and minimum explanation lengths agree with the real full linter; every emitted explanation has current edges and locations. The response provides one explanation per violation, not the CLI's full multi-chain report. The experimental rule is not a policy declared by Django.

Four focused tests additionally validate **360 randomized source-update batches**, relative/lazy/multiline/star/nested imports, namespace packages, missing-name recovery, removal of obsolete index entries after retargeting, file/package replacement, stale-generation rejection and syntax-error rollback before publication. The native extension reproduction build is separately checked; see [build-helper validation](build-helper-validation.json).

Initial retained logical state is:

- All arms: the existing 907-module graph, 3,203 dependency edges and 3,358 resolved import records, plus native consumer caches.
- Both indexed arms: **2,869 candidate names and 10,056 name-to-source memberships**, with a reverse index for removing a source's observations.
- Rebinding only: **6,520 reference records**, whose line strings sum to 292,619 UTF-8 bytes. Object/container overhead is additional and unmeasured. The scoped control discards these records after deriving its index.

These are logical counts, not RSS or a memory quota. Process peak RSS includes oracle graphs and does not isolate retention cost.

## Timing limits and a separate diagnostic

Request spans include source writes, discovery, native parsing/reference export, binding, index updates, graph mutation, native diagnostics/navigation and full JSON output. Native compilation, corpus copying, library startup and correctness checks are outside these spans. Fresh oracle construction between requests can perturb allocator, GC and cache state. Totals are sums of spans, not uninterrupted session timings. Shared advisory locking excludes cooperating measured cases, not all unrelated activity.

A separate [GC-instrumented diagnostic](gc-diagnostic.json) observed about 14.1 ms of garbage collection during the full-rescan popular-name insertion. It did **not** reproduce the unusually expensive rebinding removal seen in the main matrix. This does not establish GC as that removal's cause. The diagnostic is intrusive and is not pooled with the seven-block matrix; no GC time is subtracted to manufacture a hypothetical faster result. An uninterrupted service benchmark with controlled validation allocation would be needed before claiming a small rebinding advantage.

## Decision

Keep the **namespace observation index plus scoped native parser** as the strongest demonstrated next baseline. It obtains most of the useful reduction while retaining fewer records. Keep the full-reference variant as a tested alternative, not the selected implementation for this workload.

The substrate connection is concrete: source bytes alone do not identify a binding answer. The tool must retain which namespace entries, including absences, that answer can depend on. Exposing native facts at that boundary makes precise invalidation possible without replacing the parser or weakening its output.

About 6 ms of module discovery remains on each namespace change. That is now a visible next boundary, but no incremental-discovery speedup is claimed here. There is also a startup/retention tradeoff worth testing over actual service demand before integration. No production service, language server or compiler path was changed.

## Evidence

[Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [native build](native-build.json), [raw identity](raw-identity.json), [raw observations](results.json), [runner](../../run.py), [analysis](../../analyze.py), and [reproduction](../../README.md#reproduce). The ignored raw file is registered in the repository [evidence manifest](../../../../research/evidence.json).
