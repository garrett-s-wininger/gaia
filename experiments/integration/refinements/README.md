# Earlier facts, retained identities and precise result reuse

This continuation preserves the original workspace adapter and production fixture. A generator applies explicit checked changes to that source; generated C++ and compiled tools stay in ignored work storage. The comparison uses fresh physical Clang objects/depfiles, the executable and full declaration-index oracles.

## Reproduce

Use the matching Clang/LLVM 22 development SDK, including generated headers, and the Ninja 1.13.2 archive from the [workspace guide](../workspace/README.md). From the repository root, with absolute caller-selected paths:

```sh
mkdir -p "$TOOLS"
python3 -B experiments/integration/refinements/refine_host.py \
  --source experiments/integration/workspace/host.cpp --output "$TOOLS/refined-host.cpp"
"$CLANGXX" -O2 -std=c++17 -I"$LLVM_INCLUDE" -I"$LLVM_GENERATED_INCLUDE" \
  "$TOOLS/refined-host.cpp" -L"$LLVM_LIBRARY" -Wl,-rpath,"$LLVM_LIBRARY" \
  -lclang-cpp -lLLVM-22 -pthread -o "$TOOLS/refined-host"
GAIA_REFINED_HOST="$TOOLS/refined-host" GAIA_CLANG="$CLANGXX" \
  python3 -B -m unittest discover -s experiments/integration/refinements -p 'test_*.py' -v
python3 -B experiments/integration/refinements/run.py \
  --host "$ORIGINAL_HOST" --refined-host "$TOOLS/refined-host" \
  --archive "$NINJA_ARCHIVE" --clang "$CLANGXX" --ninja "$NINJA" --ccache "$CCACHE" \
  --work "$WORK" --output "$OUTPUT" --lock "$MEASUREMENT_LOCK" --trials 3
```

Build `ORIGINAL_HOST` with the unchanged workspace guide. `WORK` must not exist. The wrapper transforms the existing replay in memory, retaining its exact source/header/configuration fixtures and fresh full references. It records the generated replay identity. The Ninja + ccache control uses the refined standalone index, including its fast identity/configuration checks; it keeps the earlier declared membership hints and preprocessor-cache fallback.

## What changed

**Immutable identities.** File content IDs are calculated on changed admission, not every scan. Identical body admission retains its existing body/ID. Canonical fact identities are calculated when the fact set is produced and retained with it; response assembly copies digest/count/matching records. SHA-256 and the result fields remain unchanged. No OpenSSL or SIMD substitution is used in this continuation.

**Actual early publication.** The native host emits a generation/target-tagged frontend-facts frame before LLVM backend optimization/object emission. The controller publishes the current project query when facts for all invalidated targets have arrived, without waiting for the last backend or link. Receipt timestamps are measured in the client. Frontend facts are not build success: backend diagnostics and final completion remain separate. Requests are sequential; this is not a concurrent multi-client service or arbitrary-pass cancellation.

**Bounded result history.** Current observation checks can select an earlier result. Restoring a different object/depfile marks the build for linking even if no frontend runs. History uses LRU, at most eight versions per command group, 256 entries overall and a 128 MiB counted payload allowance. That allowance excludes container overhead, source/lexical caches, the separate IR cache and compiler/runtime memory. It is not a total-RAM quota or dependency-aware eviction policy.

**Conservative configuration projection.** Current command arrays and a caller-owned immutable SDK/environment family identify each target. Only valid, unreserved, object-like numeric `-D` definitions can leave the exact command key. All other options stay in it. Duplicate definitions, unknown options, command-line recording and macro-debug options fall back to exact contexts. Optimization, ABI, target, language and ordinary debug flags are not discarded.

For eligible changes, a retained result must pass current file/lookup observations and a lexical dependence check. Raw identifiers come from every loaded source/SDK buffer, including inactive source branches. Expanded aliases contribute replacement identifiers. Compiler-predefined names and repeated definitions are dependencies even when otherwise unused, preserving redefinition diagnostics. Effective command/macro-recording options also disable projection. Expanded token-paste invocations retain conservative character alphabets over replacement and actual argument tokens: a changed name that could be assembled from an invocation's characters forces invalidation. Unicode/cleaned identifiers and unavailable buffers disable projection. This deliberately over-invalidates; it does not infer semantic independence from changed output types or AST hashes.

SDK buffers are assumed immutable for the declared family. Baseline-positive SDK files, tools and linkage are verified before/after a run; arbitrary new physical SDK namespace effects and hostile writers remain outside the adapter. These are bounded Clang 22 research rules, not a universal compiler effect model or public protocol.

## Additional checks

[The scan study](results/scan/REPORT.md) replays the original retained-scan workload with original and refined hosts:

```sh
python3 -B experiments/integration/refinements/run_scan.py \
  --llvm-host "$ORIGINAL_HOST" --crypto-host "$TOOLS/refined-host" \
  --project "$STABLE_PROJECT" --ninja "$NINJA" --work "$SCAN_WORK" \
  --output "$SCAN_OUTPUT" --lock "$MEASUREMENT_LOCK"
```

The historical `--crypto-host` argument is reused only as a replay binding; both implementations here use the same LLVM SHA-256 helper. Use a stable prepared project, not the project currently being mutated by a workflow run.

[The handoff check](results/handoff/REPORT.md) compares the measured implementation/client with the hardened implementation on seven actual production-TU edits. Pass `--old-host`, `--new-host`, `--measured-client`, `--project`, `--ninja`, `--work`, `--output` and `--lock` to `check_handoff.py`. The older client can be reconstructed using the [measured-source patch](results/combined/measured-source.patch) in a disposable copy of this source tree. Never patch the working source merely to read the evidence.

The full matrix preceded failure-path hardening: explicit cached compilation now restores deleted outputs, interrupted materialization invalidates its publication marker, the client drains complete pending frames before polling again, and compiler predefined/recorded-metadata guards preserve configuration diagnostics. Historical source/binary pins remain distinct. The patch maps current files back to the measured versions; apply with `patch -p1` inside the refinements directory of a disposable source copy. Current focused checks and the supplemental actual-TU handoff validate the hardened path; no full-matrix timing-equivalence claim follows.
