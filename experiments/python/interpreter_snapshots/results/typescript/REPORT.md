# Real TypeScript initialization: audit and snapshot comparison

Follow-up: the [full project CLI comparison](../typescript-project/REPORT.md) retains a smaller snapshot gain against its API bundle, but the normal cached stock CLI is faster. The parse/transpile operation below is narrower than that full tool comparison.

The original synthetic Node experiment used a valid startup snapshot, but its cheap metadata graph was a poor stand-in for a large real dependency. This follow-up measures the published TypeScript compiler. The controls distinguish ordinary module loading, the identical single-entry bundle, and actual disk restoration with and without V8's snapshot code cache.

## What the original test actually retained

The [original script](../../node_graph.js) constructs its array and Map before calling `setDeserializeMainFunction(main)`. The retained `main` closure references both structures. Restoration launches `node --snapshot-blob ...` without an entry script, so it does not reconstruct them by rerunning JavaScript source. The 100,000-row blob grows from roughly 7 to 28 MB, and current env/argv plus lookup outputs were checked. Whole-process timing begins before launching Node and ends after stdout and normal exit; it did not accidentally time snapshot creation as restoration.

That test remains valid for its graph. It says little about parsing and initializing a 9 MB compiler module, thousands of functions/classes/tables, or an import-heavy application. Snapshot restoration and object reconstruction have different costs; neither result establishes a universal winner. The original negative evidence is preserved rather than replaced.

## Real dependency and preparation boundary

TypeScript **5.9.3** is acquired from the official npm registry, with pinned SHA-512 integrity and SHA-256 archive identity. Its distributed `lib/typescript.js` is **9,112,572 bytes**, exposing **2,244 API properties**. [Provenance](provenance.json) records the version, URL and pins. Third-party code and generated blobs remain ignored.

The upstream compiler body is embedded byte-for-byte in the standard CommonJS wrapper, preserving exports, `require`, `__filename` and `__dirname`. No compiler code is removed, patched or replaced with stubs. The ordinary bundle and both snapshot modes use this exact generated entrypoint. A separate stock `require` control checks whether packaging alone explains the result. Node's [single-entry snapshot restriction](https://nodejs.org/docs/latest/api/cli.html#--build-snapshot) motivates the bundle.

Preparation loads the compiler and retains its initialized API, functions, classes and tables. It performs **no request parsing, AST traversal, transpilation or request-result caching**. Default snapshot code-cache generation is compared with `withoutCodeCache: true`; these are runtime snapshot settings, not training on the measured requests.

The invocation reads two TypeScript sources from stdin at runtime: a generic/class/interface/async feature example and a syntax-error example. It parses and walks both ASTs, transpiles to CommonJS ES2020 JavaScript plus source maps, and reports structured diagnostics. The feature source changes between blocks. This is a real compiler-library operation, not complete project type checking, a language-server launch or a whole TypeScript ecosystem benchmark.

## Measured results

Run `2026-10-31T01:38:26.125132+00:00`, Node v26.12.0 on Linux x86-64. Seven randomized matched blocks, **28 complete fresh processes** after four validated warmups. Warm filesystem cache. The whole clock includes process creation, runtime/snapshot startup, reading the runtime request, actual compiler work, output and normal exit including its marker. Parent decoding and differential comparison occur after that clock. Blob generation is outside invocation timing.

| Mode | Full process median ms | Wins vs identical bundle | Wins vs stock require | Observed RSS MiB | Observed JS heap used MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ordinary stock require | 198.12 | 3/7 | — | 98.35 | 16.45 |
| Ordinary identical bundle | 201.57 | — | 4/7 | 97.98 | 16.39 |
| Disk snapshot, default code cache | **117.28** | **7/7** | **7/7** | 87.03 | 22.97 |
| Disk snapshot, no code cache | **132.41** | **7/7** | **7/7** | 83.63 | 21.82 |

Default restoration reduces complete operation time **41.8% versus the identical bundle** and **40.8% versus stock require**. The stock/bundle controls are close and inconclusive against each other; simply concatenating the module does not explain the gain. Removing snapshot code cache still wins, but costs another 15.1 ms by medians. This is a useful initialized-module result in genuinely fresh processes, independent of the earlier resident CPython template.

| Snapshot | Creation ms | Blob MiB |
| --- | ---: | ---: |
| Default code cache | 553.02 | 19.38 |
| No code cache | 396.77 | 14.23 |

These creation costs are single observations, not distributions. The complete comparison preparation takes 1.24 s including corpus verification/extraction, bundle writing and building **both** snapshots. Deployed/prebuilt blobs move preparation to a producer; they do not erase it. At the measured median saving, the default blob's construction alone amortizes over roughly seven invocations compared with ordinary bundle execution, before other producer costs.

Memory is sampled after compiler work. Lower observed RSS coexists with **higher JS heap used** in the restored processes; external/source-buffer accounting also differs. This does not establish lower peak memory, storage footprint or a general memory-saving architecture. All raw memory fields are retained in the [summary](summary.json).

All [28 measured processes](validation.json), four warmups and two additional source-absent restoration audits pass. All [seven regression tests](correctness-tests.txt) pass, including corpus integrity/version/path guards and the earlier isolation/lifecycle tests. The synopsis depends on actual compiler outputs, not merely a fast version string.

## State and lifecycle proofs

A marker read only during preparation differs from every invocation's environment. Restored results retain the build marker; ordinary controls report the current marker. The complete 2,244-property compiler API and exact version are checked. Both snapshot modes also produce the same compiler outputs after the upstream `typescript.js` file is temporarily hidden. They cannot silently fall back to reloading that file.

Every invocation changes current env/argv tokens and alternates cwd between two directories distinct from the build cwd. Both `process.cwd()` and `ts.sys.getCurrentDirectory()` must match that invocation. This establishes the tested fields, not arbitrary rebinding of all compiler environment/native state. All modes must match stock compiler AST counts, diagnostics, emitted JavaScript and source-map SHA-256 values. A runtime-registered exit handler writes the request token; its marker must exist after normal process exit.

Build warnings are retained in raw/compact evidence. Node specifically reports that `perf_hooks` serialization is not fully verified and runtime state may be out of sync after restoration. We do not suppress it or claim support for the full TypeScript performance, filesystem/watch, project-service or native-resource surface. The exercised parser/transpiler and request fields pass differential checks. [Deserialize callbacks](https://nodejs.org/docs/latest/api/v8.html#v8startupsnapshotadddeserializecallbackcallback-data) would be needed for explicit resource reinitialization when broadening the contract.

The runtime binary and source pins are fixed. This establishes no cross-version/machine snapshot portability or storage-cold-page result. Blob creation, size and observed memory are separate costs; faster invocation is not free producer work.

## Reproduction and retained evidence

See [reproduction](../../README.md#real-compiler-dependency-snapshot-comparison), [driver](../../node_dependency_benchmark.py), [runtime operation](../../typescript_workload.js) and [acquisition](../../fetch_typescript.py). The raw `results.json` is an ignored local artifact registered in the repository evidence manifest. Source and runtime hashes, frozen experiment sources and original build stderr are recorded in the raw run. No commit or generated binary is required for a new run on another machine.
