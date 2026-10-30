# Local dependency-solving experiment

Run: `20261029T003011.057447Z`.

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

10 interleaved fresh processes per case, 3 solves per session. Medians, ms. First-use median is computed per observation as source open + first solve. Reused is each session's mean after the first solve, then median. Validation is excluded. Metadata time is an included subset of solve time; do not add it. Callback counts are from the first solve, median across trials.

| Dataset | Variant | Status | Selected | Open ms | First solve ms | Reused solve ms | First use ms | Metadata ms | Wheel opens | Candidate checks | Satisfaction evals | Rejections |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| wide-125 | catalog-incremental | solved | 126 | 4.984 | 13.293 | 3.666 | 18.233 | 0.416 | 0 | 626 | 126 | 0 |
| wide-125 | catalog-trail | solved | 126 | 5.445 | 14.148 | 3.636 | 20.356 | 0.386 | 0 | 626 | 126 | 0 |
| wide-250 | catalog-incremental | solved | 251 | 8.670 | 41.850 | 13.897 | 51.103 | 1.041 | 0 | 1251 | 251 | 0 |
| wide-250 | catalog-trail | solved | 251 | 9.187 | 33.480 | 6.845 | 42.116 | 0.825 | 0 | 1251 | 251 | 0 |
| wide-500 | catalog-incremental | solved | 501 | 20.717 | 99.243 | 42.837 | 123.903 | 2.477 | 0 | 2501 | 501 | 0 |
| wide-500 | catalog-trail | solved | 501 | 21.819 | 79.202 | 18.935 | 102.326 | 2.760 | 0 | 2501 | 501 | 0 |
| wide-1000 | catalog-incremental | solved | 1001 | 42.820 | 306.207 | 151.154 | 356.591 | 6.513 | 0 | 5001 | 1001 | 0 |
| wide-1000 | catalog-trail | solved | 1001 | 45.937 | 132.153 | 38.657 | 178.771 | 5.026 | 0 | 5001 | 1001 | 0 |
| wide-2000 | catalog-incremental | solved | 2001 | 100.166 | 969.691 | 543.184 | 1067.392 | 12.055 | 0 | 10001 | 2001 | 0 |
| wide-2000 | catalog-trail | solved | 2001 | 95.476 | 290.968 | 130.216 | 384.840 | 11.224 | 0 | 10001 | 2001 | 0 |
| wide-4000 | catalog-incremental | solved | 4001 | 245.650 | 3983.197 | 2170.954 | 4220.403 | 27.259 | 0 | 20001 | 4001 | 0 |
| wide-4000 | catalog-trail | solved | 4001 | 249.902 | 733.956 | 180.466 | 986.871 | 24.076 | 0 | 20001 | 4001 | 0 |

## Scheduling work

First-solve medians. A dash means the baseline was not instrumented for that engine-specific counter. Satisfaction callbacks are counted for both variants, including cache hits. The test-only full-scan audit is disabled during timing. State-copy counts distinguish the incremental baseline's full snapshots from the trail's version handles.

| Dataset | Variant | Satisfaction callbacks | Changed-criterion checks | Queue rebuilds | State copies |
| --- | --- | ---: | ---: | ---: | ---: |
| wide-125 | catalog-incremental | 126 | 126 | 1 | 127 |
| wide-125 | catalog-trail | 126 | 126 | 1 | 0 |
| wide-250 | catalog-incremental | 251 | 251 | 1 | 252 |
| wide-250 | catalog-trail | 251 | 251 | 1 | 0 |
| wide-500 | catalog-incremental | 501 | 501 | 1 | 502 |
| wide-500 | catalog-trail | 501 | 501 | 1 | 0 |
| wide-1000 | catalog-incremental | 1001 | 1001 | 1 | 1002 |
| wide-1000 | catalog-trail | 1001 | 1001 | 1 | 0 |
| wide-2000 | catalog-incremental | 2001 | 2001 | 1 | 2002 |
| wide-2000 | catalog-trail | 2001 | 2001 | 1 | 0 |
| wide-4000 | catalog-incremental | 4001 | 4001 | 1 | 4002 |
| wide-4000 | catalog-trail | 4001 | 4001 | 1 | 0 |

## Copy and mutation work

First-solve medians. Whole-map entries copied counts state snapshots and candidate attempts, including optimistic saves. Version handles share a reversible store. Undo/redo counts include changing between retained historical branches. Zero whole-map copies does not imply zero allocations or zero copying of lists.

| Dataset | Variant | Whole-map entries copied | Trail mutations | Version handles | Undo | Redo |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| wide-125 | catalog-incremental | 39629 | 0 | 0 | 0 | 0 |
| wide-125 | catalog-trail | 0 | 252 | 254 | 0 | 0 |
| wide-250 | catalog-incremental | 157379 | 0 | 0 | 0 | 0 |
| wide-250 | catalog-trail | 0 | 502 | 504 | 0 | 0 |
| wide-500 | catalog-incremental | 627254 | 0 | 0 | 0 | 0 |
| wide-500 | catalog-trail | 0 | 1002 | 1004 | 0 | 0 |
| wide-1000 | catalog-incremental | 2.5045e+06 | 0 | 0 | 0 | 0 |
| wide-1000 | catalog-trail | 0 | 2002 | 2004 | 0 | 0 |
| wide-2000 | catalog-incremental | 1.0009e+07 | 0 | 0 | 0 | 0 |
| wide-2000 | catalog-trail | 0 | 4002 | 4004 | 0 | 0 |
| wide-4000 | catalog-incremental | 4.0018e+07 | 0 | 0 | 0 | 0 |
| wide-4000 | catalog-trail | 0 | 8002 | 8004 | 0 | 0 |

## Admission and input size

One producer/admission observation per dataset; buffered writes, no fsync. Admission is not charged to every solve; one-shot use must add it back. Both inventory and catalog store local paths for this prototype. Raw package bytes are unchanged.

| Dataset | Projects | Artifacts | Artifact bytes | Raw METADATA bytes | Inventory bytes | Catalog bytes | Admission ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| wide-125 | 126 | 626 | 381,317 | 40,177 | 298,120 | 366,091 | 139.070 |
| wide-250 | 251 | 1251 | 762,067 | 80,302 | 595,620 | 731,466 | 344.830 |
| wide-500 | 501 | 2501 | 1,523,567 | 160,552 | 1,190,620 | 1,462,216 | 704.654 |
| wide-1000 | 1001 | 5001 | 3,046,567 | 321,052 | 2,385,621 | 2,928,717 | 1294.133 |
| wide-2000 | 2001 | 10001 | 6,092,567 | 642,052 | 4,770,621 | 5,856,717 | 4132.377 |
| wide-4000 | 4001 | 20001 | 12,184,567 | 1,284,052 | 9,540,621 | 11,712,717 | 4713.145 |

## Interpretation limits

Generated graphs provide controlled breadth, shared constraints, conflicts and unsatisfiability; they are not evidence of real-world solve-time distributions. original-22 preserves the earlier pip package set and expected selection. All unmodified-order variants must return identical artifact selections; heuristic results must satisfy the same closure but may differ. Unsatisfiable results are resolver outcomes, not independent general unsat proofs; small correctness cases have additional finite-oracle coverage. A round limit is reported as incomplete, never unsat. The engine/provider remain Python; these measurements do not establish an Odin/native solver floor. Matched end-to-end pip comparisons are a separate experiment. The next source/backend can implement the same candidate/metadata semantics without changing the constraint engine.
