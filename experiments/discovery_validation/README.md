# Source discovery linked to recorded test execution

This prototype presents current source together with tests observed executing its function bodies and the source/configuration identity of those observations. It reuses pytest-testmon's existing collector and selection engine. It does not implement another dependency analyzer, infer a complete impact set, or treat execution coverage as proof that a bug is tested.

The [historical replay report](results/jinja/REPORT.md) and [research interpretation](../../research/connections/discovery-validation.md) describe three real Jinja fixes. [Task definitions](tasks.json) pin their commits and first-parent baselines. The prototype also provides a read-only [search/inspection CLI](evidence.py) for the retained example workspaces.

**This is a mechanical workflow replay, not a blind developer or agent study.** The replay applies known upstream patches and inspects predetermined functions. It measures preparation, native validation, source queries and evidence handling. It does not measure the reasoning needed to locate or invent a fix, or establish a reduction in human/agent task-completion time.

## What the shared boundary does

[observer.py](observer.py) wraps the pinned `TestmonData.get_tests_fingerprints` method inside an owned pytest subprocess. It first obtains the unmodified native result, then reads the same per-test line observations to construct a second projection for source inspection. It does not change native selection, fingerprints, report objects, or the returned native result. The wrapper is restored at session completion.

Python's AST supplies lexical function-body spans. Each observed line belongs to the innermost named function body containing it. The export contains function identities/locations and test-to-function associations. These are execution-context observations, not resolved call edges: a deferred generator or a lambda inside a constructor can execute while a later test is active. Generated template code and external libraries are outside the source projection.

[EvidenceStore](evidence.py) joins those observations to current source:

- Current source locations and excerpts come from the bytes being queried.
- Recorded observations retain their producing source/configuration generation and test outcome.
- After an edit, older links are explicitly historical. A matching function AST is shown separately and does not upgrade the old result to current validation.
- Publication rejects a late result or a mismatched configuration. Queries can require an expected generation.
- Invalid/incomplete source withholds structural answers; literal ripgrep search remains available.
- Responses bound the displayed matches/observations, report truncation/counts, and never present a shortlist as a complete impact set.

The generation hashes source files, tests and their fixture resources, project test configuration and an admitted environment context. This is a serialized, controller-owned workspace contract. It is not a filesystem watcher, atomic filesystem snapshot, security boundary or proof about arbitrary external services and environment variables. Dependency versions and selected tool-source hashes are pinned; the surrounding OS and all installed package bytes are not hermetically captured.

## Three measured paths

| Path | Validation | Source/test evidence |
| --- | --- | --- |
| `full_suite` | Ordinary fresh pytest, full suite at every step | Literal search and structural source inspection |
| `native_testmon` | Native testmon collection/selection | The same source inspection, without the new exported view |
| `shared_evidence` | The same native testmon collection/selection | Additional borrowed execution observations, generation-qualified inspection and persisted history |

The strong native control answers whether adding the evidence view changes selection or adds substantial cost. **It is an overhead comparison for an added capability**, not a claim that it offers identical discovery output. The full-suite comparison identifies the cost/benefit of testmon itself. Those savings must not be credited to Gaia's export.

Each task replays initial preparation, addition of regression tests, the source fix, an unchanged rerun, source reversion and restoration. Initial data is collected from the first parent before the new regression tests exist. The controller knows the fix and inspection locations; this is not a retrieval-ranking or blind bug-fixing benchmark.

For the overlay task, the upstream added test passes even before the fix. The replay additionally uses the minimal reproduction published in the original PR, preserving that validation gap as an explicit result. All ordinary upstream test bodies remain intact.

## Compatibility and validation

The pinned environment is Python 3.14.8, pytest 9.2.0, pytest-testmon 2.2.0 and Coverage 7.17.0. Coverage's default `sysmon` core cannot provide the dynamic contexts required here; the runner sets `COVERAGE_CORE=ctrace` for every path. Testmon also requires pytest's cache plugin (`lf` option); its files are redirected to owned state directories.

The unmodified testmon collector crashes on Jinja's traced extensionless template `tests/res/templates2/foo`. A recorded [one-line compatibility patch](testmon_compat.patch) routes extensionless files through its existing conservative whole-file treatment for non-Python input. **Both testmon controls use the identical patch.** [Original/patched source identities](compatibility.json) and a focused changing-template check preserve this adjustment. No selection policy is changed.

[verify.py](verify.py) compares the initial exported relationships against an independent full pytest-cov run with per-test contexts. All relationships for the replay's queried functions must match. Full-graph discrepancies are retained rather than discarded; deferred execution makes some context attribution vary between separate runs. [Oracle evidence](results/jinja/oracle-validation.json).

[test_evidence.py](test_evidence.py) checks nested lexical containment, changed bodies, absent/renamed definitions, path admission and the native compatibility fix. Each shared replay additionally checks line shifts, stale-result rejection, stale-query rejection, incomplete source and configuration mismatch. Native and shared validation must execute identical test sets/outcomes, and all paths must agree on the full-suite failure set at each step.

## Reproduce

Use Linux x86-64 and Python 3.14 for the pinned wheel hashes. Installation/build acquisition is outside the workflow clock. [acquisition.json](acquisition.json) records dependency artifact identities; source history is pinned by [tasks.json](tasks.json).

```sh
python3.14 -m venv experiments/_work/discovery-env
experiments/_work/discovery-env/bin/python -m pip install --require-hashes -r experiments/discovery_validation/requirements.txt
git clone --branch 3.1.6 --single-branch https://github.com/pallets/jinja.git experiments/_work/discovery-source/jinja
patch -p1 -d experiments/_work/discovery-env/lib/python3.14/site-packages < experiments/discovery_validation/testmon_compat.patch
PYTHONDONTWRITEBYTECODE=1 experiments/_work/discovery-env/bin/python experiments/discovery_validation/test_evidence.py
experiments/_work/discovery-env/bin/python experiments/discovery_validation/verify.py \
  --repo experiments/_work/discovery-source/jinja \
  --work experiments/_work/discovery-oracle-replay \
  --output experiments/_work/discovery-oracle-replay.json
experiments/_work/discovery-env/bin/python experiments/discovery_validation/run.py \
  --repo experiments/_work/discovery-source/jinja \
  --work experiments/_work/discovery-replay \
  --output experiments/discovery_validation/results/replay \
  --blocks 3 --lock experiments/_work/measurement.lock
```

Work/output directories must be new. Jinja's async tests require local socket operations; a sandbox that denies those operations cannot reproduce the verified baseline. No network service is needed during tests. Use a common lock for other timing experiments on the same host. Failed preflights remain separate from measured observations.

The runner retains the first shared workspace for each task under the supplied work directory. Get `context` from the result's `provenance.json`, then inspect it:

```sh
experiments/_work/discovery-env/bin/python experiments/discovery_validation/evidence.py \
  --root /path/to/b0-overlay-async-shared_evidence/project \
  --store /path/to/b0-overlay-async-shared_evidence/state/evidence.json \
  --context CONTEXT_FROM_PROVENANCE \
  inspect src/jinja2/environment.py Environment.overlay --focus overlay
```

Replace the final line with `search overlay` for literal search. Source changes are read on the next query; prior observations become historical automatically. Running arbitrary additional validation is available through the native pytest/testmon commands and the `run_tests`/`publish` APIs; the CLI is deliberately read-only.

The [captured CLI response](results/jinja/example.json) comes from the retained overlay workspace after restoration. It presents the current function and all three observed test associations, including the issue-derived regression. It explicitly marks the list as incomplete for impact analysis.

Source licensing: Jinja is BSD-3-Clause. Its [license](UPSTREAM-LICENSE.txt) accompanies the captured source excerpt and remains in each archived workspace. Testmon/Coverage implementation details are pinned private experiment dependencies, not new Gaia protocols or supported upstream extension APIs.
