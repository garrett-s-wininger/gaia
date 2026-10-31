# Local solver measurements

For current conclusions and practical limits, start with the [research review](../../../research/python/resolution.md). These notes retain the detailed experiment comparisons; measured reports remain under `results/`.

Run `20261028T232923.464853Z` isolates dependency solving from pip CLI startup, module loading and installation. The same pinned `packaging`/`resolvelib` libraries and the same finite candidate set are retained within each comparison. This is a Python reference provider over local wheels, not a native solver or a drop-in pip replacement. [Full report](results/initial/REPORT.md), raw observations (local artifact, `results/initial/results.json`), [reproduction](README.md).

There are **30 cases and 450 timed fresh processes**, 15 randomized trials per case. Each process performs three fresh solves against one immutable session, giving **1,350 timed solves**. Metadata/parsed predicates may persist; a completed solution never does. Admission, source open and repeated solve costs are separate, and successful closures are independently revalidated outside timing. The cache-free variants retain the same lexical decision order and must produce identical artifact selections. A separate smallest-candidate-set heuristic can change order and is reported independently.

The original 22 wheels are **byte-identical** to the previous experiment. A [fresh offline pip reference](results/initial/pip-reference.json) chooses the same 12 packages as every provider variant. The larger graphs are generated, not claimed to be real-world distributions. [The implementation](solver.py) also accepts a custom local wheel inventory and PEP 508 requirements/constraints; the tests exercise that CLI with different package names, extras and both satisfiable/unsatisfiable requests.

## First-use costs

Medians, ms, **source open + first solve** from each complete observation. Each cell uses exactly the same package set within its row:

| Input | Artifacts / selected | Cached wheel metadata | Metadata catalog | Catalog + predicate caches | + Constrained-first order |
| --- | --- | ---: | ---: | ---: | ---: |
| Original case | 22 / 12 | 8.008 | 3.213 | 2.887 | 2.791 |
| Wide, 50 leaves | 251 / 51 | 48.430 | 18.398 | 12.776 | 12.476 |
| Wide, 250 leaves | 1,251 / 251 | 468.692 | 303.817 | 162.946 | 166.179 |
| Shared constraints | 441 / 111 | 150.492 | 97.141 | 42.834 | 42.945 |
| Conflicts | 22 / 7 | 12.318 | 7.407 | 5.967 | 2.681 |

On the 250-leaf case, moving to a catalog improves first use by about **1.5x** against a source that already caches wheel metadata. Adding generic predicate caches brings that to about **2.9x**. On shared constraints, catalog + caches is about **3.5x** faster than the wheel-cache control. These are reference-provider results, not pip CLI speedup claims.

The uncached control is deliberately a repeated-work reference, not alleged pip behavior: its wide-250 first use is 526.047 ms with 1,502 metadata ZIP opens. Session wheel caching reduces that to 1,251 opens, while catalog consumers perform zero. The provider eagerly checks all candidate eligibility, including Requires-Python, so it reads more candidate metadata than a lazy candidate policy may need. That policy is held fixed across storage variants; lazy preparation and eligibility summaries remain unmeasured alternatives.

## Repeated work and ordering

On wide-250, caching repeated requirement/candidate satisfaction checks reduces actual first-solve predicate evaluations from **63,252 to 251**, while keeping the same result and candidate preference. It does not eliminate solver bookkeeping or callback calls. Repeated-solve medians are **290.661 ms** with cached wheel metadata, **282.577 ms** with catalog-only, and **129.850 ms** with catalog + predicate caches. Once metadata is resident, replacing its backing store alone helps much less than avoiding repeated constraint work.

On the shared-constraint graph, candidate filtering drops from **801 to 441** candidate checks and satisfaction evaluations from **20,622 to 111**. Reused solve medians fall from 93.000 ms with wheel caching to 32.695 ms with catalog + predicate caches. Cache keys include snapshot, target, policy, requirement conjunction and excluded candidates. Satisfaction entries retain requirement objects so object IDs cannot be recycled underneath a cache key. Changed roots/constraints, extras, target compatibility and snapshot changes have explicit tests.

On conflicts, constrained-first ordering reduces candidate rejections from **48 to 12**, first use from 5.967 to 2.681 ms against the otherwise cached provider, and repeated solve from 2.337 to 0.571 ms. It does not reliably help the easy wide graphs: wide-250 becomes slightly slower. This is a workload-dependent generic heuristic, not a universal improvement or permission to change selection policy silently.

The unsatisfiable fixture produces the same outcome under every variant. Round limits remain a separate incomplete result. Tests use a finite exhaustive oracle on small successful/unsatisfiable graphs; larger unsatisfiable outcomes are not independently checked unsatisfiability certificates.

## Where the remaining time goes

Separate warm-solve profiles (local artifact, `results/initial/profile-data/profiles.json`) retain detailed functions and disjoint self-time buckets. They add material overhead and are not substituted into unprofiled measurements. Before predicate caching, version/specifier/requirement library work is the largest exclusive bucket on wide/shared graphs. After caching, resolver-core bookkeeping and Python provider/runtime work dominate. Wide-250 still makes **63,252 satisfaction callback calls** even when only 251 require evaluation; calls such as current-pin checks, preference selection and state/criterion iteration remain prominent. The profiles support investigating repeated bookkeeping/state scans next, not assuming another metadata encoding alone removes the remaining cost.

The earlier pip experiment was dominated by executing CPython/pip code, compilation/import work and pip's preparation/metadata paths relative to a byte-reader change. The new solver-only control is narrower than pip: it has no installed-state preference, build hooks, index/config behavior or package installation. Therefore its few-millisecond original-case solve cannot be compared directly with the previous 63–75 ms profiled pip resolve phase or ~0.9-second complete command. The meaningful ratios above hold engine, package set and implemented semantics fixed.

## Admission, memory and protocol implications

Admission hashes full wheel bytes and validates metadata once. It takes about **9.5 ms** for the original set and **348 ms** for wide-250 in the single recorded producer observations. One-shot use must add that cost; it is not free. The wide catalog is **731,466 bytes** versus **80,302 raw METADATA bytes**: JSON identities/local paths and repeated structure are intentionally simple rather than space-efficient. This trial is not a binary-format/storage-footprint win. Cache entry counts are retained, but no cache eviction or process-memory claim is made.

The useful boundary is now explicit: list candidates, retrieve certified metadata by immutable artifact identity, solve for a specified target/policy, and return selected artifact IDs. Package payload bytes need not be read during solving after admission. A later delivery step must verify those complete bytes independently; only metadata hashes are checked on wheel-backed metadata reads here. File mutations are not incorporated into an existing session/snapshot. The chosen JSON representation and identity projection are experimental, including rejecting conflicting candidate filenames for identical byte IDs.

This provides a local input interface for later repository/transport work without implementing either. Python metadata/version semantics stay in the ecosystem adapter; other ecosystems need their own semantics. Bulk metadata delivery and eligibility summaries are candidates for future experiments, not frozen network APIs or measured remote speedups.

All **9 new correctness tests** pass, covering finite-oracle agreement, backtracking, unsatisfiability, cycles/extra expansion, markers, Requires-Python, wheel tags/multiple artifacts, prereleases, constraints, cache context changes, metadata identity/tampering, relocation, custom CLI inputs and round limits. Measurements remain warm-cache and generated except for the exact original pip-reference package set. There is no claim about arbitrary real dependency-graph distributions or an Odin/native solver floor.

## Incremental scheduling follow-up

Run `20261029T001314.508192Z` reuses the **exact original snapshots, target, roots and candidate ordering**, comparing `catalog-filter-cache` with `catalog-incremental`. Both retain the same metadata and predicate caches. The new [incremental adapter](incremental.py) uses a lexical heap of pending criteria, rechecks only changed criteria after a successful pin, and removes outgoing requirement information when an existing pin is invalidated. It reuses upstream candidate validation, result construction, optimistic backjumping/rollback and full state copies from the pinned resolvelib 1.2.1. The adapted control flow retains the [upstream license](LICENSE.resolvelib).

The queue is rebuilt conservatively after backjump/rollback. This keeps state restoration simple and correct, with targeted updates on the ordinary success path. A test-only full-scan audit checks pending-set/heap invariants at every round, but is disabled in measurements. Stable lexical preference is a deliberate restriction: arbitrary state-dependent provider priorities and the separate constrained-first heuristic need additional invalidation rules and are not silently supported.

There are **12 cases and 180 randomized timed fresh processes**, each doing three fresh solves, for **540 timed solves**. Original admission costs are carried forward, not measured again. Every baseline/incremental pair selects the exact same artifacts or reports the same unsatisfiable result, including repeated solves. Input documents/pins are unchanged. [Report](results/incremental/REPORT.md), raw observations (local artifact, `results/incremental/results.json`), separate profiles (local artifact, `results/incremental/profile-data/profiles.json`).

Matched medians, ms:

| Input | Cached baseline first use | Incremental first use | Cached baseline reused solve | Incremental reused solve |
| --- | ---: | ---: | ---: | ---: |
| Original 22 wheels | 3.141 | 2.738 | 0.738 | 0.403 |
| Wide, 50 leaves | 11.900 | 8.965 | 5.965 | 1.198 |
| Wide, 250 leaves | 174.476 | 46.188 | 135.807 | 11.152 |
| Shared constraints | 44.976 | 16.616 | 35.411 | 5.653 |
| Conflicts | 5.936 | 5.424 | 2.464 | 2.336 |
| Unsatisfiable | 2.568 | 2.561 | 0.313 | 0.245 |

The wide-250 first solve itself falls from **165.978 to 36.587 ms**; including source open, first use is **3.8x faster**, and a reused-session solve is **12.2x faster**. Compare this rerun's 174.476 ms control with its 46.188 ms result rather than mixing the older 162.946 ms control from another run. The observation at the new median combined duration has 11.983 ms opening plus 34.205 ms solving, totaling exactly 46.188 ms; independent column medians need not add.

For the same 251 selected packages and 1,251 candidate checks, satisfaction callbacks fall from **63,252 to 251**. Both still perform **251 actual predicate evaluations** on the first solve. The improvement removes the surrounding cached callbacks and global rescan/selection work rather than skipping constraints. The incremental engine records **251 changed-criterion checks, 251 heap pushes/pops and one initial queue rebuild** on this conflict-free case. It makes no repeated global preference callbacks: the heap preserves the baseline's lexical choice directly. Search behavior remains unchanged on conflicts, including **48 candidate rejections** under both engines.

The gains are largest on the wide/shared cases where unchanged criteria were repeatedly revisited. Conflict-heavy and tiny inputs benefit much less because they still exercise backtracking/rebuilds or have little redundant work. This is not a blanket speedup for all graphs.

Separate warm-solve profiles confirm that current-pin/preference rescanning is no longer dominant. Remaining work includes candidate/dependency bookkeeping, source/requirement parsing/filtering on the first solve, building the final result, and full state copies: wide-250 still records **252 state copies plus 251 candidate-criteria copies**. Some copying remains quadratic in graph width. No fully linear complexity, native/Odin implementation or hardware-floor claim follows from the new timing.

The expanded **13-test suite** runs every original semantic case against the new engine, including extras, marker/target compatibility, cycles and cache context changes. Dedicated tests cover late constraints on already-pinned packages, disappearing dependencies, rejected attempts and backjump rebuilds. **Eighty seeded four-project/two-version graphs** compare exact selections/status with the reference, run a full queue-invariant audit, and check finite satisfiability against an exhaustive oracle. They exercise optimistic state restoration as well as successful backtracking. Custom CLI tests also verify that reusing saved inputs preserves constraints and results rather than silently changing the query.

The experiment remains local, warm-cache, Python, and limited to the supported named-wheel semantics. No remote transfer/repository work, payload changes, package execution or native solver is introduced. The result supports removing repeated bookkeeping before pursuing a language rewrite; reversible/compact state and deferred candidate preparation remain separate possible follow-ups.

## Reversible state follow-up

Run `20261029T002918.127435Z` compares `catalog-incremental` with `catalog-trail` on the same admitted snapshots, target, queries and lexical policy as the scheduling follow-up. There are **180 timed fresh processes and 540 fresh solves**, with 15 randomized trials per case. Source open, first solve and reused-session solves remain separate. No completed solution is cached. [Report](results/trail/REPORT.md), raw observations (local artifact, `results/trail/results.json`), [implementation](trail.py).

The new engine retains one mutable store per map. Each mutation records the prior and replacement entry; a saved map is a constant-size version handle. Switching historical branches undoes and redoes the intervening records. Ordered links preserve pin insertion order, which upstream backjumping relies on. Candidate attempts use a read-through overlay and publish only changed criteria, removing both the candidate map copy and its full-map update. Candidate validation, scheduling and upstream optimistic backjumping stay the same. The implementation deliberately keeps compatibility with the pinned upstream control flow instead of introducing a different search policy.

Matched medians, ms:

| Input | Full-copy first use | Trail first use | Full-copy reused solve | Trail reused solve |
| --- | ---: | ---: | ---: | ---: |
| original-22 | 2.616 | 2.825 | 0.449 | 0.552 |
| wide-50 | 8.387 | 8.132 | 1.146 | 1.525 |
| wide-250 | 44.541 | 37.643 | 10.360 | 6.721 |
| shared-100 | 15.801 | 18.852 | 5.095 | 6.205 |
| conflicts | 5.770 | 6.573 | 2.010 | 2.773 |
| unsatisfiable | 2.240 | 2.368 | 0.281 | 0.413 |

On wide-250, first solve alone falls from **34.655 to 28.975 ms**. First use improves by about **1.2x**, and reused solve by **1.5x**. At this size, removing copying helps but Python map/history machinery adds substantial per-operation overhead. Tiny, shared-100 and conflict-heavy cases generally regress. This is a scaling-oriented prototype, not a universal improvement or a reason to replace the default resolver for all inputs.

The wide-250 engine records **502 mutations and 504 version handles**, with **zero whole-map entries copied**, versus **157,379 entries copied** across state and candidate snapshots in the incremental control. Both still check 1,251 candidates and make 251 satisfaction callbacks. Every timed solve selects identical artifact IDs or reports the same unsatisfiable outcome. Conflict rejection counts remain unchanged, including 48 rejections on the conflict fixture.

Tests cover all prior semantics under both engines, full queue audits for both incremental schedulers, and 80 seeded graphs compared against exact baseline selections and a finite exhaustive satisfiability oracle. Optimistic rollback is exercised. A dedicated version-history test runs **1,500 operations** with branching saved versions, comparing values and insertion order against independent ordered-map copies after every step. A growth test verifies exactly two recorded mutations per selected package at three conflict-free widths. The suite now has **15 passing tests**.

Whole-map copy counters cover state snapshots, candidate copies and optimistic saved maps. They do not claim zero allocations or zero list copying: initial map construction enumerates roots, criterion-information lists are copied when new requirements arrive, backtrack-cause lists are still copied, and optimistic saves retain a list of state handles. Full pruning/queue rebuilds and incompatibility scans remain on conflict paths. Long shared constraint lists, dense graphs, historical branch replay and repeated search can still be expensive. The measured wide graphs specifically isolate the ordinary conflict-free path; no general polynomial-time or native/Odin floor claim follows.

### Conflict-free scaling

Run `20261029T003011.057447Z` uses six generated widths from 125 to 4,000 leaves, with five candidate versions per leaf. **120 randomized timed fresh processes and 360 fresh solves** compare the two engines, ten trials per case. Admission is performed once per dataset outside consumer timing. [Scaling report](results/trail-scaling/REPORT.md), lossless raw observations, gzip (local artifact, `results/trail-scaling/results.json.gz`).

Medians, ms:

| Leaves | Full-copy first solve | Trail first solve | Full-copy reused solve | Trail reused solve |
| ---: | ---: | ---: | ---: | ---: |
| 125 | 13.293 | 14.148 | 3.666 | 3.636 |
| 250 | 41.850 | 33.480 | 13.897 | 6.845 |
| 500 | 99.243 | 79.202 | 42.837 | 18.935 |
| 1000 | 306.207 | 132.153 | 151.154 | 38.657 |
| 2000 | 969.691 | 290.968 | 543.184 | 130.216 |
| 4000 | 3983.197 | 733.956 | 2170.954 | 180.466 |

At 4,000 leaves, the universe has **20,001 artifacts** and the selected closure has **4,001 packages**. First solve is **5.4x faster**, reused solve **12.0x faster**, and open plus first solve falls from **4,220.403 to 986.871 ms**. Exact selections and candidate/rejection/callback counts match at every size and pass. The 250-leaf values differ from the matched six-fixture run because these are separate observations; compare controls within their own run.

For these star-shaped inputs, the measured full-copy count is exactly **2.5L² + 4.5L + 4** entries for L leaves, versus **2(L + 1)** trail mutations and **2(L + 2)** version handles. At 4,000 leaves that is **40,018,004 copied map entries versus 8,002 mutations and 8,004 handles**. No undo/redo or conflict rebuild beyond initialization is needed. This establishes removal of the quadratic snapshot/candidate-copy work for this family.

Increasing leaves 32-fold raises reused solve time about **592x** for full copies and **50x** for the trail. That is consistent with much better growth, but it is not a proof of linear wall time: heap ordering, Python allocation/garbage collection, cache effects and normal measurement variation remain. In particular the 2,000-leaf trail timing is uneven relative to adjacent sizes. Counters establish linear mutation growth more directly than fitting an asymptotic curve to six timing points.

Separate warm-solve profiles (local artifact, `results/trail/profile-data/profiles.json`) cover wide-250, shared-100 and conflicts under both engines. Full ordered-map/dictionary snapshot copies disappear from the trail path; provider bookkeeping and the Python map/overlay machinery remain. Profiles add material overhead and are not used to partition or replace unprofiled timings.

## Naive scaling and startup follow-up

Run `20261029T004920.057772Z` measures the original `wheel-uncached` reference at 250, 1,000 and 4,000 leaves against `catalog-trail`, then compares single-use solver workers with the original offline pip startup. **138 timed fresh processes** comprise **120 startup observations** (15 per case) and **18 scaling observations** (three per case, two solves each): **66 reference-solver solves and 90 real pip CLI commands**. No extra untimed warmup is included. [Report](results/naive-startup/REPORT.md), raw observations (local artifact, `results/naive-startup/results.json`), [reproduction harness](compare_startup.py).

Original pip and solver consumers use byte-identical wheel hashes and select identical versions. Solver variants additionally match artifact IDs, snapshot and target. All repeated solves return the same selection. Solver closures are independently validated; pip retains code-origin/resource/report/backtracking checks and zero network events. No installation, producer admission or native rebuild occurs.

### Original uncached reference at scale

Medians, ms; three trials per case. These are measured ratios within this run. The second solve starts fresh resolver state; the deliberately uncached provider continues to repeat metadata/predicate work. This combines metadata/predicate caching, incremental scheduling and reversible state, rather than attributing the whole gain to the trail.

| Leaves | Naive first solve | Trail first solve | Speedup | Naive second solve | Trail second solve | Speedup |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 250 | 560.060 | 35.739 | 15.7x | 532.246 | 8.200 | 64.9x |
| 1000 | 6109.544 | 136.629 | 44.7x | 5760.525 | 35.381 | 162.8x |
| 4000 | 155592.057 | 693.914 | 224.2x | 180304.630 | 169.957 | 1060.9x |

At 4,000 leaves, **20,001 artifacts** yield **4,001 selected packages**. Source open plus first solve falls from **155.753 seconds to 956.077 ms**, about **163x**. First-solve ranges are **147.132–163.781 seconds** uncached and **685.9–723.7 ms** optimized. The expensive baseline is sampled only three times; these are not precise ecosystem-wide performance estimates.

Both engines check exactly **20,001 candidates on the first solve**, select identical artifacts, and perform no conflict backtracking on this graph. Satisfaction callbacks/evaluations fall from **16,012,002 to 4,001**; the trail records **8,002 mutations**. On the second solve the optimized session also avoids candidate filtering through its cache. The measured minutes reflect avoidable repeated work on a conflict-free graph, not inherently difficult SAT search. This uncached reference is not pip behavior, and no real-pip wide-4,000 measurement is claimed.

### Back to the original startup question

Original 22-wheel inventory, 12 selected packages; 15 trials per case. Medians, ms. Each invocation runs its consumer once. Invocation wall includes interpreter/setup, validation, output/cleanup and parent JSON result decoding. The decoder is included here, unlike the older loader harness process metric; old observations are not retroactively adjusted.

| Consumer | Input / reader | Complete invocation | Command or open + first solve | Harness/library preparation |
| --- | --- | ---: | ---: | ---: |
| Reference solver | wheel-uncached | 231.762 | 10.579 | 179.285 |
| Reference solver | catalog-trail | 234.275 | 2.828 | 188.970 |
| Real pip dry-run | source / directory | 912.570 | 730.386 | 49.166 |
| Real pip dry-run | source / python-local | 874.780 | 696.675 | 50.931 |
| Real pip dry-run | source / odin-local | 875.143 | 695.846 | 51.727 |
| Real pip dry-run | bytecode / directory | 447.811 | 275.629 | 47.945 |
| Real pip dry-run | bytecode / python-local | 429.739 | 256.331 | 50.246 |
| Real pip dry-run | bytecode / odin-local | 420.000 | 254.176 | 47.425 |

The optimized reference worker has **no visible one-shot invocation improvement** over the uncached worker on this tiny graph: both are roughly **232–234 ms**, even though open plus solve drops from **10.6 to 2.8 ms**. Common Python/library/harness imports dominate that worker. It imports measurement and fixture helpers as well as packaging/resolvelib, so this is not pure interpreter startup, a minimal production CLI, or a native runtime floor.

The bytecode pip command takes roughly **420–448 ms**, versus **875–913 ms** with source inputs. Python-local and Odin-local byte access remain close. Pip performs configuration, candidate discovery/preparation, reporting and compatibility behavior that the reference solver does not implement. Complete-invocation ratios compare these specific commands, not equivalent-feature pip replacements. Source/solve/command timing scopes differ; independent medians cannot be added or subtracted across experiments.

The earlier approximately **298 ms** result was the complete process for a **synthetic 2,072-module source-loading fixture** using a persistent archive reader; its loading/application workload was about **190 ms**, with no dependency-version solve. See the [persistent-loader report](../dependency_bundles/results/persistent/REPORT.md). The later [CPython/Odin matrix](../dependency_bundles/results/python-native/REPORT.md) introduced the real pip startup rerun here. Loading a tool, initializing a process and selecting package versions remain distinct measurements.

All **15 solver correctness tests** pass; the new harness also completed a smoke matrix and all 138 validated observations. Timing remains warm-cache and specific to the recorded execution environment. Producer admission costs remain excluded and must be included for one-use producer/consumer scenarios.

## Published Django candidate sets

Run `20261029T014900.906542Z` uses **15 actual published wheels**, three stable candidate versions for each of Django, asgiref, sqlparse, Django REST framework and django-filter. Core roots select three distributions; REST roots select five. The universe is deliberately limited to these candidates, not the complete PyPI release history. [Report](results/django/REPORT.md), raw observations (local artifact, `results/django/results.json`), [artifact provenance](results/django/provenance.json), [reproduction](README.md).

Both queries share one admitted immutable snapshot and target. Fresh offline pip dry-run reports are retained for [core](results/django/django-core-pip-reference.json) and [REST](results/django/django-rest-pip-reference.json). Every timed solve matches pip’s selected wheel SHA-256 identities, not only version labels. Fifteen randomized fresh processes per case give **90 observations and 270 fresh solves**, with two additional session-reused solves after the first. No solution is cached. Admission and pip reference validation occur outside consumer timings.

Medians, ms:

| Query | Variant | Open + first solve | Reused solve |
| --- | --- | ---: | ---: |
| django-core | wheel-uncached | 54.082 | 44.007 |
| django-core | wheel-cached | 47.325 | 0.391 |
| django-core | catalog-trail | 2.877 | 0.238 |
| django-rest | wheel-uncached | 128.773 | 121.388 |
| django-rest | wheel-cached | 52.807 | 0.708 |
| django-rest | catalog-trail | 3.609 | 0.398 |

REST first use is about **36x faster** against the uncached reference and **15x faster** against cached wheel metadata. The three/five-package graphs are easy; first-use gains are largely a metadata-delivery result rather than evidence of a harder search. Opening Django wheels parses their many ZIP entries even though the solver only needs METADATA. First-pass wheel opens fall from **25 uncached / 14 cached to zero catalog-backed** for REST, and **12 / 9 to zero** for core. Candidate/constraint semantics are unchanged; session caches remove repeated work on later solves.

The separate [Django application loading experiment](../dependency_bundles/FINDINGS.md#real-django-application) imports 392 dependency modules in core and 455 in REST using the common template adapter, out of 938/1,026 available source files. These are not hundreds of selected packages or SAT variables. Framework startup uses a frozen dependency set and does not perform resolution. Its source-to-bytecode gain is ordinary precompilation; the Odin byte provider has no consistent startup advantage over the Python sidecar in that fixture.

No selected package is installed into the host environment or executed by the solver. The separate app experiment does execute the pinned framework code. The corpus includes only pure-Python wheels; conditional Windows tzdata and unrequested optional extras are not selected on the Linux target. Dynamic metadata, source builds, arbitrary plugins and a remote candidate universe remain outside scope. Producer admission/hashing and full process/library imports remain separate from open-plus-solve. All **15 solver correctness tests** pass, and every new real-wheel observation is validated against pip artifact identities.
