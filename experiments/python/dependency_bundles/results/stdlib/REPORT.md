# Admitted stdlib snapshot experiment

Run: `20261029T034650.363732Z`. Status: **complete**.

Same retained Django REST bytecode/dependency bundle, indexed discovery and native reader. The host control uses the installed stdlib. Other cases load the observed 118 pure-Python stdlib modules from an admitted code/source snapshot, using known-path files, Python mmap or the existing Odin reader. Native extensions and names outside this closure keep normal host loaders. No global hash-validation flag is changed.

## Admission and identity

The producer reads each source and checked-hash pyc, verifies interpreter magic, flags and source hash, and records input SHA-256 identities. It preserves bytecode instructions and line tables while replacing nested code filenames with a stable snapshot URI, retaining source for loader-based inspection. The manifest binds exact interpreter/build/platform/optimization identity. Consumers validate that manifest and the admitted pyc headers; payload reads retain CRC. This is an experimental v1 format.

Producer admission/pack/index cost: **441.197 ms**, outside consumer timings. Snapshot: `6ef15b171149652ca5be850ae7e1942156ab52337256a843bdc80462e8eb4fd0`; 118 modules. The directory control uses the same relocated code, source, manifest and CRC checks, separating snapshot-loader/admission policy from mapped-bundle access. Source and code are both retained. Bytecode still creates Python code objects at import.

## Startup comparison

15 randomized fresh `python -I -S -B` processes per case after one correctness warmup. Warm filesystem cache. Snapshot descriptor read, reader open, interpreter checks and mounting occur inside the application workload. Interpreter/common worker preparation still precedes that workload and remains in full-process timing. This is an application-phase closure, not a replacement for the interpreter’s own earliest bootstrap.

| Stdlib provider | Samples | Ready ms | Workload ms | Process ms | Snapshot code reads | Startup source reads |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| host | 15 | 496.714 | 541.979 | 992.417 | — | — |
| directory | 15 | 467.106 | 521.401 | 967.432 | 118 | 0 |
| python | 15 | 477.123 | 526.906 | 997.983 | 118 | 0 |
| odin | 15 | 464.270 | 516.196 | 976.361 | 118 | 0 |

Ready includes WSGI/framework initialization and system checks. Workload additionally includes the two-row SQLite fixture and first API/admin responses. Full process also includes common imports, identical module/function/class source-inspection checks for every provider, cleanup and output. Source-inspection validation occurs after the workload and intentionally reads snapshot source; the source-read column is captured before that validation. Independent medians need not add. Timings are variable: the readiness min–max ranges below show the spread; small differences between medians are not evidence of a stable ranking.

| Provider | Readiness min–max ms |
| --- | ---: |
| host | 366.553–554.938 |
| directory | 385.008–517.819 |
| python | 370.566–518.021 |
| odin | 371.864–495.120 |

## Compatibility and scope

Every observation must preserve dependency module origins/execution sets, API results, resources, app count and zero network events. Snapshot-loaded stdlib origins deliberately use stable URIs; names remain standard. Module/function/class source inspection is tested, including unit tests with changed host source files. Packages retain a host fallback path for unbundled children/data, and native extensions retain their host loader. These fallback paths mean the limited snapshot is not a fully hermetic Python installation.

The source/bytecode relationship is checked at admission against immutable inputs, rather than rereading loose source during each import. This policy is tied to the exact admitted snapshot and interpreter. It is not disabling checked caches globally or asserting arbitrary changed host files remain part of the same environment. Concurrent mutation of mapped/admitted files is unsupported, as in the existing reader experiments. Broader stdlib resource/process-spawn/debugger behavior needs its own compatibility coverage.
