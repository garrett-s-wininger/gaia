# Python dependency formats and loading

For human review, start with the [consolidated review](../../../research/python/dependency-formats.md), [evidence register](../../../research/python/experiments.json), and [follow-up queue](../../../research/python/follow-up.md). Historical paths remain valid through the aliases described in the [experiment guide](../../README.md). Instructions below reproduce individual stages; they do not define a standardized format.


The latest [stdlib snapshot comparison](results/stdlib/REPORT.md) and [file-access diagnostics](results/stdlib/diagnostics/REPORT.md) test the remaining host pure-Python imports. See the reproduction section at the end of this document.

A standard-library-only Linux experiment for the [dependency-bundle proposal](../../../research/python/designs/dependency-formats.md). It generates controlled regular Python packages and compares directory loading with stored and DEFLATE ZIP loading through the real Python import and resource APIs. No network, installs, compiler changes, or native bundler are needed.

## Run

```sh
python3 -B -m unittest discover -s experiments/python/dependency_bundles -v
python3 -B experiments/python/dependency_bundles/benchmark.py
```

The default run uses 64, 512, and 2,048 leaf modules, source-only and separately precompiled inputs, and eleven cases: directories, stored/DEFLATE ZIP through stock loading, the same two ZIP containers with shared resource readers, the same two containers with persistent module/resource providers, and four common-interface byte-access backends. Each case gets one warmup and 15 measured fresh processes, interleaved in a seeded shuffled order. The 24 package/helper modules and 32 text/binary resources are additional to the leaf-module counts. Use `--layouts` to select a smaller comparison.

The first stock-loader attempt exposed repeated archive-resource setup. [shared_zip_resources.py](shared_zip_resources.py) is a small path-hook experiment: it subclasses the stock ZIP importer only to share one lazily opened `ZipFile` for resource access. Module/bytecode loading remains standard. The same ZIP bytes are used for stock and shared-reader cases. Tests verify use of the hook and exactly one shared resource-archive open; its index/open cost is inside the measured resource phase. Common adapter import preparation occurs equally before each case's workload timing and remains included in process-wall timing.

The follow-up [persistent_zip_loader.py](persistent_zip_loader.py) keeps one archive open for **both modules and resources**, parses its contents once, and discovers module names without fetching code. Every fixture module is read exactly once. The archive opens lazily inside import timing and stays open through the entire consumer workload/validation. This is all in one process; a new process per trial resets module caches. There is no per-module IPC or child process. The original ZIP importer caches its directory index but can reopen the archive for code reads; repeated resource-reader construction was a separate issue.

This provider intentionally supports only regular packages in source-only or matching-interpreter sourceless-bytecode layouts. It rejects mixed source/cache module entries and invalid bytecode headers rather than implementing a general cache-invalidation policy. Namespace packages, native extensions, arbitrary environment replacement, and production-grade distribution semantics remain outside scope.

## Real Django application

The [Django report](results/django/REPORT.md) and [findings](FINDINGS.md#real-django-application) test published Django 6.1.2, asgiref 3.13.0 and sqlparse 0.6.0, then add REST framework 3.18.3 and django-filter 26.2. These are pinned wheels, not generated substitutes. The [provenance manifest](results/django/provenance.json) retains exact URLs and SHA-256 hashes for three candidate versions of each of the five projects. Fetching is a producer/reproduction step; measurements are offline and do not install packages into the host environment.

```sh
python3 -B experiments/python/dependency_bundles/fetch_django.py
python3 -B experiments/python/dependency_bundles/django_benchmark.py
python3 -B experiments/python/dependency_solving/django_benchmark.py
```

The loader run reuses the prior CPython/Odin extension under ignored `_work/`; supply `--library /path/to/_gaia_native.so` to use another compatible build. If that prior input is absent, run the CPython/Odin experiment below to rebuild it. `--trials 1 --output /tmp/gaia-django-smoke` reduces the loading run. The separate solver driver supports the same trial/output options and validates selected artifact hashes against fresh offline pip reports before accepting its results. [Solver results](../dependency_solving/results/django/REPORT.md) are separate from application startup.

The loading fixture starts WSGI/admin/ORM, runs system checks, creates a two-row in-memory SQLite table, serves a filtered JSON request and renders the admin login page. REST uses a real serializer/view/filter backend. Dependency sources stay unmodified. [django_fixture/template_loader.py](django_fixture/template_loader.py) adapts Django templates to `importlib.resources`; ordinary files use that same adapter for controlled byte-reader comparisons, alongside an extra stock-filesystem-template baseline. Form rendering uses Django's TemplatesSetting renderer in every case. Sources/templates are not silently extracted by bundle consumers.

There are 20 loading cases: core/REST × source/bytecode × five readers, with 15 randomized fresh processes each. Code origins/loader use, import/execution sets, checks, API data, admin form markers, package versions, resource hashes, single archive lifetime and zero network events are validated. Stock filesystem templates intentionally import different loader code; the four common-adapter cases must have identical dependency import/execution sets. Source-to-bytecode gains must not be attributed to bundling or Odin; ordinary deployments can already use bytecode caches. I18N is disabled, and migration discovery, static collection/serving, autoreload, arbitrary filesystem access and native wheels remain outside this fixture's compatibility claim.

The [bridge diagnosis](results/bridge/REPORT.md) isolates the exact Django module-read trace from compilation/framework execution:

```sh
python3 -B experiments/python/dependency_bundles/bridge_diagnostic.py
```

It reuses the Django run's exact archives/index pins and native extension. Both readers run in each fresh process with randomized opening/block order. Named paths both return owned bytes with CRC verification; a separate ordinal diagnostic bypasses Python name/wrapper handling. Full payload equivalence and checksums are checked outside/inside the appropriate scopes. Repeated reads are warm after validation/warmup, not first-touch import timings. Separate constructor profiles retain function self/inclusive times and are never substituted into unprofiled timings. This measures bridge-inclusive reads, not the ABI in isolation, and makes no native-kernel optimization.

The [Django filesystem/profile diagnostics](results/django-diagnostics/REPORT.md) identify remaining path operations and discovery work. They use the unchanged worker through [django_probe.py](django_probe.py); its clock wrapper brackets only the application workload and checks the expected seven main clock calls. These instrumented timings are never used as benchmark samples. Reproduce after the Django run:

```sh
python3 -B - <<'PY'
import json, subprocess, sys
from pathlib import Path
folder = Path('experiments/python/dependency_bundles').resolve()
data = json.loads((folder/'_work/runs/django/results.json').read_text())
work = folder/'_work/django-diagnostics'
work.mkdir(exist_ok=True)
for reader in ('directory-stock', 'directory', 'python', 'odin'):
    case = next(c for c in data['cases'] if c['scenario']=='rest' and c['mode']=='bytecode' and c['reader']==reader)
    command_file = work/(reader+'-command.json')
    command_file.write_text(json.dumps(case['command']))
    probe = [sys.executable, '-I', '-S', '-B', str(folder/'django_probe.py'), '--command', str(command_file)]
    subprocess.run(['strace', '-qq', '-f', '-T', '-yy', '-e', 'trace=%file,fstat,fstatfs,read,pread64,close,lseek,getdents64,mmap,munmap,write', '-o', str(work/(reader+'.trace')), *probe, '--result', str(work/(reader+'-trace-result.json'))], check=True)
    subprocess.run([*probe, '--profile', str(work/(reader+'.pstats')), '--result', str(work/(reader+'-profile-result.json'))], check=True)
PY
python3 -B experiments/python/dependency_bundles/summarize_django_probe.py
```

Tracing requires ptrace permission in a sandbox. Include descriptor-based `fstat` explicitly in the trace filter. Raw traces/profiles stay under ignored `_work/`; the summary retains counts, path attribution, full per-function profile records and application validation. Counts are scoped to the workload, including lazy host imports. The recorded traces were concurrent; profiles were sequential. The script above collects both sequentially. Neither syscall durations under strace nor cProfile self times estimate uninstrumented cycle costs.

## Index-backed package discovery

[indexed_path_loader.py](indexed_path_loader.py) adds an optional mount over the existing provider. It installs a path-entry finder for the admitted bundle's paths, derives regular-package/direct-child tables once, and serves module lookup, misses and `pkgutil` enumeration from that index. Other filesystem paths retain their normal hooks. Installation is lazy and idempotent; close removes owned hooks/cache entries and restores prior importers where possible. Source and bytecode use the same implementation; archive bytes, integrity checks and native ABI are unchanged.

```sh
python3 -B experiments/python/dependency_bundles/path_index_benchmark.py
```

This reuses the exact retained REST application inputs and compares directory, Python/legacy, Python/indexed, Odin/legacy and Odin/indexed cases in both modes. Fifteen randomized fresh processes per case give 150 observations. Indexed correctness warmups forbid stock ZIP-directory parsing, while a legacy negative control must trigger that guard. The guard is disabled in timed runs. Every result must preserve the prior imports, code executions, resources and API output. `--modes bytecode --trials 1 --output /tmp/path-index-smoke` narrows a run. Direct workers select the feature with `--discovery index`; legacy remains the default benchmark control. [Report](results/path-index/REPORT.md), [findings](FINDINGS.md#index-backed-discovery-follow-up), raw observations (local artifact, `results/path-index/results.json`).

The [matched trace/profile report](results/path-index/diagnostics/REPORT.md) verifies removal of the ZIP fallback. For reproduction, use the diagnostic Python block above with `results/path-index/results.json` as input, `_work/path-index-diagnostics` as the work directory, and select every `mode=='bytecode'` case. Label each command `directory` for that reader, otherwise `reader+'-'+discovery`. Then summarize with:

```sh
python3 -B experiments/python/dependency_bundles/summarize_django_probe.py --inputs experiments/python/dependency_bundles/_work/runs/path-index/results.json --work experiments/python/dependency_bundles/_work/path-index-diagnostics --output experiments/python/dependency_bundles/_work/runs/path-index/diagnostics
```

The six new tests compare source/bytecode enumeration with stock behavior, prohibit payload reads and ZIP fallback during discovery, block filesystem probes for indexed lookup/misses, exercise recursive package walking, and check hook/cache restoration, overlapping mounts and failure cleanup. The full loader suite now has 42 tests. Profiler counts include generator resumptions: the older `iter_zipimport_modules` count of 77 corresponds to 18 enumeration requests, not 77 complete scans. This change does not replace the host stdlib loader, rewrite the native reader, or add namespace/native-wheel support.

## Isolate generic byte access

[bundle_access.py](bundle_access.py) supplies the same entry-read/resource interface through ZipFile, indexed `pread`, indexed `mmap`, and whole-file-resident backends. These cases use identical stored ZIP bytes and payload CRC checks. Indexed readers validate header/name/range metadata once at opening. The common resource wrapper is used by all four so its implementation is not another variable. The original persistent reader remains as an extra baseline.

```sh
python3 -B experiments/python/dependency_bundles/benchmark.py --modules 2048 --trials 15 --warmups 1 --layouts directory persistent-stored access-zipfile access-pread access-mmap access-resident --output experiments/python/dependency_bundles/_work/runs/access-loader
python3 -B experiments/python/dependency_bundles/access_benchmark.py
```

The first command holds module/bytecode interpretation fixed while replacing only the byte-access/resource provider. It reruns baselines with the same common worker setup and generates retained fixture inputs. The second does no dependency import/compilation/execution: it separately measures opening/index validation and full-entry reads of that stored source bundle. It tests lexical/shuffled access, first/reused scans, and bytes versus explicitly released views, in fresh processes. Use `access_benchmark.py --archive /path/to/stored.zip` for an explicit corpus; the default selects the retained access-loader fixture, falling back to the earlier persistent run if needed.

Only plain regular stored members are supported in this access experiment; compressed/encrypted/descriptor/ZIP64 entries are rejected. Concurrent mutation/truncation of a mapped bundle is outside scope. CRC verification remains on every read/view. mmap/resident views can avoid a payload copy; loader integration always uses returned bytes, so it does not claim zero-copy compilation. Opening/indexing/mapping or reading the entire resident archive is included in first-use costs.

This is an access-layer reference under the current Python harness, not an established hardware/native floor. Python request dispatch, namespace validation, and ZipFile central-directory parsing remain. Mapping/page faults and whole-file residency can incur work not visible as `read` calls.

For a quick smoke run:

```sh
python3 -B experiments/python/dependency_bundles/benchmark.py --modules 16 --trials 1 --output /tmp/gaia-bundle-smoke
```

Use a different `--output` directory to retain a separate result set. Generated inputs live in ignored `_work/` run directories, retained so syscall traces can reproduce the exact worker commands. These are experimental fixtures, not a production package installer or untrusted-archive service.

The focused process-lifetime follow-up is reproduced with:

```sh
python3 -B experiments/python/dependency_bundles/benchmark.py --modules 2048 --trials 15 --warmups 1 --output experiments/python/dependency_bundles/_work/runs/persistent
```

To trace that run, use its `results/persistent/results.json` and `results/persistent/traces/combined` in the trace commands below. The first saved run used the original five layouts; reproduce its selection with `--layouts directory stored deflated shared-stored shared-deflated`.

## Trace separately

Execute the trace run where ptrace is permitted; do not include its timings in benchmark samples. One outer `strace -ff` invocation records a separate trace for each worker process:

```sh
mkdir -p experiments/python/dependency_bundles/_work/runs/traces
strace -qq -ff -s 256 -e trace=%file,read,pread64,close,lseek,getdents64,mmap,munmap,write,fstat -o experiments/python/dependency_bundles/_work/runs/traces/combined python3 -I -S -B experiments/python/dependency_bundles/trace_workers.py --results experiments/python/dependency_bundles/_work/runs/results.json --trace-prefix experiments/python/dependency_bundles/_work/runs/traces/combined
python3 -B experiments/python/dependency_bundles/benchmark.py --summarize experiments/python/dependency_bundles/_work/runs/results.json --trace-prefix experiments/python/dependency_bundles/_work/runs/traces/combined
```

The consumer writes markers around the measured import/resource/application phases. The parser counts only that interval, excluding interpreter preparation and correctness checks. A run-ID-checked worker PID map connects traces to cases. `results/traces/` is ignored; parsed counts are saved in the result JSON. `results/trace-plan.json` also contains standalone trace commands for individual cases. If tracing is denied, run with the required environment permission rather than reporting invented or audit-hook syscall counts.

The same trace runner supports the raw-access cases with `results/access/results.json` and a trace prefix under `results/access/traces/`. Ingest those traces with `access_benchmark.py --summarize ... --trace-prefix ...`. It reports `GAIA_INDEX_BEGIN/END` setup and `GAIA_WORKLOAD_BEGIN/END` read-loop syscall scopes independently. Nested trace directories are ignored too.

## Artifacts and interpretation

- [REPORT.md](results/REPORT.md): generated timing, storage, preparation/export, and syscall tables.
- results.json (local artifact, `results/results.json`): environment, raw samples, phase timing/CPU/RSS, summaries, correctness results, preparation costs, and parsed trace counts.
- `results/trace-plan.json`: local commands/paths for the recorded run, regenerated for another checkout.
- [FINDINGS.md](FINDINGS.md): interpretation of the first completed run and next experiment.
- [Process-lifetime follow-up](FINDINGS.md#process-lifetime-follow-up): interpretation of the extended loader and [its complete report](results/persistent/REPORT.md).
- [Cost/floor diagnostics](results/diagnostics/REPORT.md): original 298 ms sample partition, additional phase/startup observations, and separate import-only profiles; [raw diagnostics](results/diagnostics/diagnostics.json).
- [Generic access findings](FINDINGS.md#generic-byte-access-follow-up): [raw-access report](results/access/REPORT.md) and [fixed-loader comparison](results/access-loader/REPORT.md).
- [Prefault comparison](results/prefault/REPORT.md): setup-inclusive mmap timings and page-fault deltas for tiny entries and 64 MiB of larger entries; raw samples (local artifact, `results/prefault/results.json`).
- [Precomputed index comparison](results/index/REPORT.md): producer cost, sidecar storage, raw-access timing and fixed-loader timing with full-hash and local-admission policies; raw samples (local artifact, `results/index/results.json`).
- [Binary versus JSON index](results/binary-index/REPORT.md): the same admission/verification policies with fixed binary records and a UTF-8 name pool; raw samples (local artifact, `results/binary-index/results.json`).
- [Native Odin access comparison](results/native/REPORT.md): mapped binary records versus known-path file reads, controlled ZIP-index rebuilding, and the Python binary reader; raw samples (local artifact, `results/native/results.json`).
- [Odin connected to CPython](results/python-native/REPORT.md): actual module/resource loading with the in-process extension, synthetic imports and real offline pip resolution; raw samples (local artifact, `results/python-native/results.json`).
- [Resolution diagnostics](results/resolution/REPORT.md): isolated import name/path discovery with zero code execution, plus separately profiled CLI import/compile/solver phases; raw samples (local artifact, `results/resolution/results.json`).

Separate module discovery from dependency-version solving with:

```sh
python3 -B experiments/python/dependency_bundles/resolution_benchmark.py
```

It reuses the CPython/Odin run's exact inputs and 312 actually executed pip code files. Each fresh discovery worker checks all successful names and the same number of missing names, in four scans, without importing parents, reading module code through the loader, compiling or executing pip. Full-hash admission still scans archive bytes. Both source/bytecode and all six providers are measured with setup costs included separately. Repeated scans exercise finder caches rather than cached imports. One-miss-per-hit is an explicit stress mix, not an observed CLI miss rate. Use `--trials 1 --output /tmp/gaia-resolution-smoke` for a smoke run or `--inputs path/to/python-native/results.json` for retained inputs from another run.

After unprofiled discovery trials finish, six separate whole-pip cProfile runs partition self time and expose inclusive finder and resolver phases. Profiles add overhead and may prime profiler-related host stdlib imports; they must not be mixed into unprofiled timing. Solver resolve includes metadata/candidate callbacks and lazy imports, not solely the constraint algorithm. This graph remains the existing small 22-wheel/12-package case; solver scaling is not tested. The loader-side lookup map/spec creation remain Python even with Odin byte access.

Timing correction discovered during these diagnostics: in the original CPython/Odin pip run, temporary-directory setup lazily imported a host module and opened the input provider before the workload timer. Its **process totals remain valid**, but pip's original workload columns exclude provider setup. The original report is annotated and its observations preserved. The current worker publishes root/provider inputs only after the timer starts and guards against premature opening; the corrected profile includes provider startup. [The superseded phase diagnostic](results/resolution-before-timing-fix/REPORT.md) is retained separately. Synthetic workload timing was unaffected.

Build and run the CPython/Odin comparison with:

```sh
python3 -B experiments/python/dependency_bundles/python_native_benchmark.py
```

It needs Linux, Odin, a C compiler, CPython development headers, zlib and OpenSSL. The current environment already provides all of them. The script builds [native/python_api.odin](native/python_api.odin) and [native/python_shim.c](native/python_shim.c) into a CPython extension and connects it using [native_loader.py](native_loader.py). Native reads check CRC and the GIL-held shim copies directly into an owned Python bytes object; explicit close/capsule destruction free native resources, and input errors raise Python exceptions. The original module/resource loader remains unchanged. Extension loading, native open and catalog-to-Python construction occur inside timed loading; their phases are retained. Both native and Python binary readers use full-hash and trusted-local policies. Directory and Python ZIP-rebuilding controls are rerun with equal common adapter preparation.

The representative case uses the locally bundled pip wheel from `ensurepip/_bundled`, pinned by version and SHA-256 in the report. It performs real `pip install --dry-run` offline resolution over 22 generated wheels, with a 12-package solution and required backtracking; nothing is installed. The dependency graph is synthetic, while pip's 404 Python files and vendored implementations are unmodified. This invocation executes 312 distinct pip code files and retains 310 unique origins plus 32 aliases. All origins, file-execution counts, code-read counts, resource bytes, resolver report and selected versions are validated; an audit hook rejects network activity. Standard pip metadata access, wheel reading and any resource-to-path extraction stay on their normal code paths and are included in timing.

Use `--pip-wheel /path/to/pip.whl` if `ensurepip` does not bundle one, `--odin /path/to/odin` to select the compiler, or `--modules 16 --trials 1 --output /tmp/gaia-python-native-smoke` for a smoke run. Full runs use 2,048 synthetic leaf modules and 15 trials per case. Source-only and equivalent precompiled-only inputs are measured separately, with `-I -S -B` for every consumer. The experiment establishes one real-tool result, not typical ecosystem counts or a platform-wide speedup.

Build and run the native comparison on Linux with:

```sh
python3 -B experiments/python/dependency_bundles/native_benchmark.py
```

This uses retained source/bytecode/large-entry archives from the binary-index run. Use `--inputs path/to/results.json` to select another index benchmark run, `--odin /path/to/odin` to select the compiler, and `--trials 1 --output /tmp/gaia-native-smoke` for a smoke run. It builds [native/main.odin](native/main.odin) with `-o:speed` and bounds checking retained, emits an object file, and links it with the installed C driver plus system zlib/OpenSSL. Exact commands, versions and executable hash are saved. Compile and link costs are outside consumer timing. The driver emits an Odin object and selects the installed C linker explicitly; no retained linker installation is required.

The accessor maps the binary sidecar and archive once per process, keeping them open across four scans. Sidecar/bundle binding, metadata bounds/UTF-8 checks and name-map/path construction belong to setup. Named access builds/queries a native name map; ordinal access uses row IDs scoped to that specific pinned index, with no name-map construction. Rows are read directly from mapped records, with an array of basename positions and directory string views. Neither row IDs nor this binary layout are a standardized platform interface.

Both implementations retain zlib CRC on every read; native full-content SHA-256 validation runs after the timed scans and is checked by the parent against expected per-member hashes. The directory baseline reads a known list of files, opens/fstats/reads/closes each request, and has no directory walk or whole-directory admission hash. The native ZIP control additionally rebuilds central/local metadata against the certified sidecar; it is a restricted ordered stored-ZIP parser, not a general native ZIP implementation. Bytes allocate/copy/release a payload each request; mapped views avoid that copy. Both are reported separately, as are full-hash versus trusted-local admission. Process wall includes runtime/crypto bootstrap, all four scans and extra validation; it cannot be substituted for CPython module-loading time. Native memory/syscall measurements are not claimed.

`python3 -B -m unittest discover -s experiments/python/dependency_bundles -v` includes native cross-language equivalence and failure tests when the Linux Odin/C toolchain is available. Without it, those native tests are explicitly skipped; the Python tests still run.

Compare both sidecar encodings with:

```sh
python3 -B experiments/python/dependency_bundles/index_benchmark.py --encodings json binary
```

This writes to ignored `_work/runs/binary-index/` by default and reruns the ZIP-parsing control. The experimental binary layout has a 128-byte little-endian header, 28-byte entry records, directory-length records, and a UTF-8 string pool. Entries store payload offset/length, CRC, directory ID and basename length. Repeated directory prefixes are stored once. Both readers hash the pinned sidecar, validate the same payload ranges, and construct Python dictionaries for names and offsets; neither sidecar reader is an in-place native lookup engine. Both bundle verification policies and per-read CRCs remain. The test suite compares the logical metadata across encodings and rejects malformed binary headers, table sizes, names, directory IDs and payload ranges. Use `--modules 16 --trials 1 --output /tmp/gaia-binary-index-smoke` for a smoke run.

Run the separate in-memory decode diagnostic against retained inputs with:

```sh
python3 -B experiments/python/dependency_bundles/index_benchmark.py --decode-diagnostic experiments/python/dependency_bundles/_work/runs/binary-index/results.json
```

It consumes the complete logical document from already loaded index bytes in 100 randomized trials per encoding and writes [decode-diagnostic.json](results/binary-index/decode-diagnostic.json). It excludes I/O, hashing, entry objects and range checks. Binary rows are materialized into an outer list for this diagnostic, whereas the real reader streams them. Its costs are not substitutes for the startup intervals in the full report.

Reproduce the precomputed-index comparison with:

```sh
python3 -B experiments/python/dependency_bundles/index_benchmark.py
```

This creates independent source/bytecode fixtures with 2,048 leaf modules, plus a 64 MiB larger-entry bundle. A versioned JSON sidecar stores producer-validated names, ranges, CRCs and directory names. Consumers verify the sidecar against a caller-supplied SHA-256 and either hash the entire bundle or check its previously admitted local file identity. The local mode requires a trusted immutable store; stat checks provide cache invalidation, not authentication. Both modes retain per-read CRCs, and the full-hash mode works across copied bundles. Sidecar creation/validation and storage are reported separately, while sidecar loading, hashing, decoding and consumer checks are inside startup timing. No ZIP parsing happens in the precomputed-index reader itself. The ordinary mapped reader is rerun as a control, with equal adapter setup. Use `--modules 16 --trials 1 --output /tmp/gaia-index-smoke` for a smaller smoke run; the larger-entry corpus remains 64 MiB.

Reproduce the warm-cache prefault comparison with:

```sh
python3 -B experiments/python/dependency_bundles/prefault_benchmark.py
```

It uses the retained raw-access archive plus a deterministic stored bundle of 64 one-MiB entries. Linux `MAP_POPULATE`, explicit page touching, and demand paging use identical bytes within each corpus. Each case measures open/index (including prefaulting), first scan, and reused scans, with process-wide minor/major fault deltas collected outside the timed intervals. Both bytes and views retain CRC checks; full SHA-256 equivalence follows timing. This requires Linux `MAP_POPULATE`; no cache dropping or cold-storage inference is involved. Use `--archive` to replace the small corpus and `--output` to retain a separate run.

Reproduce the phase/floor diagnostic against retained persistent-run inputs with:

```sh
python3 -B experiments/python/dependency_bundles/diagnose.py
```

It runs four directory/provider source/bytecode cases plus no-op and harness-setup probes, 15 fresh processes each. Profiles are collected separately from unprofiled timings. Profiled self/cumulative times are not interchangeable with unprofiled wall time; cumulative values overlap. The original measured run is preserved.

Fresh process does not mean cold filesystem cache. Fixture generation, validation, and warmups have already touched inputs. Source-only cases use no fixture bytecode and `-I -S -B`; precompiled cases use the same generated bytecode in both layouts. Precompilation and packing/export costs are reported separately. Process peak RSS uses `/proc/self/status` `VmHWM`, includes common setup/validation, and is not an isolated incremental archive-memory measurement. The first saved run has a separate one-process-per-case memory pass because inherited parent `ru_maxrss` was detected; its original diagnostic values remain labeled in JSON. New runs collect `VmHWM` with each trial. A saved run's supplemental pass can be reproduced with `--memory-pass path/to/results.json`.

Workers validate every fixture module's origin/loader, resource hashes, application checksum, missing-module/resource behavior, and absence of source-tree bytecode generation. Archive construction validates member equivalence and rejects unsupported/duplicate/colliding names. Correctness tests include no-fallback and resource-tampering failures.

This establishes a synthetic load-path baseline. It is not a measured claim about arbitrary Python distributions, native extensions, compiler builds, remote storage, or the user's physical developer laptop. The available execution environment is recorded honestly in the results.

## Admitted stdlib snapshot reproduction

```sh
python3 -B experiments/python/dependency_bundles/stdlib_benchmark.py
```

This uses regenerated `_work/runs/path-index/results.json` application inputs and the 118 checked-hash stdlib source/bytecode pairs recorded in `_work/runs/path-index/diagnostics/host-io.json`. The installed interpreter and sources must still match those inputs. No downloads or installation occur. Use `--trials 1 --output /tmp/gaia-stdlib-smoke` for a smoke run. The default is 15 randomized trials per provider after correctness warmups: installed host, admitted known-path directory, Python binary-index mmap and Odin binary-index mmap. Every process uses the same dependency bundle/index/native reader, discovery implementation and post-workload source-inspection checks. Conversion is reported separately; descriptor reading, manifest validation and mounting are timed. Full-process timing also includes common interpreter/harness preparation and validation.

[build_stdlib_snapshot.py](build_stdlib_snapshot.py) admits checked bytecode against source and exact runtime/build/platform/optimization identity, packages both, and records input SHA-256 identities. Nested code filenames are rewritten to stable `gaia-stdlib://` origins for source inspection; instructions and line information remain. [stdlib_snapshot.py](stdlib_snapshot.py) uses the existing readers through one provider interface. It validates the pinned manifest, headers and per-payload CRC without repeating source hashing at import. Its directory control has the same manifest, relocated code and CRC policy, isolating mapped access from admission policy. Modules outside the observed closure, native extensions and unbundled package data retain host fallbacks. Admitted inputs must remain immutable; this is an experimental v1 local format, not a complete relocatable Python distribution.

Collect traces separately from timing:

```python
import json
from pathlib import Path
import subprocess

base = Path('experiments/python/dependency_bundles').resolve()
data = json.loads((base/'results/stdlib/results.json').read_text())
work = base/'_work/stdlib-diagnostics'
work.mkdir(exist_ok=True)
for case in data['cases']:
    name = case['variant']
    command = work/(name+'-command.json')
    command.write_text(json.dumps(case['command']))
    subprocess.run([
        'strace', '-qq', '-f', '-T', '-yy', '-e',
        'trace=%file,fstat,fstatfs,read,pread64,close,lseek,getdents64,mmap,munmap,write',
        '-o', str(work/(name+'.trace')), 'python3', '-I', '-S', '-B',
        str(base/'django_probe.py'), '--command', str(command),
        '--result', str(work/(name+'-trace-result.json')),
    ], check=True)
```

Then run `python3 -B experiments/python/dependency_bundles/summarize_stdlib_trace.py`. It verifies consumer identities, application output and stdlib import state against the parent run, and counts only the marked application workload. Interpreter/harness preparation and post-workload inspection are outside that trace scope. Ptrace permission is required. Zero read syscalls for mapped payloads do not imply zero page-cache/storage traffic. Timing ranges overlap substantially; the report preserves that variability rather than inferring a stable provider ranking.

## Bytecode handoff reproduction

```sh
python3 -B experiments/python/dependency_bundles/handoff_benchmark.py
```

The [handoff comparison](results/handoff/REPORT.md) uses the retained Odin/stdlib-snapshot command from `results/stdlib/results.json`. It compiles a fresh bridge once and uses that same binary for all cases: owned bytes plus header slicing, owned bytes plus a body memoryview, or direct native validation/unmarshalling from the mapped entry. The CLI option is `--bytecode-handoff bytes|view|native`; the default remains `bytes`. Source and ordinary resource reads retain their existing path. No storage format changes.

All modes retain native CRC, bytecode magic/flags checks, admitted stdlib source-hash checks and code-type/origin validation. CPython's direct marshal API emits the normal `marshal.loads` audit event; with hooks installed it constructs an owned audit payload, so the native path is only free of intermediate payload copies without hooks. The application has an audit hook and its cost is included. Direct decoding holds the GIL and defers reader unmapping across reentrant audit callbacks or finalizers; no borrowed mapped view escapes into Python.

The isolated diagnostic decodes the application's 460 dependency code loads and 118 stdlib modules without executing them, with reader opening outside the decode clock. It validates resulting code against the bytes control after closing the timed readers. The separate real-application comparison includes reader mounting/setup and preserves all application/resource/origin/execution and source-inspection checks. Counters verify every target code load uses its selected path. Full process for the isolated diagnostic includes a second reference decode and is not a measure of decoding alone. Use `--trials 1 --output /tmp/gaia-handoff-smoke` for a smoke run; default trials are 15 fresh processes per mode per workload, randomized after correctness warmups.

## Precomputed catalog reproduction

```sh
python3 -B experiments/python/dependency_bundles/catalog_benchmark.py
```

The [catalog comparison](results/catalog/REPORT.md) uses the retained Django command and immutable inputs from `results/stdlib/results.json`. It builds one native bridge and holds the bytes+slice handoff and reconstructed stdlib reader fixed. The dependency reader either rebuilds the catalog, loads pinned name-to-row metadata with lazy entry wrappers, or additionally adopts producer-built module/package/discovery tables. Catalog reading, hashing, decoding and table adoption are inside application/setup timing. CLI options are `--catalog-mode rebuilt|rows|tables`, `--catalog PATH` and `--catalog-pin SHA256`; rebuilt remains the default.

[precomputed_catalog.py](precomputed_catalog.py) derives a versioned, SHA-pinned local acceleration artifact bound to the binary-index digest and interpreter/build/platform identity. It validates the admitted local archive/index and rejects ambiguous source/bytecode module names when deriving tables. It uses Python marshal for this experiment; it is not a proposed open standard. Existing binary-index validation, immutable local admission, per-read CRC, payload bytes, package discovery/misses, resources and source inspection remain. Consumers still allocate deserialized dictionaries and strings. Odin's existing native validation and native name/directory-buffer construction remain unchanged.

The same runner generates stored archives with 1,024, 16,384 and 131,072 trivial bytecode leaves, one package initializer and one resource. Every scaling observation imports the same first 32 leaves (33 code loads), separating available-catalog size from executed-module count. Fixture/index generation and additional catalog production/storage are reported separately. Fresh-process peak RSS includes common imports and validation; it is not metadata-only memory. The default is 15 randomized fresh processes per workload/mode after warmups. Use `--modules 128 2048 --trials 1 --output /tmp/gaia-catalog-smoke` for a smoke run. These scaling fixtures do not establish typical ecosystem module counts, and fresh processes still use a warm filesystem cache.

## Native bounded catalog reproduction

```sh
python3 -B experiments/python/dependency_bundles/native_catalog_benchmark.py
```

The [native catalog comparison](results/native-catalog/REPORT.md) reuses all admitted inputs and precomputed artifacts from `results/catalog/results.json`. It runs rebuilt, precomputed Python tables and native-only metadata with one freshly compiled bridge, the same bytes+slice handoff and reconstructed stdlib reader. Default trials are 15 randomized fresh processes for each of the four workloads and three modes. Use `--trials 1 --output /tmp/gaia-native-catalog-smoke` for a smoke run, or `--workloads django 131072` to select cases. Compilation is outside consumer timing; native index validation, arena initialization and hash/child-link construction are inside setup.

[native/live_catalog.odin](native/live_catalog.odin) holds strings as mapped-index views and puts all variable-size persistent native metadata into one mmap arena: directory views/name offsets, file/module/directory hash slots, and file/module child lists/counts. The default logical arena capacity is 16 MiB; `--budget BYTES` controls it. Required tables must fit or open returns `MemoryError`. There is no implicit growth or silent policy change. The fixed Odin handle and CPython shim are separately allocated. Arena page rounding, mapped input pages, temporary path/hash/OpenSSL allocations and all Python allocations are outside this metadata bound. Peak RSS measures the process separately; the arena capacity is not an RSS limit.

[native_catalog.py](native_catalog.py) supplies lazy mapping/resource/discovery adapters to the existing loader. It does not export all names or build Python dictionaries per available module. Requested lookups create owned Python strings/specs; enumeration creates objects for requested children. File and module child links avoid scanning/decoding every archive member for package enumeration, and native directory filtering precedes decoding of resource subdirectory names. Native open still scans the entire admitted index and constructs native tables, so total setup remains linear in available metadata. Its mappings/arena live until close; close is deferred across active native decoding, including reentrant audit callbacks.

`django_worker.py --catalog-mode native --catalog-budget BYTES` enables the path for dependencies; native extensions, unbundled module/data fallbacks and the stdlib reader retain their previous loaders. Rebuilt remains the default. Every observation preserves application/resources/origins/source inspection and CRC/header checks. Fixed-import scaling records lookup/name counters before validation and checks they stay small as the unused catalog grows. The scaling worker validates discovery boundaries by membership instead of building every child tuple; process/RSS include validation. Tests cover insufficient/exact budgets, stable allocation under lookups, bad indexes, ambiguous modules, Unicode/resources/enumeration, no host probing or bulk export, CRC failure, and retained code after a reentrant close.

## Producer-built mapped lookup reproduction

```sh
python3 -B experiments/python/dependency_bundles/mapped_catalog_benchmark.py
```

The [mapped lookup comparison](results/mapped-catalog/REPORT.md) retains the exact inputs from `results/native-catalog/results.json` and runs rebuilt, runtime-native and directly mapped native catalogs with one newly compiled bridge. No industry-tool experiment is included in this stage. Use `--trials 1 --output /tmp/gaia-mapped-catalog-smoke` for a smoke run, or `--workloads django 131072` to select workloads. Default trials are 15 randomized fresh processes per case, after correctness warmups. Production and compilation are separate costs; all consumer verification/validation is inside startup timing.

[mapped_catalog.py](mapped_catalog.py) constructs the existing bounded native catalog, checks every file/ordinal, module/member and directory binding against the admitted range index, and exports its integer tables. Experimental format v1 has a 256-byte header (magic/version/flags/index SHA/counts/capacities/offsets/size), directory offset/length records, and aligned little-endian u64 arrays for name offsets, file/module/directory hash slots, child heads/counts and next links. Zero is the empty sentinel; row and directory references in lookup tables use ordinal+1. Offsets reference the pinned original range index. No pointers or native string descriptors are serialized. The zero-copy integer-array consumer currently targets Linux amd64; this layout is not yet a proposed standard protocol.

[native/mapped_catalog.odin](native/mapped_catalog.odin) maps that artifact read-only and keeps the existing lazy adapters. It hashes both metadata inputs, checks their binding, validates headers/table bounds/value domains/counts and original entry ranges/UTF-8, and retains archive identity/full-hash policy plus per-read payload CRC. Directory binding is checked. File/module lookup placement and child membership semantics are trusted producer-derived data; consumers avoid reconstructing those tables to prove them again. The artifact requires a trusted external SHA pin and immutable inputs, matching the precomputed-table admission model. Corruption or malformed structural references fail safely; probe/child iteration limits prevent unbounded loops.

Only directory string views are constructed in the mutable arena; integer tables stay in the mapped file. Arena budget/usage therefore covers less data, while mapped file pages remain part of process memory. Close owns index, lookup and archive mappings and defers release during native decoding. `--catalog-mode mapped --catalog PATH --catalog-pin SHA256` selects the path in the Django worker; the stdlib reader and bytes+slice handoff stay fixed. Rebuilt remains the default.

The report separates native-open integrity time, structural/setup time and runtime table construction for native and mapped cases. Integrity includes both metadata SHA checks in mapped mode and archive policy checks; none is moved outside the startup clock. Native open remains linear through input hashing and structural validation. The tests reuse native-catalog behavior/lifetime checks and add mismatched pins/bindings, rehashed malformed headers/offsets/row domains, truncation, bounded cycle detection, budget limits and cleanup.

The format version also covers FNV-1a 64-bit hashing, canonical module-name rules, linear probing and ordinal+1 sentinels. Changes to those meanings require a new version; no compiler struct layout is part of the serialized contract.

## Unified and compact metadata reproduction

```sh
python3 -B experiments/python/dependency_bundles/unified_catalog_benchmark.py
```

The [unified comparison](results/unified-catalog/REPORT.md) reuses retained inputs from `results/mapped-catalog/results.json`. It compares the current two-file mapped metadata with a single-file 64-bit control and a compact single-file variant, holding archive bytes, bytecode handoff, stdlib loading and common harness fixed. Default trials are 15 randomized fresh processes per case after warmups. Use `--trials 1 --output /tmp/gaia-unified-smoke` or select `--workloads django 131072`. Source mapped-artifact production is inherited; additional conversion/certification time and total metadata bytes are reported separately. Compilation/conversion precede consumer timing; authentication and validation remain inside startup.

[unified_catalog.py](unified_catalog.py) emits experimental unified v1: a 256-byte header, the exact original range-index bytes, directory offset/length records and mapped name/hash/child arrays. The wide control preserves sparse 64-bit tables. Compact mode uses 32-bit references when entry/directory counts and embedded-index offsets fit, sizes file/module hash tables independently, and permits up to 75% occupancy. It falls back to the wide layout for inputs that require larger references. Scalars are explicit little-endian values, empty slots are zero and references use ordinal+1; no pointers are serialized. Current zero-copy consumers target Linux amd64.

[native/unified_catalog.odin](native/unified_catalog.odin) authenticates the entire envelope with one trusted SHA-256 pin, covering both range data and lookup tables. The embedded original-index digest is producer-certified lineage checked against the requested input, not a second per-open digest. The consumer does not open the old separate index file. Tests verify byte-identical embedding and operation without that file present. Structural/range/UTF-8/value/count checks, bounded hash probing and child iteration, archive identity/full-hash policy, per-read CRC, budget enforcement and deferred mapping release remain. Lookup semantics retain the same trusted-producer admission model as mapped v1.

The CLI modes are `--catalog-mode unified|compact --catalog PATH --catalog-pin SHA256`. Rebuilt remains the default. Runtime adapters read either word width directly without widening the tables into arena allocations. Mutable arena data remains directory string views; mapped metadata and fixed handles remain outside that logical budget and are included in process RSS. Hashing/validation still scale with metadata size. The tests cover both widths, malformed/rehashed headers and references, count/offset bounds, cycles, source/bytecode/resources/enumeration, standalone use, full-hash archive checks, decoder lifetime, exact budgets and 64-bit fallback selection.

## Whole-process characterization reproduction

```sh
python3 -B experiments/python/dependency_bundles/process_characterization.py
```

The [lifecycle report](results/process-characterization/REPORT.md) reuses the retained compact artifacts and native binary from `results/unified-catalog/results.json`. It measures minimal interpreter, common harness, 1,024- and 131,072-leaf fixed-import catalogs, and Django. Default trials are 15 randomized fresh processes per workload/mode after correctness warmups: 300 timed processes. Use `--trials 1 --output /tmp/gaia-process-smoke` for a smoke run. This requires the parent artifacts to remain available; it does not rebuild them. The filesystem cache is warm.

Modes are uninstrumented normal exit, observed normal exit, observed deferred GC with a charged full collection, and diagnostic fast exit. Fast exit completes application validations and explicit provider/SQLite closes, then uses `os._exit`; it deliberately changes interpreter finalization semantics and is not a production recommendation. Batch mode restores the original GC enabled state. Worker RSS is sampled before the deferred collection, rather than at final process exit.

Optional worker flags are `-X gaia_phases=PATH`, `-X gaia_profile=PREFIX`, `-X gaia_gc=batch`, and `-X gaia_exit=fast`. The driver manages them. Monotonic parent/child clocks partition the full process, with child and parent CPU tracked separately. Separate per-phase cProfile runs, compile-event audits and import-time graphs run after the timed trials. Profiles change execution/import state and do not supply benchmark observations. Output/resource/source-inspection/origin/execution checks remain enabled. The normal workers continue without observation by default.

Results retain every sample, lifecycle/GC events and commands. Full function profiles are in `profiles.json`; source-compilation filenames/sizes and import graphs are in `diagnostics.json`. The [findings](FINDINGS.md#whole-process-lifecycle-characterization) distinguish bootstrap overhead, framework work and finalization, and record why advancing readiness by deferring GC did not reduce complete-process time. Absolute times shifted from previous runs; only matched comparisons establish results.

## Generic consumer bootstrap reproduction

```sh
python3 -B experiments/python/dependency_bundles/bootstrap_benchmark.py
```

The [bootstrap comparison](results/bootstrap/REPORT.md) uses the retained compact artifacts and native binary from the unified experiment. It creates isolated consumer source snapshots and ordinary producer-compiled sourceless bytecode variants. `thin.patch` in the recorded work directory contains the exact adapter refactoring: reader-independent resources, on-demand comparison and ZIP imports, and CLI-only argparse. It changes no dependency/framework/application code. Existing consumers remain the default; the experiment does not overwrite them.

Seven modes separate unchanged source, unchanged bytecode, thin source, thin bytecode, a programmatic thin-bytecode launch, and that launch with generation-zero GC thresholds multiplied by four or sixteen. Programmatic arguments come from the unchanged CLI parser at admission, are compiled as typed parameters, and are specific to that immutable configuration. Changing code, arguments or interpreter requires regeneration. Admission/snapshot compilation costs are outside consumer timing and reported separately. No live interpreter or initialized application state is reused. All consumers exit normally with GC enabled.

Default trials are 15 randomized fresh processes per mode/workload, 315 observations across two fixed-import catalog sizes and Django, plus correctness warmups. Use `--trials 1 --output /tmp/gaia-bootstrap-smoke` for a smoke run. Separate lifecycle profiles and compilation/import audits follow the timed trials. Source/bytecode/fixture hashes, exact launch source, native binary pin, commands, CPU/RSS and individual observations are retained. Narrower imports change the preloaded stdlib set; each worker still validates newly loaded admitted stdlib origins, normal native fallbacks and source inspection. Compare whole process, including shutdown, before attributing a readiness improvement to reduced work.

The [focused Django confirmation](results/bootstrap-confirmation/REPORT.md) reuses the admitted commands and runtime snapshots, with three launch modes in randomized blocks:

```sh
python3 -B experiments/python/dependency_bundles/bootstrap_benchmark.py --confirm experiments/python/dependency_bundles/_work/runs/bootstrap/results.json --trials 30 --output experiments/python/dependency_bundles/_work/runs/bootstrap-confirmation
```

This checks the retained source, bytecode, fixture and native binary hashes before reuse. The thin source adapters pass all 70 existing tests; the [test log](results/bootstrap/regression-tests.txt) and runtime-source comparison are retained with the main results. Across these retained runs, exact dependency and stdlib decode counts and origins also remain equal; import-set changes are permitted by the harness but were not needed here.
