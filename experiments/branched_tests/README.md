# Branching initialized Django test state

This experiment combines an initialized Python/Django process with a prepared SQLite fixture and attachment files. It compares the complete request lifecycle against fresh pytest, native database reuse, fixture copies with fresh interpreters, and a warm worker. The target is a small selection of **unmodified upstream django-todo 2.7.0 test bodies**, with explicit fixture adapters and additional boundary probes.

Read the [measured report](results/django-todo/REPORT.md), [research interpretation](../../research/connections/branched-tests.md), and [machine-readable summary](results/django-todo/summary.json). This is an application-specific test harness, not a general snapshot runtime or an integration into Gaia's production components.

## Controls and contract

| Mode | Runtime | Database/media preparation | Failure handling |
| --- | --- | --- | --- |
| `stock_fresh` | New Python/Django/pytest per request | Native migrations and fixture construction | Ordinary pytest teardown; next request starts fresh |
| `stock_reuse` | New Python/Django/pytest per request | Native `--reuse-db`, fresh fixture construction; keep schema across the tested non-schema edits | Retain schema after verified ordinary teardown; native Django flush after SIGKILL |
| `exec_seed` | New Python/Django/pytest per request | Private copies of prepared SQLite and attachment files | Discard private files |
| `warm_seed` | Same initialized process within a generation | The same private fixture copies | Restart process after failed/killed requests |
| `fork_seed` | Fresh native fork child of initialized parent per request | The same private fixture copies | Discard child and files; parent survives |

The prepared fixture calls the upstream fixture function, then creates one real attachment. The prepared arms override the documented `django_db_setup` fixture; pytest-django still owns per-test transactions and teardown. Every mode runs the same added assertions. All main measurements use Django's standard fast **test-only** MD5 hasher. The original password-hashing profile is recorded separately and is not claimed as an architectural saving.

The prepared parent is single threaded and owns no descriptors beyond stdin/stdout/stderr. Django connections are closed before fork. Requests rebind SQLite and media paths to controller-owned branches. File copies use `shutil.copyfile` and `copytree`; there is no filesystem reflink or database server snapshot. Successful and failing child requests perform normal Python finalization, verified by an `atexit` marker and process wait. SIGKILL intentionally bypasses finalization; the controller cleans private files afterward.

Source bytes, harness bytes, declared configuration, an admitted dependency digest and fixture date identify a generation. The controller hashes the current private source before reuse, rejects unannounced changes, and rebuilds initialized state for source/settings changes. It holds one active generation and reconstructs even a previously seen generation. These are conservative invalidation rules. The dependency environment is held fixed for the run; installed Python/extension/metadata hashes are checked before/after measurement. Package data and system libraries are assumed fixed. This is not a live package-update protocol.

Python audit hooks reject socket operations and Python-observed writes outside the current branch. They are diagnostic guards, **not an OS security boundary**; native extension I/O is not fully mediated. This harness does not support external databases, background threads, subprocess-spawning tests, GPU contexts, or arbitrary external side effects.

A warm worker has a narrower contract than a forked child. A separate diagnostic proves that a **successful** heap-mutating test contaminates its next request until restart. The ten-event timing trace uses selected successful tests that satisfy the warm worker's bounded reuse contract; its injected mutations occur in failed/killed requests. Do not interpret equal answers on that trace as equivalent general isolation.

## Reproduce

Use Linux and Python 3.14. The retained run used CPython 3.14.8, Django 5.2.8 and SQLite from that interpreter. Artifact URLs and SHA-256 hashes are in [acquisition.json](acquisition.json); dependency pins and hashes are in [requirements.txt](requirements.txt). The source package is BSD-3-Clause; its license remains in the downloaded tree. The package contains its tests and migrations but omits the root test-project settings and URL adapter, so [gaia_settings.py](gaia_settings.py) and [gaia_urls.py](gaia_urls.py) supply those explicitly.

From the repository root, create a private environment and acquire the pinned app:

```sh
python3.14 -m venv experiments/_work/branched-tests-env
experiments/_work/branched-tests-env/bin/python -m pip install --require-hashes -r experiments/branched_tests/requirements.txt
python3 - <<'PY'
import hashlib, json, pathlib, tarfile, urllib.request
spec = json.loads(pathlib.Path('experiments/branched_tests/acquisition.json').read_text())['app']
dest = pathlib.Path('experiments/_work/branched-tests-source')
dest.mkdir(parents=True, exist_ok=True)
archive = dest / 'django_todo-2.7.0.tar.gz'
archive.write_bytes(urllib.request.urlopen(spec['url']).read())
assert hashlib.sha256(archive.read_bytes()).hexdigest() == spec['sha256']
with tarfile.open(archive) as source:
    source.extractall(dest, filter='data')
PY
```

The pinned titlecase source distribution needs pip's ordinary build environment. Installation/download/build time is outside the test-operation measurement. Installed dependency source/extension identities are recorded in provenance and checked unchanged across the run.

Run the contract diagnostic, then the randomized matrix. Work/output paths must be new; the controller deletes its own per-trial state after successful completion. Use a shared cooperative lock when another experiment is measuring on the same host.

```sh
PYTHONDONTWRITEBYTECODE=1 experiments/_work/branched-tests-env/bin/python experiments/branched_tests/check_boundary.py \
  --app experiments/_work/branched-tests-source/django_todo-2.7.0 \
  --work experiments/_work/branched-boundary-replay \
  --output experiments/_work/branched-boundary-replay.json
PYTHONDONTWRITEBYTECODE=1 experiments/_work/branched-tests-env/bin/python experiments/branched_tests/run.py \
  --app experiments/_work/branched-tests-source/django_todo-2.7.0 \
  --work experiments/_work/branched-replay \
  --output experiments/branched_tests/results/replay \
  --blocks 7 --lock experiments/_work/measurement.lock
```

`run.py` writes raw observations, summary, validation, raw identity and provenance. Raw `results.json` stays ignored; published evidence identifies it by hash. The boundary diagnostic is separate from timing and uses an expected failing request to demonstrate the warm worker limitation.

For the initial attribution profile, run [profile_tests.py](profile_tests.py) with `--app` and a fresh `--work`; repeat with `GAIA_FAST_HASHER=1`. Its `cProfile` output is intrusive and should not be compared as an unprofiled speed benchmark.
