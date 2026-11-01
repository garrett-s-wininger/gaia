# Build and editor queries over the same current observations

This Linux Clang 22 experiment extends the earlier observed compiler host with an immutable project symbol index. It compares one frontend feeding build and query consumers with independently cached consumers running concurrently, plus Ninja + ccache and an independent cached query consumer.

## Reproduce

Use compatible Clang/LLVM 22 development headers and libraries, including matching generated headers. With absolute caller-selected work paths, from the repository root:

```sh
mkdir -p "$TOOLS"
"$CLANGXX" -O2 -std=c++17 -I"$LLVM_INCLUDE" -I"$LLVM_GENERATED_INCLUDE" \
  experiments/integration/workspace/host.cpp \
  -L"$LLVM_LIBRARY" -Wl,-rpath,"$LLVM_LIBRARY" -lclang-cpp -lLLVM-22 -pthread \
  -o "$TOOLS/workspace-host"
GAIA_WORKSPACE_HOST="$TOOLS/workspace-host" GAIA_CLANG="$CLANGXX" \
  python3 -B -m unittest discover -s experiments/integration/workspace -p 'test_*.py' -v
python3 -B experiments/integration/workspace/run.py \
  --host "$TOOLS/workspace-host" --archive "$NINJA_ARCHIVE" --clang "$CLANGXX" \
  --ninja "$NINJA" --ccache "$CCACHE" --work "$WORK" --output "$OUTPUT" \
  --lock "$MEASUREMENT_LOCK" --trials 3
```

Acquire the unchanged Ninja 1.13.2 tag archive using the earlier [production graph instructions](../../compiler/followthrough/README.md). Supply compatible native Ninja and ccache executables. `WORK` must not exist, and the lock's parent must exist. The fixture appends labelled probes to upstream sources and creates small include-choice headers. It is not an arbitrary build-system importer.

## What is shared

One host admits a source generation and runs a fresh Clang frontend only for invalidated translation units. An actual AST traversal collects project declarations with qualified name, kind, type, file and byte offset; immutable sorted records serve a fixed `gaia_` substring query over declaration records and a whole-index identity. This is a bounded declaration index, not a complete language server, semantic linter or portable AST format. It includes project-header records and may repeat them across TUs.

The same frontend supplies current code generation and that index. Observation validation tracks admitted content, failed lookups and directory queries. An IR hit refreshes both dependencies and facts; the scan checks current observations before returning retained query results. Content descriptions are cached within a generation and cleared on admission. Mutable Clang state is private to each request; no thread traverses a concurrently mutating AST.

The independent control uses the same observation-aware cache and admitted bytes in two separate hosts. Its build and syntax/index consumer run concurrently. The Ninja control has a cached standalone index host running alongside `ninja -j1` with ccache. These controls can use two active workers; the shared path uses one frontend/backend worker. Both current editor readiness and final build readiness matter. This first shared controller publishes the project-wide query after the build and link finish; earlier handoff is not implemented. That serialization is an implementation limit, not a necessary property of shared preparation.

For optional-header appearance/removal and earlier-include shadowing, the Ninja adapter explicitly removes the probe TU's object before invoking Ninja. The cache also uses preprocessor mode for these events: the [cache diagnostic](results/negative-cache/REPORT.md) rejects a stale direct-manifest hit. These declared hints compensate for missing namespace observations; they are not automatic generic Ninja invalidation. Changed objects do not seed the ccache control from prior oracle runs: each trace starts with a restored baseline seed.

## Correctness and clocks

Full physical stock-CLI compilation of every TU, linking and uncached physical syntax/index traversal supply each scenario's oracle outside measurement clocks. Objects, depfiles, executable identity and symbol records must agree. The executable also runs `--version`. A burst exercises multiple source generations and rejects stale scans before current publication; it cancels no already-running compiler pass.

Complete retained-operation clocks include physical edit application, generation admission, validation, compilation/query work, required linking and handoff. Cold preparation, full reference work and initial cache population are separately recorded. Worker CPU combines process ticks with controller/finished-child usage; it is an estimate. Current `smaps_rollup` worker samples are not atomic peaks or total-system memory. The host has one current source generation and count-bounded caches; it implements neither dependency-aware eviction nor a hard RSS budget.

The source namespace is authoritative and UTF-8; normalized mtimes and date/time builtin rejection follow the earlier adapter. Configuration namespaces must identify one immutable command per target. External baseline-positive SDK headers, tool/linkage identities and environment are pinned across each run; unseen SDK namespace effects remain outside the observation engine. Arbitrary side outputs, PCH/modules/plugins, symlink semantics, hostile writers, concurrent edits during a request and durable service recovery remain outside this bounded protocol. Preserve source/binary pins and rerun output oracles when changing the adapter.
