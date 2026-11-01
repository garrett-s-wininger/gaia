# CPU-dispatched SHA-256 in the observation scan

This follow-up changes the implementation of the actual compiler host's SHA-256 helper, preserving its digest bytes, cache keys, symbol identities and generation checks. It compares LLVM's portable implementation with OpenSSL's dispatched implementation and the same library with its advertised CPU capabilities masked.

## Reproduce

Provide a prepared, stable Ninja fixture from the [workspace experiment](../workspace/README.md), compatible Clang/LLVM 22 headers/libraries, OpenSSL development headers and `libcrypto`. Do not use a project being mutated by another experiment. From the repository root:

```sh
mkdir -p "$TOOLS"
python3 -B experiments/integration/hash_dispatch/variant.py \
  --source experiments/integration/workspace/host.cpp --output "$TOOLS/hash-host.cpp"
"$CLANGXX" -O2 -std=c++17 -I"$LLVM_INCLUDE" -I"$LLVM_GENERATED_INCLUDE" \
  "$TOOLS/hash-host.cpp" -L"$LLVM_LIBRARY" -Wl,-rpath,"$LLVM_LIBRARY" \
  -lclang-cpp -lLLVM-22 -lcrypto -pthread -o "$TOOLS/hash-host"
GAIA_WORKSPACE_HOST="$TOOLS/hash-host" GAIA_CLANG="$CLANGXX" \
  python3 -B -m unittest discover -s experiments/integration/workspace -p 'test_*.py' -v
python3 -B experiments/integration/hash_dispatch/run.py \
  --llvm-host "$LLVM_HOST" --crypto-host "$TOOLS/hash-host" \
  --project "$STABLE_PROJECT" --ninja "$NINJA" --work "$WORK" \
  --output "$OUTPUT" --lock "$MEASUREMENT_LOCK"
```

`LLVM_HOST` is the original workspace host. `WORK` must not exist. The generator changes only the hash helper and writes the generated C++ into ignored work storage. It uses stack-owned SHA contexts through OpenSSL's low-level API to keep the substitution narrow. Those APIs are deprecated in OpenSSL 3; this is research evidence, not a production dependency/API selection. A production hash interface would need its own lifecycle and supported-provider decision.

The host variant passes the same object/index/invalidation regression suite. The scan study then initializes all 33 actual TUs through independent syntax/index requests in each of three native processes. Every timed result must match the original full index and current-generation validation. A final source change must invalidate the affected target and produce a new, equal identity in all variants.

Seven blocks shuffle three backends and two operations: retained scans, and admitting an unchanged generation before scanning. Each case performs ten requests. Clocks include JSON handoff, observation validation, fact identity assembly and response decoding. Admission is included in the second operation. Native startup, source admission and initial parsing are separately recorded preparation. Repeated requests within a block are not independent process starts or a latency percentile.

OpenSSL selects implementations from CPU capabilities at initialization. Its [documented capability override](https://docs.openssl.org/3.6/man3/OPENSSL_ia32cap/) supports the `OPENSSL_ia32cap=0:0:0:0:0` control used here. This masks library dispatch capabilities; it is not a claim that every instruction in the process is scalar. Hash/crypto ISA acceleration is distinct from the explicit integer-vector union study. No full build speedup is extrapolated from scan timings, and unchanged immutable identities are still recomputed rather than cached away.
