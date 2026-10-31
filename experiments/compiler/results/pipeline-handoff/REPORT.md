# Remove redundant handoff work and reuse the native process

Run `20261030T203622.432683Z`; seven randomized blocks, five engines, six scenarios. Same Zstandard 1.5.7 portable C target plus one probe, 31 objects, eight compiler workers, warm page cache. Every result matches independent CLI artifacts and runtime probes. All controls use the same newly instrumented native binary and exact compilation/link requests.

## Complete request results

| Operation | Previous memo ms | Inline snapshot ms | Inline + resident ms | Ninja ms | Ninja + ccache ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| unchanged | 3.56 | 3.37 | 3.37 | 3.20 | 3.08 |
| implementation | 96.26 | 91.25 | 67.44 | 65.45 | 97.55 |
| shared-header | 73.91 | 68.82 | 47.53 | 42.62 | 64.22 |
| generated-header | 75.34 | 69.11 | 47.28 | 42.66 | 64.36 |
| unused-header | 3.36 | 3.64 | 3.43 | 3.07 | 3.06 |
| revert | 65.56 | 58.92 | 43.66 | 65.84 | 24.82 |

The previous memo path's source-edit excess over Ninja falls from 30.81 to 1.99 ms: about 94% closed. Source-edit requests improve 29.9%, headers about 36–37%, and reverts 33.4%. Resident wins all seven paired changed-request blocks against both preceding Gaia paths. It wins only one of seven source-edit blocks against Ninja, and no header-edit blocks. Source edits remain about 3% slower; headers about 11–12% slower. This is near source-edit parity, not a general Ninja win. Reverts beat plain Ninja in every block but remain slower than ccache. All changed cases beat ccache except revert; no-op decisions remain about 3.4 ms.

## The redundant work

The parent already owned the admitted bytes and observed edits. The old path nevertheless rehashed the old bundle, serialized a delta, launched a separate native producer, authenticated and parsed the baseline, reconstructed a full snapshot and hashed/published it. `gaia-inline` publishes that same full snapshot directly from the caller's current admitted bytes. It still encodes, hashes and atomically writes the snapshot and masks; native authentication/framing checks still run. Added/removed files and changed visibility are supported by the direct publisher. This saves roughly 6–8 ms in preparation, while complete medians save about 5–7 ms because other stages vary.

`gaia-resident` also retains one serial native process. Every request still maps/adopts its inputs, validates candidates and journals, imports objects, creates private compiler filesystems on misses and links. The pool, mappings, dependency state and compiler workers are released before an explicit completion acknowledgement. No request filesystem, objects, journals or AST are intentionally retained. LLVM/LLD process initialization and internal global caches remain warm. The worker enters the request's output directory each time, including after that directory is recreated. Absolute fixture paths, explicit logical compiler cwd and ordered linker inputs are unchanged.

Process reuse saves about 15–23 ms beyond direct publication, depending on the operation. This includes warm native initialization/code paths, not just ELF loading. Source compile wall also falls from about 29 to 24 ms; link time can improve too. Do not attribute the entire gain to spawning a process.

## Where time went

| Source-edit stage | Previous memo ms | Inline snapshot ms | Inline + resident ms |
| --- | ---: | ---: | ---: |
| Preparation/snapshot | 16.04 | 9.30 | 9.15 |
| Full native process/request | 67.60 | 67.22 | 44.87 |
| Native setup | 14.73 | 14.87 | 14.33 |
| Compile wall | 29.19 | 29.36 | 23.94 |
| Link | 4.43 | 4.40 | 3.05 |
| Cache publication | 0.12 | 0.12 | 0.12 |
| Native report | 2.33 | 2.33 | 2.47 |
| Condition export | 9.62 | 9.55 | 9.31 |

Setup/compile/link/publication/report are nested inside the native clock; preparation and condition export are outside it. Independent medians do not form an exact partition. Native publication is only about 0.1 ms for a one-action miss and reporting about 2.3–2.5 ms. Those were not the large missing costs. The native report clock stops before final counter formatting/cleanup; the full native process/request clock includes them, and the resident completion acknowledgement follows request defers.

A separate [no-build diagnostic](startup-floor.json) measures 15 randomized observations per executable: invalid-argc native startup/exit takes 14.19 ms, the lightweight checker 1.11 ms, `clang --version` 16.92 ms and `ld.lld --version` 11.40 ms. These include dynamic loading, constructors/initialization and exit as applicable. They do not exercise a valid build request or partition ELF loader work. They support the process-lifetime diagnosis without substituting for the complete build clock. Reproduce with [startup_floor.py](../../startup_floor.py), supplying explicit local executable paths.

## Cold start, memory and failure

The resident process starts inside its first seed build, which takes 2.87 s including a complete 31-object compilation. Fresh memo/inline seeds take 2.85/2.81 s; Ninja 2.92 s. These are single setup observations, not a full-build performance conclusion or an isolated startup estimate. Initial SDK admission and fixture/reference preparation remain excluded equally. The randomized measurements assume an already-running worker; this architectural advantage must remain explicit.

The main worker handles 30 native requests: two seeds plus 28 timed changed requests. All recorded process high-water peaks are 228,945,920 bytes (218.34 MiB). This is a cumulative peak, not current idle/live RSS; a flat high-water mark does not prove zero allocation growth below that peak. The prototype has one request in flight, bounded argument frames and a fixed worker set, but no production hard memory quota, idle eviction, cancellation or automatic retry. Tests include repeated requests with 1 MiB admitted collections and a broad growth regression guard. Failed requests end the worker; a newly started worker recovers from disk state. Cache corruption remains a validated miss, as before.

Diagnostic-free requests are required by the benchmark. Worker stderr is spooled locally; forwarding arbitrary warning streams is not established as a production protocol. The private transport is an experiment, not a proposed open compiler service standard.

## Verification and scope

The main run checks 210 libraries and 6,510 object identities. [Compile-heavy checks](BOUNDARIES.md) add nine libraries and 279 objects: 219 libraries/6,789 object checks total. Every artifact, runtime probe, compiler/link count, fragment count, shared-tree count and native launch count passes. [Seventy-four tests](correctness-tests.txt) include exact direct/native snapshot equivalence with addition/removal/content/mask changes, corrupted snapshot rejection, history/corruption/negative lookups, request repetition, changed output-directory inodes and failed-worker restart. Resident test libraries are compared before invoking the independent reference so a misplaced worker output cannot be masked.

Each observation restores independent Ninja logs, outputs, caches and fragment state outside timing. Resident request state is torn down; persistent LLVM/LLD process globals remain resident across randomized blocks. The operation clock includes tool checks, request/namespace construction, a fresh lightweight checker, current-file discovery, snapshot publication/admission, native work through cleanup, index/cache export and receipt publication. Parent artifact/runtime verification and editor writes are outside all clocks. No-op and irrelevant-header gate hits send no native request. CPU accounting includes live-worker `/proc` ticks but is coarse and supports no fine-grained CPU claim.

This remains one C target, canonical regular files/implicit directories, fixed virtual metadata, an explicitly admitted namespace, stat-visible edits and a warm-cache virtual Linux host. Native setup still costs about 14 ms and Python condition export about 9 ms. Those are concrete remaining costs; the current data do not establish a fundamental floor or a broad production build-system advantage. Attribute admission hashing/parsing, mask/action preparation, retained-object validation/import and export separately before the next representation change.

[Summary](summary.json) retains medians/ranges, paired comparisons, cold setup, counters, source hashes and resident peaks. [Validation](validation.json) binds ignored local `results.json`; frozen sources remain in the ignored measured work tree. [Reproduction and transport details](../../README.md#remove-the-snapshot-round-trip-and-reuse-the-native-process).
