# Python dependency resolution

For human review, start with the [consolidated review](../../../research/python/resolution.md), [evidence register](../../../research/python/experiments.json), and [follow-up queue](../../../research/python/follow-up.md). Historical paths remain valid through the aliases described in the [experiment guide](../../README.md). Instructions below reproduce individual stages.


Measure metadata delivery, parsing and repeated constraint work separately from Python/pip startup. This is a local reference experiment over an immutable finite wheel inventory. It does not install, download, build packages, serve an artifact repository or implement a network protocol.

The Python provider uses the same pinned `packaging` and `resolvelib` libraries across cases, loaded from the interpreter's bundled pip wheel. It does not execute pip's CLI. Native components in the broader project remain Odin; no native constraint solver is claimed here.

```sh
python3 -B experiments/python/dependency_solving/benchmark.py
python3 -B -m unittest discover -s experiments/python/dependency_solving -v
```

Default cases preserve the original 22-wheel set, add wide graphs with 50/250 leaves and five versions each, shared-dependency fan-in, conflicts, and an unsatisfiable graph. Fifteen randomized fresh processes per case each perform three fresh solves through the same session. Later passes reuse metadata/parsed predicates, not a saved solution. Warm filesystem caches are explicit; cold storage is not tested. Source admission and consumer opening are separately recorded. Complete process wall and Python/library bootstrap are retained, while solve clocks exclude bootstrap and independent result validation.

For a smoke run, use `--trials 1 --output /tmp/gaia-solving-smoke`. Choose a new output directory to preserve a separate run. Inputs and worker requests are retained in ignored `_work/` directories.

## Use another package set

```sh
python3 -B experiments/python/dependency_solving/benchmark.py --wheelhouse /path/to/wheels --requirement 'project[extra]>=1' --constraint 'dependency<3' --output /tmp/my-solve
```

`--requirement` and `--constraint` repeat. `--requirements file.txt` accepts one named PEP 508 requirement per nonblank/noncomment line, not pip command-line directives. All variants use the same admitted package set. Invalid/missing local directories fail; an empty inventory is valid and can produce an empty solution or unsatisfiability.

The default target is the current interpreter's complete marker environment and ordered compatible tags. `--target target.json` accepts `{"environment": {...}, "tags": ["py3-none-any", ...]}` with a complete string-valued PEP 508 environment. `python_version` and `python_full_version` must agree; tags are supplied in preference order. `--prereleases` allows prereleases globally; an explicit prerelease requirement also enables them for that criterion. The default does not automatically fall back to prereleases when only prereleases exist.

Supported behavior includes normalized project names, PEP 440 versions/specifiers, constraints, extras and extra-expansion cycles, environment/extra markers, Requires-Python, compatible wheel tags and multiple artifacts. Unknown requested extras add no undeclared dependencies. The reference policy prefers latest version/build, best compatible tag rank and then artifact ID. This is a documented local policy, not a promise to duplicate every pip tie-break. Source distributions/build hooks, direct URL/VCS requirements, yanked index information, installed-state preference and pip index/config semantics are excluded or explicitly rejected. No artifact/package Python code executes.

## What changes between variants

1. `wheel-uncached` reads and parses certified METADATA for every request. This exposes repeated-work cost; it is not presented as pip's caching behavior.
2. `wheel-cached` caches metadata and parsed requirements/specifiers lazily. It is the meaningful session-reuse storage control.
3. `catalog` reads an admitted metadata table once, retaining the same solver and lexical decision order.
4. `catalog-filter-cache` also deduplicates candidate predicates, memoizes filtered candidates, and caches requirement/candidate satisfaction results.
5. `catalog-constrained-first` additionally prefers the smallest known candidate set. This changes solver decision order, can select a different valid solution on ambiguous inputs, and is reported separately from storage improvements.
6. `catalog-incremental` keeps the same lexical order and caches as `catalog-filter-cache`, using a dirty-criterion heap and upstream candidate validation/backjumping. The queue is rebuilt after rollback; ordinary success checks only affected criteria. Full state/criteria copies remain. It uses pinned private resolvelib 1.2.1 internals and deliberately rejects the state-dependent constrained-first policy.
7. `catalog-trail` keeps that scheduler and policy, replacing full map snapshots with constant-size version handles over reversible mutations. Candidate attempts read through a small overlay and publish only changed entries. Rollback can undo and redo retained branches, preserving pin insertion order. It still scans globally on conflicts and copies criterion-information/backtrack-cause lists.

The reference provider currently enumerates eligible candidates eagerly and checks each candidate's Requires-Python metadata. Pip can use different lazy-candidate/metadata policies. These are controlled provider/cache comparisons, not a recreation of pip's exact wheel-access behavior. Candidate summaries carrying eligibility fields and lazy candidate preparation are additional experiments, not measured gains here.

Compare incremental scheduling with the cached baseline on exactly the original admitted inputs:

```sh
python3 -B experiments/python/dependency_solving/benchmark.py --inputs experiments/python/dependency_solving/_work/runs/initial/results.json --variants catalog-filter-cache catalog-incremental --output experiments/python/dependency_solving/_work/runs/incremental
```

`--inputs` reuses the original snapshot digests, target, roots, constraints, prerelease policy and round limit; it does not readmit/recreate artifacts. Explicit query-option overrides remain possible. Original admission observations are carried forward and labeled as producer costs. `--variants` can select a subset of controls. With no `--inputs`, custom wheel directories and generated inputs still work. Each query creates new resolver state; caches do not reuse a completed plan.

The incremental adapter's resolve-loop/control-flow derives from resolvelib and retains its [upstream license](LICENSE.resolvelib). It applies only to the stable lexical policy owned by this reference provider. Tests compare dirty-set state with a full criterion scan on each round, and differential/finite-oracle cases cover late constraints, disappearing dependencies, cycles, backjumps and optimistic state restoration. This is a Python scheduling experiment, not a native solver or a generic plug-in for arbitrary dynamic provider priorities.

Compare full copies with reversible state on the same original inputs, then measure increasing graph sizes:

```sh
python3 -B experiments/python/dependency_solving/benchmark.py --inputs experiments/python/dependency_solving/_work/runs/incremental/results.json --variants catalog-incremental catalog-trail --output experiments/python/dependency_solving/_work/runs/trail
python3 -B experiments/python/dependency_solving/benchmark.py --wide-sizes 125 250 500 1000 2000 4000 --variants catalog-incremental catalog-trail --trials 10 --output experiments/python/dependency_solving/_work/runs/trail-scaling
gzip --keep --no-name experiments/python/dependency_solving/_work/runs/trail-scaling/results.json
```

`--wide-sizes` generates only the named wide graphs with five versions per leaf, using the same admission/provider path as other inputs. Solver code does not recognize graph shapes. Work counters distinguish whole-map entries copied, constant-size version handles, mutation records and undo/redo operations; timings retain all allocations and state disposal. These are controlled conflict-free scaling cases, not a general complexity guarantee. The trail tests additionally compare 1,500 branching-map operations against independent ordered-map snapshots.

The scaling run's repetitive raw JSON is archived losslessly as `results.json.gz`; its uncompressed working copy is ignored. Decompress that archive to a JSON file before using it with `--inputs` or other JSON readers. Timing and correctness observations are unchanged by archival.

Measure the original uncached control at 250/1,000/4,000 leaves and compare one-shot startup with the original offline pip command:

```sh
python3 -B experiments/python/dependency_solving/compare_startup.py
```

This reuses existing snapshots and loader inputs, verifies original wheel bytes across pip/solver consumers, then runs 15 randomized startup trials per case and three scaling trials per case. Each startup worker solves once; each scaling worker solves twice. The large uncached control can take minutes per process, so it uses a 900-second worker timeout and checkpoints observations/reports after every process. `--widths`, `--startup-trials`, `--scaling-trials`, `--timeout` and `--output` can narrow or relocate a run. No producer/native rebuild or install occurs. The smaller solver does not implement all pip command behavior; compare matching timing boundaries and read the limitations before interpreting process ratios. The startup worker's one-pass mode is available only through `benchmark.py --worker`; normal multi-pass benchmarks still require at least two passes.

The real [Django follow-up](results/django/REPORT.md) uses 15 published wheels: three candidate versions each of Django, asgiref, sqlparse, Django REST framework and django-filter. Fetch the pinned corpus with the [loader reproduction instructions](../dependency_bundles/README.md#real-django-application), then run:

```sh
python3 -B experiments/python/dependency_solving/django_benchmark.py
```

The driver admits the corpus once, checks fresh offline pip reports, and compares uncached wheel metadata, cached wheel metadata and the catalog/trail engine on core and REST root queries. Every timed selected artifact ID must match pip's wheel hash. All runs reuse one immutable target/snapshot. Fifteen fresh processes per case each solve three times: 90 observations, 270 solves. Source/bytecode application startup is [measured separately](../dependency_bundles/results/django/REPORT.md); three/five selected distributions do not imply hundreds of solver variables merely because the framework imports hundreds of modules. The candidate universe is deliberately limited to these 15 published wheels, not all PyPI releases.

Full filter keys include snapshot, target, prerelease policy, requirements and incompatibilities. Satisfaction keys retain the requirement object and candidate within a fixed snapshot/target session, preventing object-ID reuse. Parsed data and caches are session-scoped. Every solve creates new resolver state and independently validates a successful closure outside timing. The session is for an immutable snapshot; it does not watch or silently incorporate wheel mutations. Cache sizes are reported; no eviction policy is standardized.

Small satisfiable/unsatisfiable tests use a finite exhaustive oracle. Other unsatisfiable results are resolver outcomes, not independent general unsat certificates. A round limit is incomplete and is never labeled unsatisfiable. Every variant except `catalog-constrained-first` must select identical artifacts on a fixed input; heuristic results must satisfy the same requirements, although their choices may differ.

## Input boundary, not yet a remote protocol

[solver.py](solver.py) separates `Source.list_candidates(name)` and `Source.metadata(artifact_id)` from the resolver. Admission streams full artifact hashes, checks metadata identity/semantics, and emits pinned inventory/catalog documents with a content-derived snapshot identity. Local artifact paths are excluded from snapshot identity, so copying the same wheels preserves it. The consumer validates the admitted document digest. Wheel-backed sources also check returned METADATA against its admitted hash; catalog sources need no artifact ZIP opens.

The solver consumes **certified metadata**, not package payload bytes. A later artifact-delivery operation must verify complete artifact bytes against the selected artifact ID. Changed payload bytes with unchanged metadata therefore do not change a solve against the old admitted metadata snapshot; they would fail artifact delivery. This distinction is intentional, and no artifact delivery service exists in this experiment.

The metadata fields/requirement interpretation here are Python-specific. Other ecosystems need their own semantics adapters. JSON schemas are versioned experimental fixtures, not a durable repository/transport standard. The useful future boundary is immutable candidate/metadata identity plus explicit target/policy; bulk metadata queries could implement it locally or remotely. No per-file RPC pattern, server topology, trust/signature scheme or permanent index layout is chosen here.

Duplicate wheel bytes under an identical candidate filename/identity collapse. Conflicting filename identities for the same bytes currently fail admission rather than silently choosing one; a future repository model may need separate candidate-descriptor and artifact-byte identities.

## Results and diagnostics

- [Initial measurements](results/initial/REPORT.md), raw observations (local artifact, `results/initial/results.json`).
- [Findings](FINDINGS.md): interpretation and limits of the initial run.
- [Fresh pip reference](results/initial/pip-reference.json): verifies the original 22 artifacts and selected versions.
- Separate warm-solve profiles (local artifact, `results/initial/profile-data/profiles.json`): where repeated work remains after caching.
- [Incremental scheduler comparison](results/incremental/REPORT.md), raw observations (local artifact, `results/incremental/results.json`).
- Incremental warm-solve profiles (local artifact, `results/incremental/profile-data/profiles.json`).
- [Trail comparison](results/trail/REPORT.md), raw observations (local artifact, `results/trail/results.json`).
- [Trail scaling](results/trail-scaling/REPORT.md), raw observations, gzip (local artifact, `results/trail-scaling/results.json.gz`).
- Trail warm-solve profiles (local artifact, `results/trail/profile-data/profiles.json`).
- [Naive scaling and original startup comparison](results/naive-startup/REPORT.md), raw observations (local artifact, `results/naive-startup/results.json`).
- [Real Django candidate solving](results/django/REPORT.md), raw observations (local artifact, `results/django/results.json`), [published-wheel provenance](results/django/provenance.json).

After timing completes, separate warm-solve profiles can be collected with:

```sh
python3 -B experiments/python/dependency_solving/profile_solver.py
```

Raw `.pstats` files are ignored; `results/initial/profile-data/profiles.json` records disjoint self-time buckets and detailed functions. Profiles add overhead and are not substituted into unprofiled timing. The default profiles wide/shared/conflict graphs with catalog variants after one completed solve.

For the scheduling comparison, use `profile_solver.py --results experiments/python/dependency_solving/_work/runs/incremental/results.json --output experiments/python/dependency_solving/_work/runs/incremental/profile-data`.
