# Interpreter state reuse: resident templates help; disk restore needs evidence

Follow-up: the [real TypeScript dependency comparison](../typescript/REPORT.md) finds a fresh-process disk-restore win. The synthetic Node result below remains valid for its cheap metadata graph and is not representative of all large dependency initialization.

A single-threaded resident CPython template avoids substantial repeated initialization on the pinned Django workloads. This is **fresh-child execution from a live process**, not a cold serialized interpreter restore. When template creation and normal shutdown are charged, one-shot dependency/framework templates are slower than ordinary execution; reuse becomes worthwhile at roughly two requests in this run.

A separate synthetic Node check does perform disk restoration into fresh processes. Its startup blobs are slower than reconstruction on both tested graph sizes. These results support investigating reusable initialized state, not assuming any snapshot representation is automatically faster.

## Python complete-request results

Run `20261031T011606.163500Z`: CPython 3.14.8, Linux x86-64, seven randomized paired blocks. All variants use identical `-I -S -B`, precompiled dependency/fixture/harness code, and warm filesystem cache. The existing pinned Django core/REST fixture performs framework setup, all system checks, creation and seeding of a fresh in-memory SQLite database, a filtered ORM/API request and first admin-login rendering. Resource hashes, dependency versions/origins and complete controlled module sets agree.

| Request mode | Core ms | REST ms | Core wins vs exec | REST wins vs exec |
| --- | ---: | ---: | ---: | ---: |
| Fresh exec | 251.00 | 256.04 | — | — |
| Minimal interpreter template | 219.95 | 248.51 | 6/7 | 6/7 |
| Dependency imports template | 135.10 | 160.52 | 7/7 | 7/7 |
| Framework-initialized template | 105.27 | 130.94 | 7/7 | 7/7 |

Dependency imports move Django WSGI/checks/database/template imports into preparation; they do not initialize the app registry or create a database. The framework stage additionally calls `get_wsgi_application()` in the parent. That is an explicit workload preparation hook, not a generic interpreter capability. System checks, database setup, requests, resource/version/origin checks and normal finalization still run in every child.

The generic mechanism is a workload interface with preparation and request hooks, a serial template process, IPC and a new child per request. Template settings, input corpus, runtime, cwd and import paths are fixed. The old dependency-loader measurements used different harnesses; their absolute times must not be combined with this fresh comparison.

The timed request includes parent request encoding/transmission, fork, execution/validation, reply transmission, **normal CPython child finalization**, template wait and reply arrival. The controller decodes the returned JSON and compares semantics afterward. Fresh exec includes spawn/exec/interpreter startup and ordinary exit. Child code returns through `main`/`sys.exit`; it never substitutes `os._exit`. An `atexit` marker regression verifies finalizers complete before the reply is accepted.

## Startup cost and amortization

Input extraction, hash verification and bytecode production cost 2.76 s, separately from all consumer clocks. That fixture production is common to the controls; it is not a repeated consumer gain. Each template is started once and shut down once. Startup/shutdown figures below are single observations, not latency distributions.

| Scenario / template | Creation ms | Shutdown ms | One request including lifecycle ms | Five requests, average ms | Modeled break-even requests |
| --- | ---: | ---: | ---: | ---: | ---: |
| Core minimal | 18.17 | 5.81 | 243.93 | 224.75 | 1 |
| Core imports | 117.44 | 38.99 | 291.53 | 166.38 | 2 |
| Core framework | 170.27 | 54.13 | 329.66 | 150.15 | 2 |
| REST minimal | 16.98 | 5.50 | 270.98 | 253.00 | 3 |
| REST imports | 111.99 | 32.34 | 304.86 | 189.39 | 2 |
| REST framework | 164.99 | 60.66 | 356.59 | 176.07 | 2 |

Averages are `(measured creation + N × median request + measured shutdown) / N`; they are modeled, not measured N-request session distributions. The request samples do execute successive independent children, but this is a short run, not a longevity/memory-growth study. Full template creation+one request is not a cold-start improvement for import/framework templates. A service or editor session could amortize it; standalone occasional commands might not.

## Residency and isolation

| Scenario / mode | Child RSS after work MiB | Child PSS MiB | Child private dirty MiB |
| --- | ---: | ---: | ---: |
| Core exec | 49.92 | 38.10 | 36.14 |
| Core imports | 45.60 | 30.92 | 22.64 |
| Core framework | 44.45 | 29.46 | 19.98 |
| REST exec | 52.00 | 40.19 | 38.21 |
| REST imports | 47.81 | 33.13 | 24.87 |
| REST framework | 46.49 | 31.62 | 22.27 |

Ready template RSS is about 40 MiB for import templates and 46–47 MiB for framework templates, in addition to the child. Shared pages make RSS addition misleading. All six templates are resident during the main comparison, which can also affect proportional sharing. Template-ready and child-after-work PSS are sampled at different moments and must not be added as a simultaneous aggregate. These observations show sharing/private dirtiness, not a total-system memory reduction or a bounded-memory production service. `/proc` memory collection is inside every request clock.

Each fork starts from the same parent Python heap. Child global mutations and database state disappear with the child; external side effects would not. Requests bind argv and environment; the global `random` generator is reseeded. This does not reset arbitrary `Random` instances, native RNGs, cached environment decisions or imported library resources. Settings/scenario/template-loader environment and cwd mismatches are explicitly rejected. Other env values may already be cached by arbitrary imports; only the tested request fields have established behavior.

Templates are rejected if more than one OS thread or an open descriptor beyond stdio exists before forking. Network attempts are rejected in the fixture. This deliberately excludes many real applications and native extensions; consumer hooks would have to close/reopen resources and establish safe identity/invalidation. [CPython documents fork/thread hazards and the single-threaded forkserver model](https://docs.python.org/3.14/library/multiprocessing.html#contexts-and-start-methods). Filesystem immutability during an admitted session is a research assumption, not automatic live-edit invalidation. This is Linux-only; it does not establish Windows/macOS behavior or persistence across template death.

## Actual serialized disk restoration: small Node control

Run `2026-10-31T01:16:21.991744+00:00`, Node v26.12.0, seven paired blocks. A single script constructs an array and map of synthetic dependency-like metadata. The restored entrypoint checks lookups and binds env/argv from the current invocation. Every observation is a fresh process with normal exit and warm pages; no resident Node server exists.

| Graph | Ordinary exec ms | Disk restore ms | Restore wins | Blob size MiB | Blob creation ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Empty | 26.33 | 31.75 | 0/7 | 6.87 | 233.52 |
| 100,000 records | 98.91 | 120.20 | 0/7 | 26.43 | 959.05 |

This is a genuine negative result for these two synthetic graphs. The metadata graph is relatively cheap to reconstruct while restoration consumes a 7/28 MB blob. It does not measure a real import-heavy Node tool or prove disk snapshots cannot win with other initialization. The empty control exposes blob-restore overhead; the larger graph shows serializing an object graph can still cost more than reconstructing it. Blob creation is separate and makes amortization worse here.

[Node's official startup-snapshot documentation](https://nodejs.org/docs/latest/api/cli.html#--build-snapshot) supports a serialized blob and deserialize entrypoint, with bundling and built-in serialization constraints. [Deserialize callbacks](https://nodejs.org/docs/latest/api/v8.html#v8startupsnapshotadddeserializecallbackcallback-data) can reacquire runtime resources. Our blobs are built for this exact runtime; cross-version/machine portability is not established. No serialized CPython heap restoration was implemented. No `criu` executable was available; OS checkpoint/restore would be a separate kernel/resource-admission experiment, as described by [CRIU](https://criu.org/Checkpoint/Restore).

## Evidence and next question

All [five regression tests](correctness-tests.txt), [56 Python operations](validation.json) and [28 Node operations](node/validation.json) pass. Warmups are separately validated and excluded from sample counts. See [Python summary](summary.json), [Node summary](node/summary.json), [input/source provenance](provenance.json) and [reproduction](../../README.md). The generic runner rejects threads/resources, tests failed-child recovery, unknown/oversized requests, mutable-state isolation, env/cwd identity and normal finalization.

The useful next question is whether a real developer tool can offer a safe reusable preparation boundary with a worthwhile session lifetime. A true disk-restore experiment needs an initialization workload costly enough to beat measured restoration, plus rebuild/version/resource costs. Neither result justifies another dependency-container micro-optimization or an arbitrary application snapshot promise.

Raw `results.json` and `node/results.json` are ignored local artifacts, registered in the [repository evidence manifest](../../../../../research/evidence.json). Frozen Python experiment sources are retained in the ignored run's `sources` directory and hashed in raw/compact provenance; generated wheels, bytecode and Node blobs are not version controlled.
