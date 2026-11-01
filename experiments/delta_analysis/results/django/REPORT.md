# Django: retain facts first; maintained proofs do not establish an overall win

The complete source-edit response improves substantially when Grimp's parser facts and native graph survive requests. Adding a separate dynamic shortest-path engine does **not** establish a further overall benefit in this experiment. This is an architectural experiment in source tooling, with no compiler flags changed and no claim of faster compilation.

Seven shuffled blocks compare 16-event traces over Django 6.1.2: 907 original modules, 3,203 direct dependency edges and 3,358 import records. Every request returns three dependency-navigation sets and an experimental forbidden-dependency diagnostic, with one shortest current explanation per violation. The [implementation and semantic boundary](../../README.md) are essential: the native control uses the same single-explanation response, and the real full linter independently verifies the violation set. This is not the full multi-chain CLI report.

## Complete costs

Values are medians of per-trace sums in milliseconds. Parenthesized counts identify how many event spans enter each row. The rows overlap; do not add them together.

| Operation | Cached library | Retained native | Delta proofs |
| --- | ---: | ---: | ---: |
| All requests, including initialization (16) | 467.343 | 199.637 | 203.136 |
| After initialization (15) | 415.383 | 155.366 | 156.186 |
| Edits preserving module membership (8) | 240.440 | 22.262 | 24.574 |
| Module membership changes (4) | 165.877 | 129.923 | 128.525 |
| Initial response (1) | 51.401 | 45.597 | 47.671 |
| Rule-target change (1) | 2.293 | 1.805 | 1.414 |
| Unchanged requests (2) | 0.908 | 1.243 | 1.560 |

For each shuffled block, compare the candidate's total with that block's control total, then summarize those percentages:

- **Retained native versus cached library:** median **57.47% less time** across all event spans; block reductions range from 52.21% to 59.43%. For the eight edits with unchanged module membership, median reduction is 91.09%.
- **Delta proofs versus retained native:** median **1.75% more time** across all spans; individual differences range from 7.14% less to 6.40% more. That variation crosses zero and supplies no robust overall improvement.
- **Delta proofs on fixed-membership edits:** median **11.81% more time** than retained native; differences range from 5.40% less to 14.86% more. The additional proof representation is not justified by this edit mix.
- **Rule-target change:** delta proofs use a target already maintained for navigation, reducing the complete request by a paired median 22.84%, with reductions in all seven blocks. The absolute medians are 1.805 versus 1.414 ms. Neither retained arm reparses source or recomputes navigation for this event.

These are bounded observations on one corpus and a designed trace, not an estimate of average developer productivity, a language-server benchmark or confidence intervals. The large first comparison combines retained source production and precise consumer caching; it must not be credited to the min-plus transformation alone. The third arm isolates the additional transformation against that stronger implementation.

## What the counters explain

The producer parses one file on ordinary edits and 907–909 on membership changes. For example, making the missing probe module appear costs 30.959 ms in retained native and 31.514 ms with proofs; roughly 28–29 ms of each is producer work. The alternative touches only eight root/node proof entries and examines 14 edges at that event, so accelerating the derived analysis cannot remove the scan cost.

A single import retarget is less local in the derived graph. It produces two edge deltas, processes 741 root/node proof entries across the three maintained targets and examines 5,426 edges. Its median request costs 5.113 ms with proofs versus 3.687 ms with retained native. Removing the added dependency costs 3.806 versus 2.814 ms. A small source edit does not guarantee a small maintained result change.

The disconnected probe cycle is a useful correctness and locality case. Removing its exit retracts the affected violations: the violation count falls from 31 to 28, then returns to 31 after restoring an exit. Its delta update examines 24 edges and handles 11 root/node entries, costing 2.348 ms versus 2.630 ms for retained native. This local advantage does not compensate for broader repairs elsewhere in the trace.

The location-only edit refreshes one selected diagnostic without graph-query or proof-propagation work. The comment-only edit changes no import facts; both retained arms scan one file and perform zero native graph queries, proof repairs or diagnostic refreshes. The cached-library arm still reassembles its graph and rechecks consumers. Unchanged requests are fastest in the simpler cached-library arm because its no-change path returns directly from retained final answers; retained-arm orchestration still has overhead.

## State and correctness

At initialization, both retained arms store 3,358 native-parser import records alongside the 907-module native graph, 1,798 navigation entries, 164 diagnostic witness edges and a witness-owner index. The proof arm additionally stores 6,406 forward/reverse adjacency entries, 1,801 distances, 1,798 parent entries and reverse witness-child sets. Those are logical entries, not bytes. Process peak RSS includes oracles and cannot isolate retained-state costs.

All **336 responses** pass comparison with fresh uncached Grimp graphs and the unmodified Import Linter rule. All graph facts, source lines, line text and lazy flags match. Violations and minimum explanation lengths agree; every explanation edge is current. Equal-length tie-breaking is allowed. Four focused tests include **3,000 random update batches** checked with independent breadth-first search, cyclic support loss, alternatives, node changes, stale generation rejection and syntax-failure rollback before publication.

Correctness exposed a context boundary in Grimp 3.17's file cache: after a missing module appears, an unchanged `from ... import ...` can retain its old resolved edge. The [recorded reproduction](cache-boundary.json) shows the stale cached edge and the correct fresh/rotated-cache edge. The benchmark repairs the cached-library control by rotating its cache namespace on membership changes. Both retained arms conservatively rescan all files. Every timed answer therefore passes the same current-source checks.

An earlier preflight also rejected the assumption that the full linter returns one chain for exact-module pairs. The final controls explicitly use a one-explanation adapter; the native path calls its singular shortest-chain API. No timing benefit comes from charging the native comparator for explanations absent from the requested response.

## Decision and next boundary

Keep the **retained native producer plus consumer caching** as the successful architectural baseline. Do not adopt the extra Python proof graph for this workload. The result supports extending a mature tool's lifetime and exposing its changes; it does not support replacing fast native graph traversal indiscriminately.

The next bounded question is producer reuse across namespace changes: retain file-local import references separately from their resolved targets, index the names and absences they observe, then rebind only affected references when modules appear or disappear. That would connect source discovery, contextual resolution and incremental database-style views at the dominant boundary here. It needs the same fresh resolver oracle, absent-module counterexample and retained-native control. No speedup from that further design has been measured.

## Evidence and reproduction

The [runner](../../run.py), [analysis](../../analyze.py) and [reproduction instructions](../../README.md#reproduce) define the experiment. [Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [package acquisition](acquisition.json) and [raw identity](raw-identity.json) accompany the ignored [raw observations](results.json), registered in the repository [evidence manifest](../../../../research/evidence.json).

Clocks include writing edited files, parser work, graph maintenance and full JSON serialization. They exclude interpreter/library startup, corpus copies and the fresh validation calls between requests. Those separate spans are recorded. Summed request clocks do not represent an uninterrupted session; intervening oracles can influence cache warmth. Shared advisory locking excludes cooperating measured cases, not all unrelated activity. Source/tool identity checks passed again after measurement. The experiment used a private source copy and did not change production integrations.
