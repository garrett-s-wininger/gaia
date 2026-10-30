# Python dependency resolution: review

**Conclusion:** certified bulk metadata and query-scoped caches remove substantial avoidable work. Incremental scheduling and reversible state remove repeated full scans/map copies on the measured conflict-free graphs. This is a local Python reference provider, not pip's complete behavior or a claim that dependency search has become linear in general.

The consumer selects Python wheel identities from an immutable finite inventory with explicit target, roots, constraints and policy. It does not install packages, execute builds or fetch remote candidates. Resolving versions is separate from importing hundreds of framework modules.

## Results to assess

| Finding | Evidence | Practical limit |
| --- | --- | --- |
| Metadata delivery and predicate caching dominate early easy cases | [Initial comparison](../../experiments/python/dependency_solving/results/initial/REPORT.md) | The uncached provider intentionally repeats work; it is not pip's cache policy. Admission is separately charged. |
| Incremental scheduling avoids repeated global checks | [Scheduler comparison](../../experiments/python/dependency_solving/results/incremental/REPORT.md) | Lexical policy is fixed; the implementation uses pinned private resolvelib 1.2.1 internals. |
| Reversible state replaces quadratic snapshot copying | [Trail comparison](../../experiments/python/dependency_solving/results/trail/REPORT.md), [scaling](../../experiments/python/dependency_solving/results/trail-scaling/REPORT.md) | At 4,000 conflict-free leaves, full-copy reused solve 2,171 ms → trail 180 ms. Counters establish removed copying, not a general search complexity bound. |
| The naive reference can be enormously slower without being SAT-hard | [Naive/startup comparison](../../experiments/python/dependency_solving/results/naive-startup/REPORT.md) | 4,000-leaf reused solve 180 s → 170 ms combines optimizations; only three expensive baseline samples, no real-pip large-graph comparison. |
| Tiny solve gains need not improve full process startup | [Same startup comparison](../../experiments/python/dependency_solving/results/naive-startup/REPORT.md) | Reference worker stays about 232–234 ms as open+solve falls 10.6 → 2.8 ms; imports/harness dominate. It is not an equivalent-feature pip CLI. |
| Real published candidates validate metadata delivery | [Django candidates](../../experiments/python/dependency_solving/results/django/REPORT.md) | REST open+first solve 52.8 ms cached-wheel → 3.6 ms catalog/trail. Only 15 candidate wheels/five selected distributions; wheel hashes match offline pip. |

## Reproduction and implementation map

Use the [experiment README](../../experiments/python/dependency_solving/README.md) for synthetic/custom-wheel commands and retained-input comparisons. [solver.py](../../experiments/python/dependency_solving/solver.py) owns source/admission/target/cache semantics, [incremental.py](../../experiments/python/dependency_solving/incremental.py) owns dirty scheduling, and [trail.py](../../experiments/python/dependency_solving/trail.py) owns reversible map state. [Tests](../../experiments/python/dependency_solving/test_solver.py), [scheduler tests](../../experiments/python/dependency_solving/test_incremental.py) and [trail tests](../../experiments/python/dependency_solving/test_trail.py) include differential/finite-oracle cases and rollback coverage. Upstream-derived code retains [resolvelib's license](../../experiments/python/dependency_solving/LICENSE.resolvelib).

The large scaling raw file is retained as lossless gzip (local artifact, `../../experiments/python/dependency_solving/results/trail-scaling/results.json.gz`). Decompress to JSON before passing it to scripts. Generate fresh inputs using the [reproduction guide](../../experiments/reproducing.md); saved commands are observations from the original run.

## Review boundaries

Compare wheel-cached metadata with catalog metadata separately from scheduling/trail changes. Ordering heuristics may select a different valid solution and must not be attributed to storage. Fresh solves reuse metadata/predicates within an immutable session, not a completed solution. Successful closures are independently checked; a round limit is incomplete, never unsatisfiable. General unsatisfiability is not independently certified beyond finite-oracle fixtures.

Artifact delivery must later verify full selected wheel bytes; solving uses certified metadata and does not deliver payloads. Dynamic metadata/source builds, arbitrary pip configuration, installed-state preference and a remote candidate universe remain outside scope. Cache identity includes snapshot/target/policy; changing the universe requires a new session.

Read [follow-up IDs PY-RES-01 through PY-RES-04](follow-up.md) before reopening this track. No Odin solver floor or network protocol has been established.
