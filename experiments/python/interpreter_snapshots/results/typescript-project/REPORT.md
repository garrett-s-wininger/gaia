# Full TypeScript project CLI: useful module reuse, cached stock CLI still leads

A module-initialization snapshot reduces the complete project operation from **799.01 to 737.54 ms** against the identical compiler API bundle, with seven paired wins. It **does not beat the competent stock CLI**: TypeScript's normal warmed Node compile cache takes **722.45 ms**, winning five of seven blocks against the snapshot. The smaller parse/transpile result did not establish a full-tool win.

This experiment also replaces the earlier unverified `perf_hooks` snapshot binding with an explicit forwarding adapter and deserialize-time rebinding. Actual project checking, extended diagnostics, changing source/config/cwd and normal CLI exit are validated. The upstream compiler and project sources remain unchanged.

## Real project and full operation

Run `2026-10-31T02:19:39.812347+00:00`; Node v26.12.0 and TypeScript 5.9.3 on Linux x86-64. The published `exponential-backoff` **3.1.3** library contributes ten production TypeScript files; a small runtime-changing consumer makes eleven. Upstream Jest specs are excluded. Both npm archives are pinned by SHA-512 integrity and SHA-256 identity in [provenance](provenance.json).

The explicit local tsconfig uses strict checking, ES2020/CommonJS, genuine ES2020/DOM standard libraries, **`skipLibCheck: false`**, `noEmitOnError`, declarations, declaration maps, JavaScript source maps and embedded source text. There are **57 program files**, including **46 standard-library files**; extended diagnostics report **49,324 library lines** and **244 TypeScript lines** in the boundary fixture. This is a small real library project, not an arbitrary large application or its upstream Jest suite.

The API entrypoints call TypeScript's genuine `executeCommandLine` implementation. Config discovery/parsing, file/module resolution, standard-library reading/parsing/checking, project type checking and **44 filesystem outputs** are inside the fresh-process clock. No AST, parsed standard library, project, diagnostic or emit result is prepared in the snapshot. Source changes each paired block and cwd alternates between two project directories created after snapshot generation.

Input edits, removal of the previous output directory and independent validation occur outside the clock. All controls perform the same operation with warm filesystem pages. This is a fresh process, not storage-cold media or a resident worker. All controls load a small runtime exit/clock probe. API controls additionally include their host adapter and a bounded roughly 0.5 ms live TypeScript-clock check; that cost is not removed from their latency.

## Complete matched comparison

Seven randomized blocks, five controls, **35 timed operations**:

| Entry | Median ms | Wins vs cached stock | Wins vs identical API bundle |
| --- | ---: | ---: | ---: |
| Normal `tsc.js`, warmed Node compile cache | **722.45** | — | 7/7 |
| `_tsc.js`, compile cache disabled | 771.30 | 0/7 | 6/7 |
| Ordinary compiler API require | 797.55 | 0/7 | 3/7 |
| Ordinary identical compiler API bundle | 799.01 | 0/7 | — |
| Default module-initialization snapshot | **737.54** | **2/7** | **7/7** |

The snapshot's 7.7% reduction against the identical bundle isolates a real initialized-module benefit. Stock CLI packaging is leaner than the full compiler API, and the modern `tsc.js` shim enables Node's compile cache automatically. Including that baseline changes the product conclusion: this snapshot has no demonstrated advantage over the best existing CLI path on this project. The approximately 2.1% median gap is a measured comparison, not a universal floor.

The stock cache is genuinely populated in a fresh local cache directory, then warmed before matched observations. First cache-creating compilation takes **783.61 ms** and leaves about **1.30 MiB** of cache payload. That is one complete first-use observation, not an isolated cache-construction measurement or a storage-cold latency distribution. API controls and `_tsc.js` explicitly disable the Node compile cache; the default stock shim retains its normal optimization. See [summary](summary.json) and [validation](validation.json).

## Snapshot creation, rebuild and memory

The compiler-init blob costs **577.94 ms** to create and occupies **19.05 MiB**. A separately charged rebuild takes **466.94 ms**, also about 19 MiB. These are single observations. Both build and rebuild produce **no serialization warnings**. Neither executes the measured project, preloads its standard-library ASTs or trains on its inputs.

At the median saving against the ordinary API bundle, construction alone amortizes over roughly ten invocations, before acquisition and other producer costs. There is no positive median amortization against the faster cached stock CLI. A compiler/runtime/host-adapter identity or pinned package-location change requires a new blob; ordinary project source/config edits are read at invocation and do not require rebuilding this module-only snapshot. Archive verification/extraction and bundle creation remain producer work.

Observed exit-time RSS is about **213 MiB** for cached stock, **232 MiB** for ordinary API bundle and **233 MiB** for snapshot. These are one observation per process aggregated by median, not peak PSS or a memory bound. A snapshot is not a general memory-saving claim. The source/API bundle, cached CLI and snapshot store different amounts of code/metadata; do not conflate their storage footprints.

## Bind current performance and request state

The unchanged compiler body receives `perf_hooks` through a [host performance bridge](../../typescript_performance_bridge.js). During blob creation a stable forwarding object exposes the narrow API TypeScript consumes, with no captured native performance handle. A Node [deserialize callback](https://nodejs.org/docs/latest/api/v8.html#v8startupsnapshotadddeserializecallbackcallback-data) binds the current process's real native performance object. Ordinary bundle execution uses the same bridge.

The runtime adapter refreshes `ts.sys.args`, current cwd and TypeScript's performance counters. It checks that compiler timestamps fall between current native timestamps, that native/compiler epochs match, and that actual TypeScript marks/measurements advance on the current clock. Real `--extendedDiagnostics` invocations match all fifteen labeled integer counters across stock and restored paths; timings must be nonnegative and bounded by the complete process observation. Native timing and memory values vary by process and are retained, not forced equal.

Compiler version, production environment and relevant watcher environment are constrained. Different runtime env tokens and cwd are checked through the actual compiler system. A retained build marker proves the compiler module is restored; actual source/config and standard-library work occur afterward. This proves the tested nonwatch CLI contract, not arbitrary Node builtins, compiler versions, debugger/profiler modes or persistent project services. Watch/build/incremental/tracing/profiling modes are outside the admitted CLI surface. File and library identities are admitted for the research session; there is no automatic cross-machine relocation or live compiler-package mutation protocol here.

Each positive operation completes genuine CLI exit and a synchronous exit marker. Unsupported snapshot version/environment can fail in the deserialize callback **before** runtime preloads register the exit marker. Those startup rejections require the exact expected error, nonzero exit and no emitted files; they are not counted as successful normal CLI executions.

## Correctness boundaries and evidence

All **35 measured operations**, **five warmups**, the first cache-creating operation and **29 correctness boundaries** pass. All [nine regression tests](correctness-tests.txt) pass, including [labeled-counter and stale-clock checks](../../test_project_diagnostics.py). Every valid build emits the same 44 JavaScript/declaration/map files as stock CLI, byte for byte. Each emitted consumer is independently run and returns the changing request sequence. All semantic diagnostic text and exit statuses agree.

Boundary checks cover semantic type errors, invalid module options, an ES5 target change, extended diagnostics, wrong compiler-version/environment context and rejected watch mode. A semantic error returns status 1 with no output. An invalid module-option config follows a noteworthy **stock TypeScript behavior**: status **2** with emitted files. The snapshot reproduces it; consumers must respect tool exit status rather than treat present output files as success.

The correctness harness required two corrections after main timing: compare labeled diagnostic integers instead of whitespace padding, and accept an absent runtime exit marker only for exact early startup rejections. TypeScript's memory-column width can shift every count's padding while all counts remain identical. Timed samples were checkpointed before these later checks; no timed engine or runtime adapter changed. Raw evidence records the frozen main driver plus the corrected boundary-harness checksum. The earlier discarded pilot had an incorrect invalid-config exit-status assumption; its timings are not pooled into this report.

See [reproduction](../../README.md#full-typescript-project-cli), [CLI driver](../../node_project_benchmark.py), [runtime adapter](../../typescript_cli_workload.js), [performance bridge](../../typescript_performance_bridge.js) and [input/source pins](provenance.json). The raw `results.json` is an ignored local artifact registered in the [repository evidence manifest](../../../../../research/evidence.json). Generated source copies, binaries, cache payloads and blobs remain ignored. This is a bounded research result, not a selected Gaia runtime or a complete TypeScript compatibility guarantee.
