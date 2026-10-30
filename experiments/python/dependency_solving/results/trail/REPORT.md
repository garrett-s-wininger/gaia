# Local dependency-solving experiment

Run: `20261029T002918.127435Z`.

Reuses admitted snapshots and target from `20261029T001314.508192Z`. Admission observations below are carried forward from that run, not measured again. Requirements/constraints/options are inherited unless explicitly overridden.

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
| original-22 | catalog-incremental | solved | 12 | 1.196 | 1.367 | 0.449 | 2.616 | 0.020 | 0 | 28 | 13 | 1 |
| original-22 | catalog-trail | solved | 12 | 1.187 | 1.588 | 0.552 | 2.825 | 0.019 | 0 | 28 | 13 | 1 |
| wide-50 | catalog-incremental | solved | 51 | 2.306 | 5.522 | 1.146 | 8.387 | 0.131 | 0 | 251 | 51 | 0 |
| wide-50 | catalog-trail | solved | 51 | 2.403 | 5.608 | 1.525 | 8.132 | 0.117 | 0 | 251 | 51 | 0 |
| wide-250 | catalog-incremental | solved | 251 | 9.061 | 34.655 | 10.360 | 44.541 | 0.798 | 0 | 1251 | 251 | 0 |
| wide-250 | catalog-trail | solved | 251 | 8.367 | 28.975 | 6.721 | 37.643 | 0.715 | 0 | 1251 | 251 | 0 |
| shared-100 | catalog-incremental | solved | 111 | 3.678 | 12.025 | 5.095 | 15.801 | 0.261 | 0 | 441 | 111 | 0 |
| shared-100 | catalog-trail | solved | 111 | 3.755 | 14.831 | 6.205 | 18.852 | 0.260 | 0 | 441 | 111 | 0 |
| conflicts | catalog-incremental | solved | 7 | 1.291 | 4.192 | 2.010 | 5.770 | 0.066 | 0 | 106 | 22 | 48 |
| conflicts | catalog-trail | solved | 7 | 1.383 | 5.053 | 2.773 | 6.573 | 0.072 | 0 | 106 | 22 | 48 |
| unsatisfiable | catalog-incremental | unsatisfiable | 0 | 1.137 | 0.998 | 0.281 | 2.240 | 0.012 | 0 | 9 | 3 | 2 |
| unsatisfiable | catalog-trail | unsatisfiable | 0 | 1.135 | 1.217 | 0.413 | 2.368 | 0.012 | 0 | 9 | 3 | 2 |

## Scheduling work

First-solve medians. A dash means the baseline was not instrumented for that engine-specific counter. Satisfaction callbacks are counted for both variants, including cache hits. The test-only full-scan audit is disabled during timing. State-copy counts distinguish the incremental baseline's full snapshots from the trail's version handles.

| Dataset | Variant | Satisfaction callbacks | Changed-criterion checks | Queue rebuilds | State copies |
| --- | --- | ---: | ---: | ---: | ---: |
| original-22 | catalog-incremental | 15 | 25 | 2 | 15 |
| original-22 | catalog-trail | 15 | 25 | 2 | 0 |
| wide-50 | catalog-incremental | 51 | 51 | 1 | 52 |
| wide-50 | catalog-trail | 51 | 51 | 1 | 0 |
| wide-250 | catalog-incremental | 251 | 251 | 1 | 252 |
| wide-250 | catalog-trail | 251 | 251 | 1 | 0 |
| shared-100 | catalog-incremental | 651 | 201 | 1 | 112 |
| shared-100 | catalog-trail | 651 | 201 | 1 | 0 |
| conflicts | catalog-incremental | 69 | 104 | 13 | 35 |
| conflicts | catalog-trail | 69 | 104 | 13 | 0 |
| unsatisfiable | catalog-incremental | 6 | 8 | 2 | 10 |
| unsatisfiable | catalog-trail | 6 | 8 | 2 | 0 |

## Copy and mutation work

First-solve medians. Whole-map entries copied counts state snapshots and candidate attempts, including optimistic saves. Version handles share a reversible store. Undo/redo counts include changing between retained historical branches. Zero whole-map copies does not imply zero allocations or zero copying of lists.

| Dataset | Variant | Whole-map entries copied | Trail mutations | Version handles | Undo | Redo |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| original-22 | catalog-incremental | 403 | 0 | 0 | 0 | 0 |
| original-22 | catalog-trail | 0 | 29 | 30 | 3 | 0 |
| wide-50 | catalog-incremental | 6479 | 0 | 0 | 0 | 0 |
| wide-50 | catalog-trail | 0 | 102 | 104 | 0 | 0 |
| wide-250 | catalog-incremental | 157379 | 0 | 0 | 0 | 0 |
| wide-250 | catalog-trail | 0 | 502 | 504 | 0 | 0 |
| shared-100 | catalog-incremental | 30549 | 0 | 0 | 0 | 0 |
| shared-100 | catalog-trail | 0 | 312 | 224 | 0 | 0 |
| conflicts | catalog-incremental | 833 | 0 | 0 | 0 | 0 |
| conflicts | catalog-trail | 0 | 80 | 70 | 60 | 0 |
| unsatisfiable | catalog-incremental | 69 | 0 | 0 | 0 | 0 |
| unsatisfiable | catalog-trail | 0 | 18 | 22 | 12 | 0 |

## Admission and input size

One producer/admission observation per dataset; buffered writes, no fsync. Admission is not charged to every solve; one-shot use must add it back. Both inventory and catalog store local paths for this prototype. Raw package bytes are unchanged.

| Dataset | Projects | Artifacts | Artifact bytes | Raw METADATA bytes | Inventory bytes | Catalog bytes | Admission ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| original-22 | 12 | 22 | 13,069 | 1,547 | 10,353 | 12,759 | 9.466 |
| wide-50 | 51 | 251 | 152,867 | 16,102 | 119,369 | 146,615 | 70.020 |
| wide-250 | 251 | 1251 | 762,067 | 80,302 | 595,620 | 731,466 | 347.976 |
| shared-100 | 111 | 441 | 296,121 | 45,714 | 215,988 | 275,526 | 112.140 |
| conflicts | 7 | 22 | 13,220 | 1,836 | 10,350 | 12,914 | 7.237 |
| unsatisfiable | 4 | 5 | 3,034 | 399 | 2,519 | 3,096 | 3.035 |

## Interpretation limits

Generated graphs provide controlled breadth, shared constraints, conflicts and unsatisfiability; they are not evidence of real-world solve-time distributions. original-22 preserves the earlier pip package set and expected selection. All unmodified-order variants must return identical artifact selections; heuristic results must satisfy the same closure but may differ. Unsatisfiable results are resolver outcomes, not independent general unsat proofs; small correctness cases have additional finite-oracle coverage. A round limit is reported as incomplete, never unsat. The engine/provider remain Python; these measurements do not establish an Odin/native solver floor. Matched end-to-end pip comparisons are a separate experiment. The next source/backend can implement the same candidate/metadata semantics without changing the constraint engine.
