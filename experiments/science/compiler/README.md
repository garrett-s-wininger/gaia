# Compiler parallelism and shared input generations

Two bounded experiments test different sharing boundaries. [Pass overlap](results/passes-frozen/REPORT.md) runs real LLVM analyses and speculative code generation from private copy-on-write IR snapshots. [Shared inputs](results/shared-inputs/REPORT.md) maps one sealed source generation into independent Python compiler workers. Read the [findings](../../../research/science/compiler/findings.md) and [run index](../../../research/science/compiler/experiments.json).

## Reproduce pass overlap

Use Linux and a matching Clang/LLVM 22.1.8 development SDK. Installed runtime libraries alone are insufficient: both source headers and version-matched generated LLVM/Clang headers are required. The measured host reused cached generated headers from the earlier compiler preparation. On a new machine, obtain the development package or configure the same LLVM source release to generate them; do not silently substitute another release's headers. Supply source/generated include roots explicitly below. Where a packaged SDK combines them, the variables may name the same directory. Library names can differ by package; these match the measured LLVM 22 installation.

```sh
mkdir -p "$WORK"
"$CLANGXX" -O2 -std=c++17 \
  -I"$LLVM_GENERATED_INCLUDE" -I"$CLANG_GENERATED_INCLUDE" \
  -I"$LLVM_INCLUDE" -I"$CLANG_INCLUDE" \
  experiments/science/compiler/pass_host.cpp \
  -L"$LLVM_LIB" -Wl,-rpath,"$LLVM_LIB" -lclang-cpp -lLLVM-22 -pthread \
  -o "$WORK/pass-host"
"$CLANGXX" -O2 -std=c++17 \
  -I"$LLVM_GENERATED_INCLUDE" -I"$CLANG_GENERATED_INCLUDE" \
  -I"$LLVM_INCLUDE" -I"$CLANG_INCLUDE" \
  experiments/science/compiler/child_lifecycle_test.cpp \
  -L"$LLVM_LIB" -Wl,-rpath,"$LLVM_LIB" -lclang-cpp -lLLVM-22 -pthread \
  -o "$WORK/child-lifecycle-test"
GAIA_PASS_HOST="$WORK/pass-host" GAIA_CLANG="$CLANG" \
  GAIA_CHILD_HARNESS="$WORK/child-lifecycle-test" python3 -B -m unittest discover -s experiments/science/compiler -p 'test_*.py' -v
```

Reproduce the [single-frontend IR study](../../compiler/followthrough/README.md) locally, retaining its source tree and completed `results.json` as `IR_RESULTS`. The origin contains commands referencing that locally generated private project: copying an old raw file alone is insufficient. The runner copies that tree into a fresh work directory, constructs fixed-context identities and prepares fresh stock-CLI object references. It uses the origin's compiler commands, so the selected compiler/SDK must remain available.

```sh
python3 -B experiments/science/compiler/run_passes.py \
  --host "$WORK/pass-host" --origin "$IR_RESULTS" \
  --work "$WORK/pass-case" --output "$OUTPUT/passes-frozen" \
  --lock "$MEASUREMENT_LOCK" --trials 3
```

`--work` must not exist. Supply a writable lock path whose parent exists. The lock covers each request, not preparation or a whole matrix. Object mutation and reference checking occur outside request clocks; complete measured requests include host handoff and object publication. The parent host must be single-threaded whenever it forks; a runtime `/proc/self/task` check enforces that bounded research contract. This adapter must not be transplanted into a multithreaded compiler service without another isolation design.

## Reproduce shared compiler inputs

Use Linux with sealed `memfd`, descriptor passing and readable `/proc/PID/smaps_rollup`. Python compilation and marshal output are interpreter-version dependent; the measured interpreter was Python 3.14.8. `STDLIB_SOURCE` names an actual compatible Python standard-library source directory. The runner excludes test/site-package directories, validates source compilation and pins every selected file. Another installation can select different files; compare its recorded identities rather than assuming an identical corpus.

```sh
python3 -B experiments/science/compiler/shared_inputs.py benchmark \
  --source "$STDLIB_SOURCE" --limit 16777216 \
  --workers 4 --requests 3 --units 20 --trials 3 \
  --work "$WORK/shared-case" --output "$OUTPUT/shared-inputs" \
  --lock "$MEASUREMENT_LOCK"
python3 -B -m unittest discover -s experiments/science/compiler -p test_shared_inputs.py -v
```

This fresh work directory also must not exist. Both controls admit the same sealed generation, verify its complete SHA-256 and use private interpreter/compiler state. One retains a private bytes copy; the other retains a read-only shared mapping. The broker's byte budget counts retained unique input generations, not total memory. Leases are cooperative and released after worker exit; arbitrary duplicated descriptors outside the broker are unsupported.

## Evidence boundaries

Keep binaries, copied projects and full raw observations ignored. Versioned summaries identify raw size/hash and frozen measured source pins. Postmeasurement review hardening is explicitly separated in each report; rebuilding current source does not reproduce the exact measured binary. Nine baseline tests passed before review hardening. The hardened code passes thirteen focused tests: eight native host tests, one child-lifecycle test method and four broker tests. Set both `GAIA_PASS_HOST` and `GAIA_CHILD_HARNESS` to run all thirteen; otherwise the corresponding native methods are explicitly skipped. The original two measured compiler command lines were additionally replayed through the hardened parallel/speculative host and matched fresh CLI objects. The performance matrix was not rerun. Current worker PSS samples are neither atomic peaks nor whole-system memory measurements. No compiler state or arbitrary process snapshot is shared, and Python source is compiled rather than executed.
