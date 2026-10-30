# Local dependency-solving experiment

Run: `20261029T014900.906542Z`.

Reuses admitted snapshots and target from `20261029T014857.351840Z`. Admission observations below are carried forward from that run, not measured again. Requirements/constraints/options are inherited unless explicitly overridden.

Same admitted wheel set, target, requirements, ordering policy and resolvelib version within each storage/cache comparison. No pip CLI, network, installation, candidate-package code execution or remote service. Python packaging/resolvelib imports are prepared before solve timing; their bootstrap and complete process wall remain in raw observations. Warm filesystem cache, new process/session per trial; subsequent solves reuse the immutable session, not a saved solution.

## Contract and semantics

Admission hashes wheel bytes, validates filename/metadata identities and named requirements, and writes pinned inventory/catalog documents. Both carry the same content-derived snapshot ID; local artifact paths are excluded from that identity. Sources expose list_candidates(name) and metadata(artifact_id). Solving needs certified metadata only; full artifact delivery/hash verification is a later operation. The JSON encoding is experimental, not a transport protocol.

Named PEP 508 requirements, version constraints, extras/extra markers, target environment markers, Requires-Python, compatible wheel tags and explicit prerelease policy are supported. Source builds, direct URL/VCS requirements, installed-state preference, yanked data, pip config/index semantics and remote retrieval are excluded. This is a reference provider, not a drop-in pip replacement. Candidates prefer latest version/build, compatible tag priority, then stable artifact ID. Cache keys include snapshot, target, prerelease policy, requirements and incompatibilities; parsed data is scoped to a session. Selected closures are independently revalidated outside solve timing.

## Variants

- wheel-uncached: reopen/read/parse certified METADATA on each request, reparse requirements.
- wheel-cached: lazy metadata and parsed requirement/specifier caches; realistic reuse control.
- catalog: one admitted metadata table; same lazy parsed-object caches and lexical solver order.
- catalog-filter-cache: deduplicate repeated predicates, memoize complete candidate filters, and cache repeated requirement/candidate satisfaction checks within the immutable session.
- catalog-constrained-first: additionally prefer the smallest known candidate set. This changes decision order and can change which valid solution is found; it is not a storage-only comparison.

- catalog-incremental: same catalog/caches and lexical candidate/criterion order as catalog-filter-cache; replace full satisfaction/preference scans with a dirty-criterion heap. Reuse upstream candidate validation/backjumping and rebuild the heap conservatively on rollback. Full state/criteria copies remain; this is not a fully linear or native solver.

- catalog-trail: same incremental scheduler and candidate policy; saved maps are version handles into reversible mutation histories, and candidate attempts use small overlays. Backtracking replays mutations rather than copying full maps. Global scans on conflict, criterion information lists and backtrack-cause lists remain.

The reference provider eagerly enumerates candidate eligibility, including Requires-Python metadata checks. This is fixed across these variants and is not pip's exact candidate-preparation policy. Lazy candidates and compact eligibility summaries are not measured in this run.

15 interleaved fresh processes per case, 3 solves per session. Medians, ms. First-use median is computed per observation as source open + first solve. Reused is each session's mean after the first solve, then median. Validation is excluded. Metadata time is an included subset of solve time; do not add it. Callback counts are from the first solve, median across trials.

| Dataset | Variant | Status | Selected | Open ms | First solve ms | Reused solve ms | First use ms | Metadata ms | Wheel opens | Candidate checks | Satisfaction evals | Rejections |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| django-core | wheel-uncached | solved | 3 | 1.161 | 52.800 | 44.007 | 54.082 | 50.591 | 12 | 9 | 12 | 0 |
| django-core | wheel-cached | solved | 3 | 1.211 | 45.572 | 0.391 | 47.325 | 43.673 | 9 | 9 | 12 | 0 |
| django-core | catalog-trail | solved | 3 | 1.281 | 1.459 | 0.238 | 2.877 | 0.010 | 0 | 9 | 3 | 0 |
| django-rest | wheel-uncached | solved | 5 | 1.136 | 127.215 | 121.388 | 128.773 | 123.384 | 25 | 21 | 40 | 0 |
| django-rest | wheel-cached | solved | 5 | 1.233 | 51.191 | 0.708 | 52.807 | 48.094 | 14 | 21 | 40 | 0 |
| django-rest | catalog-trail | solved | 5 | 1.256 | 2.275 | 0.398 | 3.609 | 0.017 | 0 | 21 | 7 | 0 |

## Scheduling work

First-solve medians. A dash means the baseline was not instrumented for that engine-specific counter. Satisfaction callbacks are counted for both variants, including cache hits. The test-only full-scan audit is disabled during timing. State-copy counts distinguish the incremental baseline's full snapshots from the trail's version handles.

| Dataset | Variant | Satisfaction callbacks | Changed-criterion checks | Queue rebuilds | State copies |
| --- | --- | ---: | ---: | ---: | ---: |
| django-core | wheel-uncached | 12 | — | — | — |
| django-core | wheel-cached | 12 | — | — | — |
| django-core | catalog-trail | 3 | 3 | 1 | 0 |
| django-rest | wheel-uncached | 40 | — | — | — |
| django-rest | wheel-cached | 40 | — | — | — |
| django-rest | catalog-trail | 10 | 7 | 1 | 0 |

## Copy and mutation work

First-solve medians. Whole-map entries copied counts state snapshots and candidate attempts, including optimistic saves. Version handles share a reversible store. Undo/redo counts include changing between retained historical branches. Zero whole-map copies does not imply zero allocations or zero copying of lists.

| Dataset | Variant | Whole-map entries copied | Trail mutations | Version handles | Undo | Redo |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| django-core | catalog-trail | 0 | 6 | 8 | 0 | 0 |
| django-rest | catalog-trail | 0 | 12 | 12 | 0 | 0 |

## Admission and input size

One producer/admission observation per dataset; buffered writes, no fsync. Admission is not charged to every solve; one-shot use must add it back. Both inventory and catalog store local paths for this prototype. Raw package bytes are unchanged.

| Dataset | Projects | Artifacts | Artifact bytes | Raw METADATA bytes | Inventory bytes | Catalog bytes | Admission ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| django-core | 5 | 15 | 28,469,845 | 97,277 | 7,059 | 10,073 | 115.393 |
| django-rest | 5 | 15 | 28,469,845 | 97,277 | 7,059 | 10,073 | 115.393 |

## Interpretation limits

Generated graphs provide controlled breadth, shared constraints, conflicts and unsatisfiability; they are not evidence of real-world solve-time distributions. original-22 preserves the earlier pip package set and expected selection. All unmodified-order variants must return identical artifact selections; heuristic results must satisfy the same closure but may differ. Unsatisfiable results are resolver outcomes, not independent general unsat proofs; small correctness cases have additional finite-oracle coverage. A round limit is reported as incomplete, never unsat. The engine/provider remain Python; these measurements do not establish an Odin/native solver floor. Matched end-to-end pip comparisons are a separate experiment. The next source/backend can implement the same candidate/metadata semantics without changing the constraint engine.
