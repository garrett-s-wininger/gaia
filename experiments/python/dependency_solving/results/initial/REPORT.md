# Local dependency-solving experiment

Run: `20261028T232923.464853Z`.

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

The reference provider eagerly enumerates candidate eligibility, including Requires-Python metadata checks. This is fixed across these variants and is not pip's exact candidate-preparation policy. Lazy candidates and compact eligibility summaries are not measured in this run.

15 interleaved fresh processes per case, 3 solves per session. Medians, ms. First-use median is computed per observation as source open + first solve. Reused is each session's mean after the first solve, then median. Validation is excluded. Metadata time is an included subset of solve time; do not add it. Callback counts are from the first solve, median across trials.

| Dataset | Variant | Status | Selected | Open ms | First solve ms | Reused solve ms | First use ms | Metadata ms | Wheel opens | Candidate checks | Satisfaction evals | Rejections |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| original-22 | wheel-uncached | solved | 12 | 1.159 | 8.864 | 6.769 | 10.182 | 6.197 | 39 | 30 | 179 | 1 |
| original-22 | wheel-cached | solved | 12 | 1.172 | 6.768 | 1.436 | 8.008 | 3.838 | 22 | 30 | 179 | 1 |
| original-22 | catalog | solved | 12 | 1.201 | 1.991 | 1.297 | 3.213 | 0.021 | 0 | 30 | 179 | 1 |
| original-22 | catalog-filter-cache | solved | 12 | 1.174 | 1.703 | 0.692 | 2.887 | 0.021 | 0 | 28 | 13 | 1 |
| original-22 | catalog-constrained-first | solved | 12 | 1.176 | 1.618 | 0.607 | 2.791 | 0.019 | 0 | 24 | 12 | 1 |
| wide-50 | wheel-uncached | solved | 51 | 1.770 | 53.143 | 55.264 | 54.939 | 33.872 | 302 | 251 | 2652 | 0 |
| wide-50 | wheel-cached | solved | 51 | 1.921 | 46.424 | 14.230 | 48.430 | 27.865 | 251 | 251 | 2652 | 0 |
| wide-50 | catalog | solved | 51 | 2.315 | 15.658 | 13.448 | 18.398 | 0.135 | 0 | 251 | 2652 | 0 |
| wide-50 | catalog-filter-cache | solved | 51 | 2.209 | 10.273 | 5.605 | 12.776 | 0.142 | 0 | 251 | 51 | 0 |
| wide-50 | catalog-constrained-first | solved | 51 | 2.343 | 10.411 | 6.130 | 12.476 | 0.131 | 0 | 251 | 51 | 0 |
| wide-250 | wheel-uncached | solved | 251 | 7.414 | 519.431 | 509.266 | 526.047 | 191.478 | 1502 | 1251 | 63252 | 0 |
| wide-250 | wheel-cached | solved | 251 | 6.719 | 461.974 | 290.661 | 468.692 | 136.140 | 1251 | 1251 | 63252 | 0 |
| wide-250 | catalog | solved | 251 | 8.319 | 294.443 | 282.577 | 303.817 | 1.055 | 0 | 1251 | 63252 | 0 |
| wide-250 | catalog-filter-cache | solved | 251 | 8.883 | 154.021 | 129.850 | 162.946 | 1.038 | 0 | 1251 | 251 | 0 |
| wide-250 | catalog-constrained-first | solved | 251 | 8.424 | 158.208 | 134.374 | 166.179 | 0.991 | 0 | 1251 | 251 | 0 |
| shared-100 | wheel-uncached | solved | 111 | 2.947 | 220.174 | 220.693 | 222.904 | 111.351 | 912 | 801 | 20622 | 0 |
| shared-100 | wheel-cached | solved | 111 | 3.043 | 146.230 | 93.000 | 150.492 | 49.216 | 441 | 801 | 20622 | 0 |
| shared-100 | catalog | solved | 111 | 3.940 | 93.101 | 86.337 | 97.141 | 0.526 | 0 | 801 | 20622 | 0 |
| shared-100 | catalog-filter-cache | solved | 111 | 4.109 | 38.891 | 32.695 | 42.834 | 0.297 | 0 | 441 | 111 | 0 |
| shared-100 | catalog-constrained-first | solved | 111 | 3.575 | 38.913 | 33.176 | 42.945 | 0.291 | 0 | 441 | 111 | 0 |
| conflicts | wheel-uncached | solved | 7 | 1.135 | 31.979 | 29.646 | 33.114 | 21.394 | 173 | 358 | 238 | 48 |
| conflicts | wheel-cached | solved | 7 | 1.165 | 11.103 | 5.549 | 12.318 | 4.512 | 22 | 358 | 238 | 48 |
| conflicts | catalog | solved | 7 | 1.272 | 5.900 | 5.356 | 7.407 | 0.080 | 0 | 358 | 238 | 48 |
| conflicts | catalog-filter-cache | solved | 7 | 1.195 | 4.733 | 2.337 | 5.967 | 0.067 | 0 | 106 | 22 | 48 |
| conflicts | catalog-constrained-first | solved | 7 | 1.189 | 1.473 | 0.571 | 2.681 | 0.020 | 0 | 34 | 7 | 12 |
| unsatisfiable | wheel-uncached | unsatisfiable | 0 | 1.127 | 5.560 | 3.229 | 6.611 | 4.168 | 20 | 16 | 24 | 2 |
| unsatisfiable | wheel-cached | unsatisfiable | 0 | 1.281 | 3.597 | 0.477 | 4.878 | 2.423 | 4 | 16 | 24 | 2 |
| unsatisfiable | catalog | unsatisfiable | 0 | 1.109 | 1.088 | 0.504 | 2.282 | 0.013 | 0 | 16 | 24 | 2 |
| unsatisfiable | catalog-filter-cache | unsatisfiable | 0 | 1.189 | 1.124 | 0.304 | 2.502 | 0.012 | 0 | 9 | 3 | 2 |
| unsatisfiable | catalog-constrained-first | unsatisfiable | 0 | 1.203 | 0.937 | 0.325 | 2.121 | 0.011 | 0 | 9 | 3 | 2 |

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
