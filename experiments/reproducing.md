# Reproducing the research

Run commands from the repository root. Start with a fresh work tree and generate each predecessor dataset on the machine being measured. Published `results/` files preserve observations, including original paths, hardware details and tool identities; they are not execution plans for another checkout.

New runs default to ignored `_work/runs/` directories within each experiment. Inputs, compiled adapters and temporary files also stay under `_work/`. Commit readable reports, acquisition manifests, provenance and validation summaries. Full observations (`results.json` and compressed copies), profiler captures and trace replay plans stay ignored, including under `results/`. The [evidence manifest](../research/evidence.json) records original raw-artifact paths, sizes and SHA-256 values; those files are absent from a clean checkout and no download location has been published. Regenerate inputs locally. Publish raw artifacts separately and record a verified download location when one exists.

## Prerequisites

Choose the track before installing tools. Artifact transfer needs Python and local loopback sockets. Native compiler experiments need Odin and matching LLVM libraries. Interpreter-state work uses Python and Node; the Ruby, .NET and JVM tracks need their own pinned runtimes. Each experiment README records acquisition, versions and verification. The [experiment map](README.md) links every track.

The native experiments currently target Linux x86-64. Use Python with `ensurepip` (including its bundled pip wheel), Odin, a C toolchain and the usual build tools. Compiler experiments also need compatible Clang/LLVM/LLD 22 binaries, development headers and shared libraries. The current linker adapters expect `libclang-cpp.so`, `libLLVM.so.22.1`, `liblldELF.so` and `liblldCommon.so` under the selected prefix's `lib/`; adapt and validate other packaging layouts before measuring them.

Put Odin on `PATH`, or set `ODIN` to its executable. Select your LLVM installation explicitly:

```sh
export GAIA_LLVM=/absolute/path/to/llvm-prefix
export GAIA_LLVM_HEADERS=/absolute/path/to/matching-development-include
```

Builders also accept `--llvm` and `--llvm-headers`. When `GAIA_LLVM` is set, headers default to its `include/` directory unless overridden. No original package mirror, extracted package directory or prebuilt adapter is required.

For Python installations without bundled pip wheels, set `GAIA_PIP_WHEEL` to a local pip wheel. The native loading driver also accepts `--pip-wheel`. The solver uses private vendored resolvelib APIs: its measured implementation targets resolvelib 1.2.1, so check the selected wheel's versions and run correctness tests before comparing another version. Do not silently equate a changed toolchain with the published environment.

## Artifact transfer

The first artifact baseline needs only Python's standard library and permission to open loopback sockets. It starts its own server process and generates deterministic content; no LLVM/Odin installation or remote infrastructure is needed for this protocol-shape comparison.

```sh
python3 -B -m unittest discover -s experiments/artifacts -p 'test_*.py' -v
python3 -B experiments/artifacts/benchmark.py --corpora small mixed --delays 0 2 --trials 7 \
  --output experiments/artifacts/_work/runs/first
```

Use a fresh output directory. The [artifact guide](artifacts/README.md) explains arbitrary directory inputs, bounded modes, cached/offline scenarios and timing boundaries. The injected delay is a sleep before each response, not a real WAN model. Avoid running artifact timing concurrently with compiler or other performance experiments.

## Compiler experiments

Start with the synthetic smoke test:

```sh
python3 -B experiments/compiler/benchmark.py --headers 8 --trials 1
```

Acquire the pinned zlib and Zstandard source archives using the URLs and SHA-256 values in the [compiler guide](compiler/README.md#real-project-zlib). Store them under `experiments/compiler/_work/downloads/`. Extract Zstandard into `experiments/compiler/_work/zstd-source/` so that `lib/` is directly underneath it. zlib extraction is performed by its driver.

Run the following stages in order. Each stage reads fresh predecessor outputs from `_work/runs/`, rather than the published results:

```sh
python3 -B experiments/compiler/project_benchmark.py
python3 -B experiments/compiler/pool_benchmark.py
python3 -B experiments/compiler/handoff_benchmark.py
python3 -B experiments/compiler/zstd_handoff_benchmark.py
python3 -B experiments/compiler/build_schedule_host.py
python3 -B experiments/compiler/schedule_benchmark.py
python3 -B experiments/compiler/build_cache_host.py
python3 -B experiments/compiler/object_cache_benchmark.py
python3 -B experiments/compiler/check_object_cache.py --host experiments/compiler/_work/cache-development/build/host
python3 -B experiments/compiler/check_cache_upstream.py
python3 -B experiments/compiler/build_dependency_hosts.py
python3 -B experiments/compiler/dependency_cache_benchmark.py
python3 -B experiments/compiler/check_dependency_cache.py
python3 -B experiments/compiler/check_dependency_fanout.py
python3 -B experiments/compiler/check_cache_upstream.py --results experiments/compiler/_work/runs/dependency-cache/results.json
```

The Zstandard driver selects the host from your completed direct-handoff run. Cache stages obtain exact compiler/linker paths from their admitted predecessor tool identities. Rebuild/re-admit after changing toolchains; bypassing identity checks would invalidate the comparison.

For process-lifetime and phase diagnostics, run `build_followup_hosts.py` after direct handoff, then `lifecycle_benchmark.py` and `profile_zstd.py`. Follow-up hosts are generated under `_work/followup-hosts/`.

Use `--trials 1` for benchmark smoke runs. Keep default output locations while running the chain: some diagnostic scripts expect them. If using `--output`, also supply matching downstream `--inputs`/`--results` wherever supported. Builders preserve existing binaries; use a fresh `--work` and matching `--host`/`--producer` to rebuild. Do not run several performance experiments concurrently.

For a matched existing-tool comparison, see [Ninja incremental builds](compiler/README.md#ninja-incremental-build-comparison). It generates its own pinned Zstandard fixture and does not need the preceding benchmark datasets. Ninja and ccache are explicit comparison dependencies; native toolchain setup is the same.

The later [logical workspace](compiler/README.md#authoritative-logical-compiler-inputs) comparison uses the same native backend with a different update-authority contract. The separate [C++ graph](compiler/cpp_graph/README.md) captures pinned fmt sources and a labelled integration fixture. Follow their guides for fresh cache seeds, input lifetimes and independent work-count checks rather than interpreting repeated-edit hits as compilation misses.

## Python loading and resolution

Synthetic loading and local resolution can be tested independently:

```sh
python3 -B experiments/python/dependency_bundles/benchmark.py --trials 1
python3 -B experiments/python/dependency_solving/benchmark.py --trials 1
```

Build fresh Python/Odin inputs before the Django or catalog comparisons:

```sh
python3 -B experiments/python/dependency_bundles/python_native_benchmark.py
python3 -B experiments/python/dependency_bundles/fetch_django.py
python3 -B experiments/python/dependency_bundles/django_benchmark.py
python3 -B experiments/python/dependency_solving/django_benchmark.py
python3 -B experiments/python/dependency_bundles/path_index_benchmark.py
```

Only acquisition requires network access. `fetch_django.py` reads the published URL/hash manifest and writes new local paths into a generated provenance file; it does not reuse the manifest's original artifact paths. An explicit `--library` can supply a newly built compatible extension to the Django driver without a preceding native benchmark.

The later loading chain is path-index diagnostics → stdlib snapshot → catalog → native catalog → mapped catalog → unified catalog → process/bootstrap characterization. See the [loading guide](python/dependency_bundles/README.md) for diagnostic commands and stage-specific options. Those stages consume predecessor commands and admitted identities: regenerate them in order rather than editing absolute paths inside a saved measurement.

For incremental/trail solver comparisons, first generate the initial dataset, then pass its `_work/runs/initial/results.json` to the subsequent variants. The [solver guide](python/dependency_solving/README.md) has the commands, differential tests and scaling controls.

## Measurement context

Record the actual machine, OS, tool versions, input identities, cache conditions and producer costs for every new run. Hardware information and observed paths belong in evidence. Machine-specific setup instructions, retained-binary dependencies and hard-coded checkout/toolchain locations do not belong in reproduction defaults. Compare controls within the same run; a new machine is not expected to reproduce the same absolute timing.

## JVM framework startup

The [Java startup experiment](java/startup/README.md) uses a local JDK and pinned Groovy/Picocli JARs, with every artifact verified before compilation/archive construction. It compares ordinary bytecode with static supplied classlists, explicit AOT class linking and separate process/constructor controls. No native image or application-trained cache is needed. Rebuild archives on the measured JDK and keep preparation, complete-process and intrusive diagnostics separate.
## Managed JVM compilers

The [JVM compiler experiment](java/compiler/README.md) creates a local jlink runtime and compatible default CDS archive, then optionally trains a compiler AOT cache. It compares actual pinned-source CLI/API compilations, normal lifecycle and independent complete-target queues. The target SDK remains an explicit separate input. Rebuild preparation on the measured JDK; no retained binary, source archive path or original worktree is required.

## Interpreter and managed-runtime startup

The [Python/Node state experiment](python/interpreter_snapshots/README.md) separates live templates, dependency snapshots and full TypeScript CLI work. Keep template creation, snapshot rebuilds, changing request inputs and normal shutdown in the documented lifecycle accounting.

The [Ruby experiment](ruby_startup/README.md) acquires pinned gems and compares a real RuboCop command with warmed Bootsnap and packed bytecode. The [.NET experiment](dotnet_startup/README.md) acquires a matching SDK/crossgen2 toolchain and compares composite Roslyn R2R with the shipping compiler's existing optimizations. Generated gems, SDKs, native images and caches belong in ignored work directories; use each guide's pinned fetch/preparation commands.

## Review a combined research change

Run `python3 -B tools/check_repository.py` and `git diff --check`. The repository check covers Markdown reports and topic guides, indexed paths, raw-data ignore rules and available evidence hashes. It also works in a clean source checkout where raw observations are absent. Run the affected experiment's regression tests; documentation consolidation alone does not require new performance measurements.

Keep local cache links, binaries and downloaded third-party inputs out of the commit. Reports retain their measured environment and source identities; current reproduction instructions should use caller-selected paths and regenerated inputs.
