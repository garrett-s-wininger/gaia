# Delta-maintained dependency navigation and diagnostics

This experiment changes the unit of work after an edit: retain native import facts, then maintain derived paths from edge additions and deletions. It uses a private Django source copy and native Grimp/Import Linter consumers. The [Clang integration](../integration/README.md) is a separate experiment.

Read the [measured report](results/django/REPORT.md), [research interpretation](../../research/connections/delta-analysis.md), or the [proposal that motivated it](../../research/connections/architectural-next.md).

## Operation and semantic boundary

Every request publishes an immutable JSON response containing:

- All other modules that depend, directly or indirectly, on each of `django.db.models`, `django.template`, and `django.utils.functional`.
- The forbidden-dependency rule's violations for exact modules under `django.utils.`, initially against exact module `django.db.models`. Each violation includes one shortest import chain and current source line numbers. The rule target changes to `django.template` late in the trace.
- The current source/configuration generation.

The rule is an experimental policy, **not a policy declared by Django or a claim of Django defects**. Navigation concerns module dependencies, not symbol definitions, Python types or runtime imports. Grimp's parser/resolver supplies all import facts, including lazy-import metadata and imports inside type-checking guards. External packages are excluded identically in every arm. The three query roots remain present throughout.

The actual installed `ForbiddenContract.check` runs in every arm. A small graph adapter replaces its chain traversal with a single-explanation operation: the control calls Grimp's native singular `find_shortest_chain`; the alternative supplies a maintained shortest path. All other rule logic and source-detail formatting remain in Import Linter. The adapter supports only this exact-module rule with no ignored imports or package expansion.

This boundary matters: the unmodified linter can return **multiple chains for one violation**, including longer alternative chains. An early assertion assuming a singleton failed on Django before measurement. This experiment measures the declared editor response, not reproduction of the full CLI report or the cost of enumerating all its explanations. The native control gets the same single-explanation operation, so unused chain enumeration cannot inflate its time. Equal-length witnesses may differ; minimum length, endpoints, every edge and every source location must be correct.

## Three controls

| Arm | Fact production | Derived answers |
| --- | --- | --- |
| `cached_library` | Public `grimp.build_graph`, disk cache enabled | Recompute native navigation and the adapted real rule after edits; reuse unchanged requests |
| `retained_native` | Native scanner for changed files; mutate a retained native graph | Cache unaffected answers; use native reachability and shortest-chain queries when invalidated |
| `delta` | Identical retained producer | Maintain target-rooted shortest proofs; use them for navigation and the adapted real rule; cache unaffected diagnostics |

The principal control is **retained native**, not repeated command startup. Both retained arms keep source import records, native graph state, navigation results, diagnostic witnesses and a witness-owner index. Both use declared edits from one serialized client. They do not rediscover edits through a filesystem watcher or a full content scan.

For a deletion, a native diagnostic whose chosen explanation remains valid is reusable. For an addition, any old ancestor of the new edge's importer might acquire a shorter explanation, so the native control invalidates those sources. Navigation recomputation is conservatively restricted to edges touching its prior reachable region. A rule-target change preserves unchanged navigation results. Location-only changes refresh witnesses using the affected importer without changing reachability. Both arms avoid all graph-query work on the exercised comment-only edit.

Any module addition/removal changes resolution context. For example, `from django.utils import later` resolves differently when `later.py` appears. Both retained arms rediscover and rescan all modules at this boundary. The public-cache control changes its cache namespace to force correct resolution. The pinned Grimp 3.17 cache otherwise retains a stale edge for an unchanged importer; [the executable reproduction](cache_boundary.py) and [observed result](results/django/cache-boundary.json) preserve this finding. No stale fast answer enters the timing comparison. Cache namespace rotation is a conservative experimental repair, not a production eviction policy.

The retained producer uses pinned Grimp internals (`_find_packages`, `scan_imports`, `_assemble_graph`) and its native Rust parser. This is an experiment in replacing the orchestration boundary, not a stable upstream extension API.

## Mathematical transformation

For each demanded target `t`, the alternative maintains distances in the min-plus algebra:

```text
d(t) = 0
d(u) = 1 + min { d(v) : import edge u -> v }
missing distance = infinity
```

Finite-distance nodes supply the navigation answer and determine forbidden-rule violations. A selected parent supplies one shortest explanation. Additions seed improvements that propagate through reverse edges. Deleting a selected parent edge first invalidates its entire witness subtree, then repairs it from still-valid boundary paths. A disconnected cycle cannot justify itself merely because each member points to another member. Source locations remain separately owned by the native import records.

This is a specialized dynamic shortest-path algorithm, not an implementation of general DBSP, differential dataflow, all-pairs closure or arbitrary incremental Python analysis. Its connection to incremental database theory is maintaining a derived relation from changes instead of rerunning every affected query. It retains an additional Python adjacency representation plus distance, parent and child maps for three roots; these costs can outweigh avoided native traversal.

## Trace, clocks and validation

Seven shuffled blocks run all three arms in fresh worker processes: 21 traces and 336 published responses. The 16-event trace contains initialization, unchanged requests, a location shift in `django.utils.deprecation`, a comment edit, added/retargeted/removed imports in `django.utils.hashable`, a reference to an absent module, two probe modules forming a cycle with an exit, exit deletion/recovery, module removal, restoration of the original edited files, a rule-target change, and another unchanged request. This is a designed stress trace over real Django source, not a captured user edit distribution. The two small probe modules are explicit fixtures; the corpus is not replicated for scale.

The request clock includes source writes, native parsing, delta discovery, graph mutation, derived-result maintenance and full JSON serialization. It excludes interpreter/library startup, corpus copying, response validation and logical-state counting. Initial native graph production and the alternative's additional graph/proof construction are charged to the initial request. Operating-system caches are not flushed. Worker process spans, preparation times and validation spans remain in the raw observations.

Every response is checked against a fresh uncached Grimp graph and an **unmodified full Import Linter contract**. Diagnostic source sets and minimum witness lengths must agree; all chosen witness edges and lines must be current. The retained native graph must match every fresh module, edge, line, line text and lazy flag. Independent breadth-first search checks 3,000 randomized dynamic graph batches; focused tests cover disconnected cycles, alternate paths, node removal, namespace changes, syntax failure rollback before publication, stale generation rejection and old response bytes.

The validation calls between events perturb cache warmth identically in protocol, though not necessarily in effect. Reported trace totals are sums of event spans, not uninterrupted end-to-end session timings. The shared advisory measurement lock excludes cooperating measured cases, not all unrelated system activity. Seven-block ranges are descriptive, not confidence intervals.

Logical state counts are retained. Process peak RSS includes fresh oracle graphs and copying, so it is **not** an attributable retained-memory measurement. This prototype does not implement arbitrary root removal, concurrent requests, crash recovery, general failure-atomic graph mutation, multi-version retention or a production memory quota. Syntax errors are tested at the scanner boundary before graph mutation.

## Reproduce

Use CPython 3.14 and a trusted Django source package matching the recorded manifest. The measured corpus is Django 6.1.2, with 907 Python modules and 3,203 unique direct dependencies. The installation [acquisition record](results/django/acquisition.json) and [provenance](results/django/provenance.json) identify selected tool/source bytes. Other interpreter dependencies and the complete OS are not hermetically pinned.

```sh
python3 -m venv experiments/_work/delta-analysis-env
experiments/_work/delta-analysis-env/bin/python -m pip install \
  grimp==3.17 import-linter==2.15

PYTHONDONTWRITEBYTECODE=1 experiments/_work/delta-analysis-env/bin/python \
  experiments/delta_analysis/run.py \
  --corpus /path/to/django \
  --work experiments/_work/delta-analysis-reproduction \
  --output experiments/delta_analysis/results/reproduction \
  --lock /path/shared/measurement.lock --blocks 7 --seed 7321

experiments/_work/delta-analysis-env/bin/python \
  experiments/delta_analysis/analyze.py experiments/delta_analysis/results/reproduction
```

Work/output directories must be fresh. The runner requires the two pinned analysis-library versions, runs the correctness tests, and verifies selected implementation, corpus, interpreter and library identities again after the matrix. Raw observations are ignored in Git; their hashes, generated summaries, validation, provenance and interpretation are retained. The acquisition record lists transitive package versions if reconstructing this exact environment.

Primary background: [Grimp's graph API](https://grimp.readthedocs.io/en/stable/usage.html), [Import Linter's forbidden contract](https://import-linter.readthedocs.io/en/stable/contract_types/forbidden/), and [DBSP, PVLDB 2023](https://www.vldb.org/pvldb/vol16/p1601-budiu.pdf). The installed, hashed library sources govern this experiment; current online documentation can differ from the pinned versions.
