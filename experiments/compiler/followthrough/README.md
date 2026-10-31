# Share compiler inputs and frontend work

These experiments connect earlier native compiler results at three boundaries:

1. Parse/lower once, check exact current LLVM IR, and continue that same module through optimization/code generation on a miss.
2. Let one parsed translation unit feed code generation and an independent analysis of detached declaration records. Compare independent parsing with shared serial and shared parallel execution.
3. Build upstream Ninja's production C++ executable from an authoritative source generation, including generated inputs and a compiler-configuration change. Use the same generation for a small editor inspection/compile interaction.

The separate reproducibility probes exercise paths, environment inputs, source-date configuration and archive order. They establish concrete identity requirements, rather than assuming an invocation is described by source bytes alone.

## What the host does

`ir_host.cpp` is a Linux-local Clang 22 C++ API adapter. A JSON-line request runs one fresh compiler action. Clang's code generator receives AST events and produces a module; an additional consumer inspects that exact module before the backend runs. A miss neither serializes/reparses the module nor invokes a second frontend. A hit writes the retained object while the current frontend still emits current source diagnostics and dependency information.

Cache keys combine the caller's fixed-context identity, working directory, arguments (except the object destination), and the complete printed pre-optimization IR. The experiments pin a private project, baseline positive SDK dependencies, compiler/tool binaries and linkage before/after measurements. This is a bounded trusted experiment, not a proof of complete arbitrary-tool identity or resistance to racing writers. Only the explicitly seeded object is retained for the IR matrix; changed-source misses do not populate its cache.

LLVM backend errors are forwarded into the compiler's failure status. Entries with backend diagnostics are not admitted to the cache. Optimization remarks are outside this adapter's contract and `-R…` options are rejected. Coverage, optimization-record, plugin, module/PCH and arbitrary compiler side products have not been established. Generic diagnostic forwarding does not preserve the stock driver's full backend source-location presentation.

For shared analysis, the AST produces a small immutable vector of declaration names. A SHA-based analysis of those names then runs serially or concurrently with the backend. This is an analysis surrogate, not a real linter comparison or a portable AST interchange format. Threads never traverse a shared Clang AST: lazy AST state and compiler consumers are not assumed thread safe. The parallel `analysis_seconds` field measures launch-to-join elapsed time, including overlapped backend work; use complete endpoint timings for comparisons.

## Authoritative source generations

An admitted UTF-8 source collection lives in the host. Updates use an expected-generation check; editor inspection and compile requests can identify that same generation. Requests are serial, with one current generation and no durable service or multi-client protocol. A source-root routing filesystem resolves project files and failed lookups only against the admitted namespace. SDK paths outside that root remain physical.

Admission parses JSON, copies the map and builds an in-memory namespace; update timing includes those costs. It is deliberately simple and is not a zero-copy transport. Filesystem discovery, generated-header execution and persistent output writes remain explicit adapters. The graph's dependency selection uses a baseline compiler depfile set and known upstream generation rules. It does not implement a general build-system importer or discover changed SDK namespaces.

The scheduler is restricted to a controlled fixed-dependency edit trace. It does not refresh its dependency map after each compile or retain negative include queries. Newly introduced includes or optional-header appearance could therefore require work that this scheduler would miss. The optional-header unit tests establish the source provider's lookup behavior, not the scheduler's invalidation soundness. The earlier logical-generation checker remains a separate implementation with a stronger observed-condition contract.

In-memory source mtimes are normalized to zero. The tests demonstrate that `__TIMESTAMP__` can consequently differ from a physical CLI build. Supported graph commands use `-Werror=date-time`, as do the existing Zstandard requests, to reject timestamp/date/time builtins. General metadata-sensitive source compatibility requires a stronger input contract.

## Reproduce

Use the Clang/LLVM 22.1.8 toolchain from the [earlier compiler preparation](../README.md). Installed Clang headers and LLVM generated headers must both match those libraries. With caller-selected toolchain/work paths:

```sh
mkdir -p "$WORK"
"$CLANGXX" -O2 -std=c++17 -I"$LLVM_INCLUDE" -I"$CLANG_INCLUDE" \
  experiments/compiler/followthrough/ir_host.cpp \
  -L"$LLVM_LIB" -Wl,-rpath,"$LLVM_LIB" -lclang-cpp -lLLVM-22 -pthread \
  -o "$WORK/ir-host"
GAIA_IR_HOST="$WORK/ir-host" GAIA_CLANG="$CLANG" \
  python3 -B -m unittest discover -s experiments/compiler/followthrough -p 'test_*.py' -v
```

The IR matrix consumes the completed direct-frontend [semantic-invalidation experiment](../semantic_invalidation/README.md), including its retained private source tree. Reproduce that study locally first; its absolute paths are acquisition inputs, not a portable external format. Supply its `results.json` as `SEMANTIC_RESULTS`.

```sh
python3 -B experiments/compiler/followthrough/run_ir.py \
  --host "$WORK/ir-host" --origin "$SEMANTIC_RESULTS" --ccache "$CCACHE" \
  --output "$WORK/ir-results" --trials 3 --measurement-lock "$WORK/measurement.lock"
python3 -B experiments/compiler/followthrough/run_analysis_parallel.py \
  --host "$WORK/ir-host" --origin "$WORK/ir-results/results.json" \
  --output "$WORK/analysis-results" --trials 3 --measurement-lock "$WORK/measurement.lock"
```

The larger graph uses unchanged [Ninja 1.13.2 release sources](https://github.com/ninja-build/ninja/releases/tag/v1.13.2) and its upstream `configure.py` build description. Supply the [tag archive](https://codeload.github.com/ninja-build/ninja/tar.gz/refs/tags/v1.13.2) as `NINJA_ARCHIVE`; the report records its SHA-256. Native code, the generated Python browse header, a static archive and final executable are all verified against the CLI control. Labelled appended probes exercise source, header, generator and configuration changes. Both paths have one compiler worker; this is not a parallel scheduling comparison.

```sh
python3 -B experiments/compiler/followthrough/run_graph.py \
  --host "$WORK/ir-host" --archive "$NINJA_ARCHIVE" --clang "$CLANGXX" \
  --ninja "$NINJA" --ccache "$CCACHE" --output "$WORK/graph-results" \
  --trials 3 --measurement-lock "$WORK/measurement.lock"
python3 -B experiments/compiler/followthrough/run_repro.py \
  --clang "$CLANG" --ar "$ARCHIVER" --output "$WORK/repro-results" \
  --measurement-lock "$WORK/measurement.lock"
```

Use a fresh output directory for each run. Keep generated sources, objects, tool binaries and full `results.json` outside source history. The host/runner sources and binary hashes are checked for changes during the final matrices. A shared advisory lock prevents overlap between this research's measured lanes; unrelated system activity and preparation are not excluded by that lock.

The [host regression record](results/host-checks.json) lists the eight passing tests and exact test/host identities. They include failed compilation recovery, hit-path dependency output, namespace membership, generation conflicts and the explicit timestamp-metadata limitation.
