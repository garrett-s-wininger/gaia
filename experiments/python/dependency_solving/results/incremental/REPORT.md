# Local dependency-solving experiment

Run: `20261029T001314.508192Z`.

Reuses admitted snapshots and target from `20261028T232923.464853Z`. Admission observations below are carried forward from that run, not measured again. Requirements/constraints/options are inherited unless explicitly overridden.

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

The reference provider eagerly enumerates candidate eligibility, including Requires-Python metadata checks. This is fixed across these variants and is not pip's exact candidate-preparation policy. Lazy candidates and compact eligibility summaries are not measured in this run.

15 interleaved fresh processes per case, 3 solves per session. Medians, ms. First-use median is computed per observation as source open + first solve. Reused is each session's mean after the first solve, then median. Validation is excluded. Metadata time is an included subset of solve time; do not add it. Callback counts are from the first solve, median across trials.

| Dataset | Variant | Status | Selected | Open ms | First solve ms | Reused solve ms | First use ms | Metadata ms | Wheel opens | Candidate checks | Satisfaction evals | Rejections |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| original-22 | catalog-filter-cache | solved | 12 | 1.192 | 1.903 | 0.738 | 3.141 | 0.023 | 0 | 28 | 13 | 1 |
| original-22 | catalog-incremental | solved | 12 | 1.316 | 1.421 | 0.403 | 2.738 | 0.020 | 0 | 28 | 13 | 1 |
| wide-50 | catalog-filter-cache | solved | 51 | 2.237 | 9.663 | 5.965 | 11.900 | 0.127 | 0 | 251 | 51 | 0 |
| wide-50 | catalog-incremental | solved | 51 | 2.335 | 6.385 | 1.198 | 8.965 | 0.156 | 0 | 251 | 51 | 0 |
| wide-250 | catalog-filter-cache | solved | 251 | 8.942 | 165.978 | 135.807 | 174.476 | 1.297 | 0 | 1251 | 251 | 0 |
| wide-250 | catalog-incremental | solved | 251 | 9.616 | 36.587 | 11.152 | 46.188 | 0.948 | 0 | 1251 | 251 | 0 |
| shared-100 | catalog-filter-cache | solved | 111 | 3.579 | 41.488 | 35.411 | 44.976 | 0.368 | 0 | 441 | 111 | 0 |
| shared-100 | catalog-incremental | solved | 111 | 4.141 | 12.408 | 5.653 | 16.616 | 0.281 | 0 | 441 | 111 | 0 |
| conflicts | catalog-filter-cache | solved | 7 | 1.369 | 4.486 | 2.464 | 5.936 | 0.069 | 0 | 106 | 22 | 48 |
| conflicts | catalog-incremental | solved | 7 | 1.285 | 3.943 | 2.336 | 5.424 | 0.063 | 0 | 106 | 22 | 48 |
| unsatisfiable | catalog-filter-cache | unsatisfiable | 0 | 1.161 | 1.325 | 0.313 | 2.568 | 0.013 | 0 | 9 | 3 | 2 |
| unsatisfiable | catalog-incremental | unsatisfiable | 0 | 1.206 | 1.115 | 0.245 | 2.561 | 0.013 | 0 | 9 | 3 | 2 |

## Scheduling work

First-solve medians. A dash means the baseline was not instrumented for that engine-specific counter. Satisfaction callbacks are counted for both variants, including cache hits. The test-only full-scan audit is disabled during timing. State-copy counts demonstrate that full snapshots remain even when ordinary full scans are removed.

| Dataset | Variant | Satisfaction callbacks | Changed-criterion checks | Queue rebuilds | State copies |
| --- | --- | ---: | ---: | ---: | ---: |
| original-22 | catalog-filter-cache | 179 | — | — | — |
| original-22 | catalog-incremental | 15 | 25 | 2 | 15 |
| wide-50 | catalog-filter-cache | 2652 | — | — | — |
| wide-50 | catalog-incremental | 51 | 51 | 1 | 52 |
| wide-250 | catalog-filter-cache | 63252 | — | — | — |
| wide-250 | catalog-incremental | 251 | 251 | 1 | 252 |
| shared-100 | catalog-filter-cache | 20622 | — | — | — |
| shared-100 | catalog-incremental | 651 | 201 | 1 | 112 |
| conflicts | catalog-filter-cache | 238 | — | — | — |
| conflicts | catalog-incremental | 69 | 104 | 13 | 35 |
| unsatisfiable | catalog-filter-cache | 24 | — | — | — |
| unsatisfiable | catalog-incremental | 6 | 8 | 2 | 10 |

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
