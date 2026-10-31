# Native compiler experiment notes

For current conclusions and practical limits, start with the [research review](../../research/compiler/findings.md). These notes retain the detailed experiment comparisons; measured reports remain under `results/`.

The [baseline-seeded C++ graph](cpp_graph/results/baseline-seeded/REPORT.md) measures four targets/six TUs using real upstream fmt plus labelled integration fixtures. Source/header/revert take 293.49/382.32/55.10 ms versus Ninja + ccache at 397.91/423.45/71.18 ms, with 3/3 paired wins and exact compilation/link counts. Both object caches reset to baseline each block; shared immutable input caches remain warm. Whole-link history is disabled for both. Repeated-edit history hits are published separately.

[Authoritative logical generations](results/logical-inputs/REPORT.md) reduce source edits to 42.25 ms versus the same-host physical adapter's 48.78 ms and low-fanout headers to about 21 versus 28 ms (7/7 paired wins). All 213 tests and 174 measured builds pass. This is an explicit editor/source-control API contract: admitted immutable bytes are authoritative, unreported physical edits are not. Strict physical import remains separately charged; the in-process checker preserves tool/output/negative/current-generation guards.

[Sealed bases and explicit overlays](results/shared-inputs/REPORT.md) reduce source/header builds to 47.82/28.33/28.01 ms versus same-host full snapshots at 55.90/33.56/33.59 ms. All external checks and exact index bytes remain. All 201 tests and 174 measured libraries pass; warm seed restoration and full clean admission are explicit.


[Batched Odin verification](results/native-conditions/REPORT.md) reduces export from 5.3–5.7 to 4.4–4.6 ms while preserving all reads/hashes and exact wire output. Both native modes pass the differential/invalidation suites; all 181 tests and 219 measured libraries pass. Final row emission adds little compared with native verification alone.


The [retained condition producer](results/retained-conditions/REPORT.md) reduces export from about 9.2 to 5.2 ms while preserving every backing-file check and exact reference wire bytes. Matched source/header builds take 54.69/32–33 ms and beat both Ninja controls in all seven blocks. All 135 tests pass; warm-session retention and a separate shared reader fix are documented.


The first native experiment supports **batching compiler requests in one process** and, on the header-heavy batch, **supplying immutable inputs directly to the compiler's VFS**. This is a synthetic C fixture on one Linux laptop, not a representative project benchmark or a standardized tool protocol.

Run `20261029T163845.341343Z` contains **180 randomized fresh-process observations**, 15 per case, plus correctness warmups, six boundary checks and six separate syscall traces. Clang/LLVM is 22.1.8. Native orchestration is Odin; a C ABI shim adapts Clang's C++ ToolInvocation/EmitObjAction and VFS interfaces. [Report](results/initial/REPORT.md), raw observations (local artifact, `results/initial/results.json`), [toolchain/header provenance](results/initial/toolchain-provenance.json), [reproduction](README.md).

## Matched result

Median full-process wall time, ms:

| Headers per translation unit | Translation units | Ordinary Clang CLI | In-process, physical inputs | In-process, mapped inputs |
| ---: | ---: | ---: | ---: | ---: |
| 32 | 1 | 53.150 | 47.359 | 47.013 |
| 32 | 8 | 400.779 | 133.275 | 121.574 |
| 512 | 1 | 141.173 | 137.784 | 131.827 |
| 512 | 8 | 1184.909 | 880.484 | 805.435 |

With eight translation units, physical in-process compilation wins **15/15 blocks** versus CLI at both sizes. The small-header batch improves about **67%** without changing the input layout; the large-header batch improves about **26%**. These are complete-process improvements with all compiler-state disposal included.

Mapped inputs add about **9%** improvement over physical in-process inputs by batch medians. The header-heavy batch has the clearest incremental evidence: **72.536 ms paired median savings, 15/15 wins**. The small-header batch saves 11.372 ms paired with 11/15 wins. Combined mapped/batched gains versus CLI are about **70% / 32%**, both 15/15 wins. One-unit differences are smaller and less consistent; the large-header physical case wins only 8/15 blocks. Do not extrapolate the batch ratios to every compiler invocation.

The CLI baseline is a normal single command accepting all eight source files, not an artificial one-wrapper-per-file comparison. Separate traces show the installed Clang driver starts eight cc1 processes for that command: **nine execs total**, versus **one** for each native host. The in-process path still constructs/parses arguments and creates fresh compiler/FileManager/action state for every unit. It shares process/library/target initialization, not AST or completed compilation state. The traces identify removed frontend execs but do not partition every internal initialization cost.

## Bulk input evidence

For the eight-unit, 512-header case, both CLI and physical in-process modes open **4,104 loose inputs**, perform **4,096 preads**, and map the eight larger source files. The mapped mode has **zero loose-input path syscalls** in the separate trace; it opens/maps its collection once. Runtime-library and output-file activity remain. Counts include warm-cache kernel work, not physical disk reads.

The collection is 230,526 bytes for 512 headers/eight source files, versus 14,622 bytes for the small fixture. Every native memory consumer hashes the full collection, checks count/ranges/flat names, and builds LLVM VFS metadata before compilation. Combined mapping/native setup is about **1.74 ms** for the large batch. Compiler payload buffers borrow the immutable mapped bytes; they are not copied once per header, but VFS metadata still allocates and does path lookup. This is not a flat native file-ID protocol or bounded metadata arena. Single-unit consumers mount all eight available source records too.

## Correctness and lifecycle

All **810 timed object outputs** match CLI byte for byte. Every mode/case warmup is additionally linked and executed against independent expected values. Inputs, flags, target, optimization and object generation are held fixed; outputs are ordinary object files. Source fixture generation and linking/validation are outside consumer timing.

Six boundary checks cover wrong pin, rehashed truncation, unsafe name, missing virtual header despite a physical copy, invalid C with error diagnostics, and compiling while the loose input directory is temporarily unavailable. The in-memory VFS has no host fallback. Odin owns the mapping until compiler and VFS objects are destroyed. The reusable path frees each request; it does not adopt one-shot Clang's optional DisableFree behavior. No worker fast exit, PCH, cache, shared AST or incremental optimization is used.

Fixture production costs **13 / 76 ms**, and adapter compilation costs **13.47 s**, outside measured process times. Matching LLVM development headers were downloaded/verified/extracted only under the ignored workspace; installed packages were unchanged. Build commands, toolchain/binary/source hashes, source snapshots, fixture hashes, individual observations and boundary diagnostics are retained. Trace classification separates `inputs/` from the sibling `inputs.gci`; raw traces remain local `_work` artifacts.

The fixture has generated flat C headers/functions, no system headers, no C++ templates/modules, no timestamps/debug metadata and no real-project dependency discovery. Virtual file timestamps are zero. Native target registration is narrower than CLI's general initialization. Every request disposes its own compiler state, while CLI may leave some reclamation to process termination. These differences and synthetic inputs limit generalization; complete process time still includes the costs of the reusable path.

## Follow-up

The evidence justifies testing a representative project before designing a protocol or expanding the microbenchmark. Original follow-up questions (CC-01 now has the zlib result below):

| ID | Question | Completion criterion |
| --- | --- | --- |
| CC-01 | Measured on zlib below; extend to larger/different real projects. | Same compiler/configuration and outputs through CLI/physical/mapped controls, normal and failure paths, full build plus producer costs; include realistic headers/generated inputs. |
| CC-02 | Is repeated invocation parsing/setup material? | Profile it separately, then compare a normalized invocation template with identical outputs and isolated per-request mutable state. No saved AST advantage hidden in the control. |
| CC-03 | What should the input interface expose? | Measure VFS metadata construction/lookups, dependency observation and source/diagnostic names before proposing an indexed/batched contract; preserve filesystem export for compatibility. |
| CC-04 | Can a long-lived service recover and remain bounded? | Repeated success/error/cancellation with memory/lifetime checks, explicit configuration/toolchain invalidation and structured diagnostics. Current batch aborts on first failure and has no daemon/transport. |

No stable compiler invocation, dependency distribution or common object-store protocol is chosen by this run.

## Real project: zlib

**A real project preserves the serial in-process gain; ordinary parallel make still wins wall time.** Run `20261029T165946.317034Z` builds the entire zlib 1.3.2 static library: 15 translation units, configured release/PIC flags, real generated/project headers and the observed system-header closure. [Report](results/zlib/REPORT.md), raw observations (local artifact, `results/zlib/results.json`), [upstream test summaries](results/zlib/upstream-tests.json), [reproduction](README.md#real-project-zlib).

The source archive is pinned to the SHA-256 published on [zlib's official site](https://zlib.net/): `bb329a0a2cd0274d05519d61c667c062e06990d72e125ee2dfa8de64f0119d16`. It was verified before extraction from the [upstream archive](https://zlib.net/fossils/zlib-1.3.2.tar.gz). Upstream source was not edited; configure generates its normal configuration. The Python driver discovers actual library compile commands from `make -n libz.a`. It retains configured feature flags, makes normal compiler header search explicit, and applies the same target/search/compiler flags to every control. The native request-vector and absolute-input adapters contain no zlib-specific logic.

### Complete library result

**75 timed library builds**, 15 randomized blocks across five modes. Medians include compiler startup, all object generation/writes, normal request/process disposal and static archive creation. Make controls force all library outputs to rebuild; cleanup occurs before timing. No PCH, saved AST, compiler/result cache or incremental reuse is involved. Filesystem caches are warm.

| Mode | Library wall ms | Total child CPU ms |
| --- | ---: | ---: |
| Upstream make, one job | 2233.466 | 2212.113 |
| Upstream make, eight jobs | 560.194 | 2944.920 |
| One ordinary Clang batch command | 2201.293 | 2183.581 |
| Sequential in-process, physical inputs | 1651.582 | 1637.826 |
| Sequential in-process, mapped inputs | 1620.408 | 1618.140 |

Physical in-process compilation improves **25.0%** against the CLI batch median, winning **15/15 blocks** with **544.431 ms paired median savings**. Mapped input improves **26.4%** against CLI, also 15/15 wins. Merely batching source arguments into one CLI command has little advantage over serial make on this build: it wins only 8/15 blocks versus make.

Mapped input adds a smaller **1.9%** improvement over physical in-process medians. Paired savings are **46.939 ms**, winning **12/15 blocks**; memory/physical ranges overlap (1,570–1,686 / 1,608–1,715 ms). This is evidence of a modest additional benefit, not the roughly 9% gain seen in the generated header-heavy batch. Actual compilation dominates much of this project.

Eight-job upstream make is **2.89x faster in elapsed time** than the sequential mapped host, winning all 15 blocks against it. Conversely, the mapped host consumes about **45% less aggregate child CPU**. Parallelism changes the comparison: this prototype demonstrates lower serial work, not a replacement for a parallel build system. Child CPU includes descendants via rusage; it is not divided by job count.

### Input delivery and validation

The mapped collection contains **126 named files: 26 project inputs and 100 system headers**, totaling **1,552,479 bytes** including metadata/terminators. Every memory launch hashes and validates it; combined mapping/native setup is about **4.55 ms**. Header dependency discovery/admission costs **1.78 s**, and adapter build costs **14.33 s**, outside consumer timing. Acquisition/configuration/admission must not be hidden in a one-use producer/consumer claim. The observed header set is compiler/target/configuration-specific, not a general complete SDK model.

Separate traces confirm both CLI and in-process physical builds open **75 project inputs plus 1,256 system headers** across their translation units. The mapped build opens/maps its collection once and performs **zero loose admitted project/system-header calls**. Its trusted invocation plan is mapped separately; runtime libraries and output/archive activity still use the filesystem. CLI compilation executes **16 processes, including 15 cc1 execs**; each in-process compiler executes once. Traces cover compilation, not archive creation, and are not timed samples or physical-disk-read counts.

All **1,125 timed object files and 75 final static archives** match the CLI reference byte for byte. Each of the five mode warmups additionally passes upstream `make check`, including normal and 64-bit example/gzip tests. Retained logs show the tested library units were not recompiled during validation, and hashes remain unchanged. Linking/test execution is outside the reported library-build clock.

Seven boundary checks cover wrong pin, rehashed truncated input, unsafe absolute name, truncated invocation plan, missing project header, missing system header, and compiling all 15 units with the physical project tree unavailable. Missing admitted headers fail despite physical copies being present: memory mode has no host input fallback. Native compiler/FileManager state is disposed per request; mappings outlive all borrowing VFS buffers. The original synthetic bridge/interfaces remain unchanged; the absolute-input experiment uses a distinct `GAIACIN2` version and bounded `GAIACRQ1` request vectors.

Full source/native/toolchain/input hashes, exact measured source snapshots, configured arguments, generated config, dependency lists, all samples and boundary diagnostics are retained. The [upstream test logs](results/zlib/upstream-tests.json) are reviewable without the ignored local build tree. Source and system-header payloads, builds and raw traces remain local; regenerate from pinned sources/toolchain when unavailable.

### Research disposition

CC-01 now has a complete small real C library result. It does not validate large C++, modules/PCH, arbitrary generated inputs, optional-header probing, timestamp macros or multi-configuration SDKs. General absolute naming and per-request arguments were added to the adapter; these are experimental local fixtures, not a portable protocol.

The next useful generic step is **CC-05: bounded concurrent programmatic compilation**. Compare against the same eight-job upstream build and keep exact artifacts/upstream tests. Measure aggregate CPU, wall time and peak memory; establish frontend/global-state thread safety or isolated worker lifetimes before choosing a concurrency mechanism. Share only admitted immutable inputs and explicit compiler configuration; do not introduce hidden incremental AST reuse into this comparison. CC-02 through CC-04 remain queued for invocation setup, input semantics and service recovery. No framework/project-specific code-generation optimization was needed or tested.

## Bounded compiler queue and embedded linker

**The proposed queue works and produces a modest real-project win over parallel make.** Run `20261029T201012.673471Z` contains **120 randomized builds**, 15 blocks across eight configurations, using the same admitted zlib sources/configuration/system headers. It extends the output to a shared ELF library so the final stage exercises a real linker rather than an archiver. [Report](results/pool-link/REPORT.md), raw observations (local artifact, `results/pool-link/results.json`), [shared-library test logs](results/pool-link/upstream-tests.json), [reproduction/design](README.md#bounded-compiler-queue-and-embedded-linker).

An Odin host owns 1/2/4/8 worker threads draining a bounded admitted job table. At most 64 jobs and 16 workers are accepted by this prototype; eight is the largest measured worker set. Each worker owns mutable VFS metadata/current-directory state; each job owns its compiler instance, LLVM context and diagnostic consumer. Only authenticated immutable source bytes and argument vectors share. Workers dispose their request state normally. After every worker joins, one embedded LLD call consumes the declared object list in deterministic order. Linking does not depend on completion order and never overlaps compiler work in this experiment.

### Complete shared-library results

Medians, including compilation, linking, startup and normal teardown:

| Control | Wall ms | Aggregate child CPU ms | Native host peak RSS MiB |
| --- | ---: | ---: | ---: |
| make, one job, external LLD | 2310.416 | 2293.338 | — |
| make, eight jobs, external LLD | 531.190 | 2947.525 | — |
| Mapped pool, one worker, embedded LLD | 1656.225 | 1654.834 | 118.15 |
| Mapped pool, two workers, embedded LLD | 923.305 | 1764.167 | 121.83 |
| Mapped pool, four workers, embedded LLD | 574.449 | 1995.254 | 126.34 |
| Mapped pool, eight workers, embedded LLD | 498.292 | 2359.422 | 131.91 |
| Mapped pool, eight workers, external LLD | 515.349 | 2315.718 | 131.96 |
| Physical-input pool, eight workers, embedded LLD | 483.890 | 2338.845 | 134.02 |

The physical-input pool is **8.9% faster** than eight-job make by wall medians and uses **20.7% less aggregate child CPU**. It wins **15/15 blocks**, with **37.136 ms paired median savings**. The mapped pool improves wall medians **6.2%** and CPU **20.0%** versus make, with **10/15 block wins** and 31.566 ms paired savings. Its range overlaps make's broadly (455–611 / 498–626 ms). This is a small-project result, not a general build-system speedup.

Mapping does not add a win inside this parallel pool: mapped eight-worker builds are 13.749 ms slower by paired median than physical input, winning only 6/15 blocks. Admission hashing and private per-worker VFS construction remain real costs. Warm physical header access also overlaps parallel compilation. The queue/embedding result should not be attributed to the input format.

Embedded LLD takes **4.13 ms** in the mapped eight-worker case, versus **25.51 ms** for its external-link process. The external control uses the same compiler-pool binary, already linked with LLD, but invokes the linker separately. Whole-build medians are 498.292 / 515.349 ms, a smaller 3.3% difference with 10/15 block wins; paired savings are 28.034 ms. Link-call and process clocks have different boundaries intentionally, and compiler scheduling variation remains. Removing the link subprocess helps its stage but does not remove frontend work.

All native samples reach their configured peak of exactly 1/2/4/8 active jobs and never exceed it. The one-worker mode minimizes aggregate CPU, while eight minimizes wall time among the mapped variants. Per-job intervals show this 15-unit fixture spends about 35% of its eight-worker job-span with only one or two active jobs; that is logical job occupancy, not CPU utilization. Queue-tail imbalance limits scaling. Peak native process RSS rises from about 118 to 132 MiB over the mapped worker sweep. Make aggregate peak memory is not measured; summing/copying cumulative child RSS would not be a valid comparison. Worker bounds do not constitute compiler byte limits.

### Correctness, failure handling and scope

All **1,800 timed object files and 120 shared libraries** match the make/Clang/LLD reference byte for byte. The 15 object identities also match the earlier CLI objects independently. Each of eight mode warmups passes upstream normal and 64-bit checks against the shared library itself, with no library-unit recompilation or artifact changes during validation. Source/input/host pins and exact measured source snapshots are retained. Adapter compilation costs **16.06 seconds**, outside consumer clocks; existing admission is reused and its earlier producer cost is not repeated inside a build.

The failure checks verify ordinary LLD diagnostic failure followed by successful linking in the same process, compilation with the physical project tree unavailable, and compile errors preserving a prior published artifact while making **zero link calls**. Job-local diagnostic callbacks update Clang's own diagnostic state as well as structured counters; the link gate independently requires every job to succeed with no errors. A compile failure stops further observed dispatch, drains already claimed/in-flight work, joins workers and returns diagnostics. The linker is a single serialized stage. `canRunAgain` is honored; unrecoverable LLD state retires the process rather than reusing it.

This tests a finite per-target batch, not an always-running daemon. Workers are reused across translation units within that batch; all workers are joined before linking. Arbitrary Clang options/plugins and compiler crashes are not proven safe to isolate inside threads. A compiler crash may terminate the shared host. General multi-build service recovery/isolation remains CC-04.

Object payloads **still pass through ordinary object files** before embedded LLD reads them. The result proves queued compiler orchestration plus process-local linking; it does not prove a zero-copy compiler-to-linker object interface or eliminate all POSIX access. The linked output, target and timing boundary differ from the earlier static-library experiment, so only controls within this new run establish its speedups. Linker internal parallelism is fixed to one to isolate invocation costs and avoid nested CPU budgeting.

### Design consequence and follow-up

The useful interface is a bounded compile queue producing object handles plus an ordered link request gated on its dependencies. On this adapter, linking must be serialized and all compiler workers are quiescent first. A future build DAG should use per-target readiness, explicit capability/resource budgets and cancellation/publication rules rather than forcing every target behind a global compile barrier.

CC-05 is now measured on this small real project. Remaining focused tasks are **CC-06: direct object-buffer handoff/linker input adaptation**, **CC-07: a larger multi-target project and job/resource scheduling**, and **CC-04: repeated-build/crash isolation and service recovery**. CC-02/CC-03 still cover invocation setup and input semantics. Direct memory handoff or a persistent service should have its own matched file/process controls; neither is assumed to improve latency. No storage or invocation wire protocol is standardized here.

## Direct object-buffer handoff

**Direct handoff removes object-file I/O, but does not increase the parallel-build speedup on this project.** Run `20261029T203940.351942Z` measures 120 complete builds in 15 randomized blocks across eight configurations. Native controls use one identical executable, compiler flags and artifact order. [Report](results/direct-handoff/REPORT.md), raw observations (local artifact, `results/direct-handoff/results.json`), [upstream tests](results/direct-handoff/upstream-tests.json), [syscall evidence](results/direct-handoff/object-io-traces.json), [reproduction and adapter limits](README.md#direct-object-buffer-handoff).

| Configuration | Complete build median ms | Aggregate child CPU ms |
| --- | ---: | ---: |
| make, eight jobs, external LLD | 538.527 | 2994.770 |
| Physical inputs, eight workers, file handoff | 497.958 | 2322.436 |
| Physical inputs, eight workers, buffer then file | 499.913 | 2345.152 |
| Physical inputs, eight workers, direct buffers | 497.411 | 2317.349 |
| Physical inputs, one worker, file handoff | 1709.552 | 1705.583 |
| Physical inputs, one worker, direct buffers | 1684.398 | 1680.662 |
| Mapped inputs, eight workers, file handoff | 480.457 | 2246.984 |
| Mapped inputs, eight workers, direct buffers | 490.461 | 2260.679 |

Eight-worker direct and file handoff are essentially level by separate medians. Direct wins only **6/15 paired blocks**, with a **5.673 ms paired median regression**. Direct versus buffer-then-file is also level: 7/15 wins, +0.229 ms paired median. Against make, direct improves wall medians **7.6%**, uses **22.6% less CPU**, and wins 13/15 blocks with 43.058 ms paired savings. The file pool already captures this benefit; this experiment does not support attributing an additional parallel speedup to direct handoff. Wide overlapping ranges matter more than the half-millisecond difference of medians.

The serial control shows a modest gain: direct improves wall medians **1.5%**, wins 12/15 blocks and saves 20.963 ms by paired median. It does not include a one-worker buffer-then-file control, so the result cannot isolate stream emission from avoiding file I/O. Mapped parallel direct wins only 8/15 blocks over mapped file handoff; its separate median is slower despite a negative paired median. Neither comparison establishes a dependable parallel benefit.

### What was removed and what remains

Clang emits **132,224 bytes (129.1 KiB)** across the 15 objects. These remain native ELF payloads, not Python objects. Each direct link records exactly 15 buffer hits, zero missing-object lookups and the matching byte total. No object file exists during timed direct builds. An untimed trace confirms **zero generated-object filesystem calls**, including temporary object outputs. In contrast, ordinary file handoff records 30 opens, 70 writes, 15 renames, 13 preads and two mmaps across object output/input, plus metadata/close calls. Buffer-then-file also records 30 opens but 24 writes. Unrelated `crtbegin.o` discovery still makes 105 metadata probes; source/toolchain/runtime access and shared-library output remain filesystem based. These are syscall counts, not physical disk-read measurements.

Physical eight-worker LLD call medians are **4.134 ms file / 3.903 ms direct**; mapped counterparts are 4.249 / 4.502 ms. Even the entire current linker call is less than 1% of a build. Buffer-then-file writes consume 4.219 ms summed across jobs, with overlap; removing that sum is not an equivalent wall-time saving. The compiler phase takes about **454–457 ms** on physical eight-worker controls. Eliminating 129 KiB of warm-cache traffic cannot account for most of that work. ELF emission/parsing, compilation and queue-tail imbalance remain.

The gap between complete process time and the native workload clock is about **35–38 ms** by paired residual medians in physical eight-worker file/direct modes. It includes startup, validation/output reporting after the clock and normal teardown; this is not a separately measured startup phase or a promise that a persistent service recovers all of it. A persistent-session experiment and compiler phase profiling are better candidates for the next latency investigation than further tuning this small handoff map. A larger multi-target/object-volume fixture is still needed to evaluate scaling or storage-pressure benefits.

### Correctness and integration limits

All **1,800 timed object identities and 120 shared libraries** match the prior CLI/file reference byte for byte. All eight configurations pass upstream normal and 64-bit shared-library checks without replacing the tested library. Direct warmups export captured objects only after linking for those checks; timed direct runs do not export. Separate checks verify link failure followed by successful same-process reuse, compile failure making zero link calls and preserving an existing output, a mapped build with its physical project tree hidden, and a missing captured object failing despite a stale physical file. These checks cover ordinary diagnostics, not compiler-crash recovery.

The adapter uses a Clang output stream plus a narrowly scoped LLVM factory interposition at LLD's read boundary. It preserves LLD input ownership and normal context destruction; native buffers outlive every borrowed wrapper. It is a Linux/LLVM 22.1.8 research adapter, not a stable supported LLD buffer-provider API. Native worker concurrency is bounded; buffer memory is not bounded in bytes. The [implementation notes](README.md#direct-object-buffer-handoff) record path/factory restrictions. Normal pool builds keep their original file path through conditional compilation. Exact measured sources, host/toolchain/input pins and build commands are retained; adapter compilation took 20.10 seconds outside consumer measurements.

CC-06 is now measured on this small fixture. Its result supports an object-handle boundary for avoiding materialization, with **no demonstrated added parallel latency win here**. CC-04 session lifetime/recovery, CC-02 compiler invocation setup/phase costs and CC-07 larger target scheduling remain follow-ups. No compiler optimization flags, AST/result caches or early process exit were used to manufacture a gain.

## Larger project, process lifetime and compiler phases

**A larger real library still shows no consistent additional handoff win; process reuse does.** Two separate matched experiments test these questions without running CPU-heavy work alongside timing. Zstandard run `20261029T205610.494160Z` contains **42 timed builds**, seven randomized blocks across release/debug × CLI/file/direct. Zlib lifecycle run `20261029T210117.876902Z` contains **112 complete timed builds**, seven randomized blocks comparing four fresh processes with four independent builds inside one process. [Zstandard report](results/zstd-handoff/REPORT.md), [lifecycle report](results/compiler-lifecycle/REPORT.md), [Zstandard phase profiles](results/zstd-handoff/PHASES.md).

### Zstandard: more work and larger objects

The Zstandard 1.5.7 dynamic-library target has **30 C translation units**, twice zlib's count. Its upstream portable-C configuration uses `ZSTD_NO_ASM=1` and disables legacy compatibility; normal `-O3` flags remain. Debug adds `-g` with a common explicit compilation directory so control output directories do not alter debug bytes. All modes share exact flags, declared object order and single-threaded LLD. The CLI control uses an admitted makefile with those same compile/link commands, rather than measuring upstream configuration work. This is a larger library target, not a large multi-target C++ repository.

| Configuration | CLI + external LLD ms | Native file ms | Native direct ms | Object volume |
| --- | ---: | ---: | ---: | ---: |
| Release | 5065.24 | 4960.26 | 4919.88 | 0.874 MiB |
| Debug | 6906.12 | 6620.02 | 6738.58 | 3.738 MiB |

Object volume is about **7× / 30× zlib** for release/debug. Direct wins only **4/7 blocks** against file handoff in each configuration, with paired median deltas of −4.18 / −22.35 ms. Separate whole-build medians show release slightly faster and debug slower; neither is a dependable added win. Native LLD call medians remain almost equal: **6.24 / 6.26 ms** release file/direct and **14.72 / 15.01 ms** debug. Most build time is elsewhere. Direct debug retains about **15 MiB more peak RSS** than native file handoff (333.95 versus 318.79 MiB); worker bounds do not imply a byte budget. Direct hashing remains inside the complete-process clock and outside the native workload clock, as in the earlier experiment.

All **1,260 timed object identities and 42 shared libraries** match their CLI references. Every direct result records 30 hits, zero missing objects and no object files. Six warmups each pass six byte-exact compression/decompression round trips through upstream simple/streaming examples on empty, small and 1 MiB inputs. Dynamic-loader resolution verifies the actual measured library. These are focused public-API checks, not the complete upstream fuzzer suite. Source/toolchain/host pins, upstream command plan, exact commands, validation logs and [compiled-host provenance](results/zstd-handoff/native-host-provenance.json) are retained. The initial debug mismatch was fixed before timing by normalizing compilation-directory metadata; compiler optimization flags were unchanged between controls.

This does not rule out a benefit for hundreds of MiB of objects, much larger TU counts, cold storage or storage contention. It establishes that a heavier compilation workload and 30× more object data do not automatically make this boundary dominate. Seven blocks with scheduling variance are sufficient to reject a claim of a clear win here, not to establish equivalence within a tiny margin.

### Process lifetime: a measurable additional gain

The separate zlib driver performs four complete builds per observation. Fresh mode starts four processes; repeat mode starts once and recreates/disposes each pool, worker set, compiler instances/LLVM contexts, object buffers and linker context for every build. Loaded libraries, process-global initialization and allocator state persist. There is no AST/object-result cache and no skipped compilation. Both controls use the same executable and output policy.

| Handoff | Fresh process ms/build | Four-build process ms/build | Paired savings ms/build | Wins |
| --- | ---: | ---: | ---: | ---: |
| File | 506.816 | 472.111 | 35.759 | 7/7 |
| Direct | 502.826 | 466.460 | 36.366 | 6/7 |

Four-build batching improves wall medians **6.8% / 7.2%** for file/direct. It amortizes one launch/exit over four builds; it is not a zero-startup steady-state measurement. File versus direct inside repeat mode has **no consistent added handoff benefit**: direct wins 3/7 paired blocks, with a 4.89 ms paired median regression. Do not compare these absolute times with CLI from another run to claim a combined speedup.

Observed launch-to-main medians are about **23–25 ms per process**, with **10–13 ms after main**. These include creation/runtime initialization, scheduling, reporting, teardown and parent observation, not exclusively loader/destructor CPU. Amortizing those boundaries explains much of the gain; native workload/allocator warming also changes, so the entire saving cannot be attributed to loading shared libraries. Pool disposal itself is roughly 10 µs for file mode and 2–3 ms for direct mode in this fixture. The Linux parent/child monotonic clocks are checked for consistent ordering. Per-build process time excludes the parent's artifact checks between fresh launches; group wall time including those checks is retained separately.

Every iteration reports 15 successful compilations and one successful link. All captured object identities match, and every process's externally inspectable file objects/shared library match. Only the last file-backed iteration in a repeated process is externally inspectable; intermediate shared-library bytes are not independently hashed. Ordinary error/reuse tests from the original handoff experiment remain applicable, but this experiment does not exercise cancellation, compiler crashes, hostile inputs or long-running memory growth. **A bounded multi-build batch is validated; a persistent crash-isolated service remains open.**

### Compiler phases: the bulk is real compiler work

Separate LLVM time-trace builds preserve all object/library identities. The one-worker zlib trace spends about **79% of summed job spans in the backend**, with about 18% in the frontend. Eight-worker Zstandard traces place **86–88% in the backend** and **10–13% in the frontend**. Backend includes optimization and machine-code generation; its nested subphases must not be added to it.

| Instrumented workload | Sum job spans ms | Frontend ms | Backend ms | Optimizer ms | CodeGenPasses ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| zlib, one worker | 1777.63 | 328.43 | 1397.94 | 779.59 | 596.99 |
| Zstandard release, eight workers | 22082.05 | 2763.05 | 19098.08 | 11667.29 | 7372.93 |
| Zstandard debug, eight workers | 30756.80 | 3195.59 | 27029.88 | 14237.17 | 12728.47 |

These are summed event wall durations, **not CPU samples**. Parallel spans overlap and include descheduling; instrumentation adds overhead. No profile run contributes to latency tables. Full traces and event/job breakdowns are retained. The larger fixture also exposes a scheduling target: `zstd_lazy.c` starts about 0.28–0.35 seconds into the trace and spans about 4.79 / 6.51 seconds, dominating the tail. Starting predicted expensive jobs earlier is a generic queue experiment worth testing; this profile does not prove its eventual speedup.

The immediate useful direction is **process/session reuse plus compiler-aware scheduling and phase profiling**, while retaining direct object handles as an optional materialization boundary. More container or handoff-map tuning has little demonstrated latency headroom on these warm-cache C libraries. CC-02 now has phase/lifecycle attribution; CC-04 has finite repeated-build evidence but still needs recovery and resource limits; CC-07 has a larger single-target fixture, with multi-target scheduling still open. No platform-wide protocol or arbitrary-toolchain safety guarantee follows from these adapters.

## Cost-aware compiler dispatch

**Starting predicted expensive jobs first yields a modest whole-build win on this fixture.** Run `20261029T232949.779224Z` contains **56 complete timed Zstandard builds**, seven randomized blocks across release/debug × file/direct handoff × FIFO/cost priority. Both policies use the same executable, eight workers, identical compile requests and unchanged ordered linker inputs. [Report](results/cost-scheduling/REPORT.md), raw observations (local artifact, `results/cost-scheduling/results.json`), [implementation and reproduction](README.md#cost-aware-compiler-dispatch).

Dispatch priority is implemented in Odin, separately from immutable job/result indices. Predictions are frozen medians of each job's elapsed span from the previous seven unprofiled file-handoff builds for that configuration. No test observation updates the estimates. Both FIFO and cost controls map/validate the same hint table before dispatch. The hints describe historical elapsed spans under parallel load, not intrinsic CPU cost; stale or inaccurate estimates can hurt performance. Every job is still compiled from scratch, with normal disposal.

| Configuration | FIFO ms | Expensive-first ms | Median wall improvement | Paired median savings ms | Wins |
| --- | ---: | ---: | ---: | ---: | ---: |
| Release, file handoff | 4680.26 | 4511.06 | 3.6% | 164.94 | 5/7 |
| Release, direct handoff | 4688.96 | 4442.99 | 5.2% | 190.25 | 6/7 |
| Debug, file handoff | 6323.69 | 6180.76 | 2.3% | 165.37 | 6/7 |
| Debug, direct handoff | 6347.38 | 6172.07 | 2.8% | 220.84 | 6/7 |

The predicted-longest job, `zstd_lazy.c`, starts about **256–335 ms** after the first job in FIFO medians and at the beginning of the priority queue. The resulting paired savings are smaller and depend on contention. Aggregate child CPU medians increase **1.6–2.9%** across the four comparisons. Debug file-handoff peak RSS rises from about **320 to 332 MiB**; other memory comparisons vary. This policy trades a little more measured CPU, and sometimes memory, for lower elapsed time. It does not reduce compiler pass work or establish a universal speedup.

The final interval with only one outstanding job actually grows: roughly **1.85–1.89 → 2.05–2.08 seconds** for release and **2.56–2.57 → 2.82–2.86 seconds** for debug. Other jobs finish earlier too, so minimizing this interval alone would misjudge the outcome. Whole-build completion is decisive. Job spans measure logical occupancy and include descheduling; they are not CPU-utilization samples. Seven blocks and one library target support this directional result, not a precise general performance guarantee. Absolute timings from the earlier process-reuse/CLI runs are separate comparisons and must not be combined into a synthetic end-to-end speedup.

All **1,680 timed object identities and 56 shared libraries** match the prior CLI references byte for byte. Direct builds each consume 30 borrowed buffers, report zero misses and create no object files. All eight mode warmups pass six byte-exact round trips through upstream simple/streaming examples, with loader resolution checked. The native reported schedule matches the independently computed stable permutation; all jobs complete and worker concurrency stays at eight. All-zero costs preserve FIFO, and malformed header/count/value records fail before dispatch while preserving the existing library. A separate [sorted-queue compile-error check](results/cost-scheduling/compile-error-check.json) confirms that failure in the highest-priority job suppresses linking and preserves a published output. These checks extend ordinary error behavior, not compiler-crash isolation.

Review also found a small input-boundary issue: the reused mapping helper required 16 bytes even though a valid one-job, zero-cost table is 12 bytes. The corrected driver keeps the 16-byte minimum for compiler plans/bundles and uses a 10-byte header minimum for costs. Six [small-queue checks](results/cost-scheduling/small-queue-checks.json) cover one job, equal costs and reordered priorities with file/direct handoff, verify CLI object/library identities, and execute every exported test function. The timed binary and its exact source snapshot are retained unchanged; this admission-only correction was built/tested separately after timing and does not affect the 30-job cost tables used in the experiment. Both binary identities/build records are retained.

The useful design is **optional historical scheduling hints**, associated with the exact source/toolchain/configuration and falling back to FIFO when unknown. History collection/estimation is outside the consumer clock here because existing observations were reused; the first build has no history and receives no predicted benefit. The experimental text table is trusted local configuration, not a standardized protocol or a source-identity contract. Sorting is bounded to the prototype's 64 jobs; worker limits do not cap memory bytes. Larger ready sets and build DAGs need an appropriate priority structure and resource budgets.

This completes the first cost-aware portion of CC-07. Next useful checks are multi-target readiness/critical paths, resource-aware priority, and whether estimates remain useful across edits and configuration changes. Bounded persistent workers/recovery (CC-04) remain separate work. The evidence supports retaining an opt-in expensive-first policy when compatible history exists; it does not justify an unconditional scheduling default for arbitrary workloads.

## Local compiled-object cache

**Object reuse provides a large consumer-time gain for unchanged inputs and light source edits; conservative shared-input keys still rebuild the entire batch.** Run `20261029T235526.613463Z` measures **90 complete builds**: five randomized blocks across six scenarios × off/whole/scoped cache policies. The target is the 30-unit Zstandard portable-C release library plus one small observable invalidation probe. [Report](results/object-cache/REPORT.md), raw observations (local artifact, `results/object-cache/results.json`), [boundary checks](results/object-cache/checks.json), [upstream checks](results/object-cache/upstream-checks.json), [reproduction](README.md#local-compiled-object-cache).

| Scenario | Full uncached batch ms | Whole-collection cache ms | Per-request view cache ms | View-cache compilers / hits |
| --- | ---: | ---: | ---: | ---: |
| Unchanged | 4650.50 | 54.61 | 53.24 | 0 / 31 |
| Light implementation edit | 4623.51 | 4666.96 | 116.99 | 1 / 30 |
| Heavy implementation edit | 4639.87 | 4663.69 | 3766.59 | 1 / 30 |
| Shared-header edit | 4697.78 | 4624.88 | 4652.73 | 31 / 0 |
| Generated-header edit | 4666.76 | 4638.29 | 4641.82 | 31 / 0 |
| Global compiler-flag edit | 4697.25 | 4612.32 | 4645.23 | 31 / 0 |

Scoped caching reduces medians **98.9% for unchanged inputs, 97.5% for the light edit and 18.8% for the heavy edit**, winning all five paired blocks in each. Paired median savings are 4599.64 / 4514.52 / 836.66 ms. Aggregate child CPU falls **99.7% / 99.4% / 81.4%** respectively. A heavy source change still regenerates its expensive object; skipped siblings save substantially more CPU than elapsed time. The shared/generated-header and flag cases execute all 31 compilers and show no demonstrated cache-based acceleration; their small timing differences are noise, with cache bookkeeping/publication still real work.

These comparisons use the existing native engine's **full uncached batch** as the baseline. They do not establish an advantage over incremental make/ninja/ccache. Each observation starts from the same baseline-only cache; edited outputs from an earlier trial are removed before the next consumer. There is no accidental all-hit edited build, AST reuse or link-result cache. Every build performs a real LLD link and normal process exit. This isolates object-cache integration into the native engine.

### Keys, namespaces and validity

The cache and its policy are Odin-owned. A narrow C++ extension installs caller-declared per-request VFS views and transfers native object bytes into/out of the existing object pool. All three controls compile against exactly the same views: admitted project/SDK headers are shared, primary source roots are scoped to their job, and declared cross-root includes are also visible. There is **no host-input fallback**. These are explicit compiler namespaces, not an assertion that positive dependency lists capture every possible host SDK lookup.

Each key includes exact framed arguments, logical working directory, an admitted toolchain/execution-context identity and the complete visible namespace's names, lengths and content hashes. Whole mode additionally binds the full collection, conservatively invalidating unrelated requests after any source edit. Scoped mode combines per-file Merkle leaves into each view root, so an implementation edit changes one key. The same design works for an explicitly declared cross-source dependency; it is not based on guessing source extensions. Presence/absence matters as well as payload: adding the optional probe header invalidates all visible views and changes the executed probe value. An admitted file with visibility mask zero leaves scoped keys unchanged, and a physical header outside the supplied namespace affects neither hits nor uncached compilation.

The fixture normalizes target/include search and compiler environment and rejects volatile date/time macros. The child receives an immutable execution-context receipt rather than rehashing installed compiler DSOs every launch. The measured receipt derives from the pinned prior run; installed bytes were verified again after timing, and current reproduction code verifies them before preparation. Arbitrary compiler plugins, response files, PGO side inputs, nondeterministic extensions, automatic complete-SDK discovery and authenticated remote caches remain outside the contract. Logical names/cwd are part of identity, so cross-workspace path portability is not established.

Records bind a key to a size-bounded object payload plus SHA-256. Hits validate framing/key/hash before copying bytes into native LLD inputs. Misses publish with exclusive temporary files and atomic rename after successful linking. Failed builds do not publish entries; write failure leaves the build usable. Records are private local cache data with corruption detection, not proof against a malicious writer. The prototype has no eviction/quota, payload deduplication, fsync durability or global multi-process resource budget.

### Correctness and measured boundaries

All **2,790 timed object identities and 90 shared libraries** match fresh CLI references for their particular edit/configuration. Runtime probes independently check the source/header/flag changes, and every direct link consumes 31 buffers with zero misses and no materialized object files. Separately, **150 byte-exact upstream example round trips** exercise all 18 final native-control libraries and seven CLI references, checking actual loader resolution and unchanged library hashes.

Fourteen post-run groups cover cold population/warm reuse; payload, framing and stored-key corruption with repair; execution-context identity changes; cache-write failure; compile-error preservation of both cache and published library; invisibility of undeclared host files and admitted-but-unexposed files; concurrent publication and all-hit readback; repeated warnings; and volatile macro rejection. The identity-change test changes the admitted ID while keeping the compiler binary fixed; it is a key-invalidation test, not a second-toolchain compatibility measurement.

Review after timing found that diagnostics needed an explicit cache policy. Current code only publishes diagnostic-free results; warning/remark-producing builds compile again so messages remain visible without designing a replay format. Two warning-producing invocations are checked for repeated diagnostics, zero hits and zero stored entries, with artifacts matching CLI. The timed inputs were all warning-free. Their original binary/source snapshot is preserved, and a separately built corrected binary, new context receipt and [diagnostic-fix provenance](results/object-cache/diagnostic-fix-build.json) accompany the post-run tests. Compiler-crash isolation and long-lived memory behavior are not established.

The baseline collection contains **196 files / 3,101,862 encoded bytes**. Consumer clocks include collection authentication, keys/lookup, integrity checking and copying, actual compiler work, linking, entry publication, result hashes, reporting and shutdown. An all-hit scoped consumer spends about **13.91 ms in admission/key/lookup setup** and **5.47 ms in LLD**, with **53.24 ms complete process time** and about **63.5 MiB peak RSS**, versus about 209 MiB for the uncached unchanged batch. The remaining process/lifecycle cost is consistent with the earlier separate reuse experiment; a combined resident-cache speedup has not been measured.

Producer work is separate and material: **45.53 seconds** prepares seven scenarios, including **10.44 seconds** of dependency discovery/collection encoding and **33.68 seconds** of full CLI reference compilation. Baseline cache population takes one full build per policy (4.64 / 4.74 seconds), and each seed contains 31 records totaling 920,160 bytes. Native adapter compilation is outside consumer time too. Thus 53/117 ms are **admitted-input consumer times**, not end-to-end edit latency including this producer. Incremental snapshot/SDK admission remains important follow-up work.

### Research consequence

The key is selective invalidation, not merely adding a hash table. A complete collection key is useful for unchanged/reverted snapshots but loses reuse on isolated edits. Explicit request-view keys recover that reuse safely within the supplied namespace contract. The shared/generated probe headers are visible to every view but only consumed by the probe; those changes and the global macro flag each alter only one object in the independent CLI outputs, yet the conservative policies rebuild 31. That after-the-fact equality is not itself permission to drop inputs or flags from a key.

The next useful refinement is dependency-aware validation that retains **negative lookup and include-resolution information**, plus incremental production of immutable input snapshots. Positive `.d` dependencies alone cannot account for newly appearing or shadowing headers. A finer policy should retain this conservative path as a correctness baseline. Resident cache consumers, matched comparisons with existing incremental build tools, and bounded/deduplicated artifact storage are additional separate follow-ups. No platform-wide cache or invocation protocol is standardized here.

## Dependency journals and incremental snapshots

**Observed-query validation recovers header-edit reuse, with measurable extra overhead on already-cheap builds.** Run `20261030T003643.076432Z` measures **160 complete producer/consumer pipelines**, five randomized blocks across eight scenarios × four policies. The target remains the 30-unit Zstandard C library plus an observable invalidation probe. Comparisons share exact arguments, hermetic input views and declared linker order. [Report](results/dependency-cache/REPORT.md), raw observations (local artifact, `results/dependency-cache/results.json`), [boundary checks](results/dependency-cache/checks.json), [upstream checks](results/dependency-cache/upstream-checks.json), [reproduction](README.md#dependency-journals-and-incremental-snapshots).

The fixture adds two include-search directories. A late directory initially supplies a probe header; an early directory exists but lacks that name. Separate edits add the earlier shadowing header, make an optional header appear, and create a previously absent directory/header. An unused anchor header gives a real visible-content change with no compiler read. Fresh independent CLI builds and runtime values distinguish the intended outcomes.

The timed audit headers are visible to every request but consumed only by the probe. This tests low-fanout invalidation precision. A header actually read by many translation units must rebuild all those readers; the one-compiler timings below are not a prediction for every shared-header edit.

### Combined preparation and consumption

These medians include snapshot production, receipt handoff, consumer admission, validation, compilation/linking, publication and normal exit of both native processes. Both cache columns below use delta snapshot production; the coarse control binds the entire visible input view. Every cache is restored to its baseline-only seed before each observation.

| Scenario | Uncached full batch ms | Coarse view-cache ms | Journal-cache ms | Journal compilers / hits |
| --- | ---: | ---: | ---: | ---: |
| Unchanged | 4675.24 | 77.19 | 104.36 | 0 / 31 |
| Implementation edit | 4659.25 | 128.90 | 164.07 | 1 / 30 |
| Used shared-header edit | 4648.64 | 4624.07 | 109.96 | 1 / 30 |
| Generated-header edit | 4740.59 | 4678.20 | 115.51 | 1 / 30 |
| Optional header appears | 4652.78 | 4683.11 | 115.11 | 1 / 30 |
| Earlier header shadows fallback | 4660.85 | 4620.33 | 118.57 | 1 / 30 |
| Unused visible header changes | 4694.05 | 4710.51 | 101.88 | 0 / 31 |
| Previously missing directory appears | 4653.75 | 4692.25 | 120.79 | 1 / 30 |

For the six header/namespace scenarios, journal validation wins **5/5 paired blocks** against the coarse cache, saving **4.50–4.60 seconds** by paired median. Complete pipelines fall to roughly **102–121 ms**. Actual consumers take about 81–101 ms; the producer adds approximately 16–21 ms. Negative lookups and include-search order are preserved: optional/shadowing/new-directory edits rebuild the probe rather than returning a stale object. An unused visible-content change remains an all-hit build.

This adds cost when coarse keys already suffice. The unchanged pipeline rises from **77 to 104 ms**, and the implementation edit from **129 to 164 ms**, with regressions in all five paired blocks for each. A warm journal hit checks **6,962 observations**, including **3,462 negative outcomes**, across the 31 actions. Native peak RSS is about 66.1 MiB unchanged versus 63.5 MiB for coarse keys. Baseline journal storage is 1,632,773 bytes across 31 records versus 920,168 bytes for coarse records. Selective validation provides useful coverage, not a free replacement for exact input-view equality.

### What a journal hit means

An action ID includes exact framed argv, logical cwd and the admitted toolchain/provider/execution context. It locates one latest candidate; it does not identify an object by itself. The compiler's VFS adapter records actual observations, and a candidate is imported only if those observations still hold in the new actual view. Status/existence/open failures are retained alongside successful queries. Opened file bytes are content-hashed; the adapter also represents realpath, directory sequence, locality and cwd behavior. The measured C fixture exercises status, existence, open and cwd queries. This is not comprehensive validation of arbitrary Clang options or all adapter operations.

The provider contains independent regular files and implicit directories with fixed metadata. Numeric InMemoryFS IDs differ across instances, so the observation model preserves canonical logical-path identity and alias relations rather than comparing incidental numeric IDs. Symlinks/hardlinks and arbitrary metadata providers require a different contract; this result does not establish their safety. Response/plugin/PGO side inputs and volatile date/time macros retain the earlier restrictions. There is no host-input fallback.

One atomically replaced record binds action ID, journal lengths, journal and object under a checksum. A well-formed but outdated journal is an ordinary miss; malformed or corrupted records are rejected and repaired. Concurrent different-input writers cannot mix a valid journal from one result with another result's bytes. One latest candidate is kept per action; this is not a multi-version action index. Diagnostics bypass publication, and compiler/linker failures preserve previous outputs. Cache records are private local data with corruption detection, not authenticated remote artifacts. Resource quotas, eviction and crash-isolated persistent workers remain open.

### Incremental snapshot preparation

The separate Odin producer applies explicit put/remove events to an authenticated prior collection/view pair. Full refresh instead rereads every named file after applying the same membership changes. Both emit byte-identical canonical collections and masks and still serialize/hash the entire snapshot. The baseline contains **198 files / 3,102,695 encoded bytes**; appearance scenarios have 199 files.

Journal-mode producer medians are roughly **16–21 ms for delta updates versus 23–29 ms for full refresh**. Paired producer savings are **3.0–8.2 ms**, with 4/5 or 5/5 wins depending on scenario. Loose project/SDK reads fall from **198–199 to zero**; base collection, masks and delta are still read. Combined pipeline improvements are smaller/mixed because consumer variation can offset those milliseconds: for example unchanged and shadowing cases do not show a reliable whole-pipeline delta advantage. The dominant acceleration here is selective result reuse, not the snapshot encoding change.

This measures updating an **already admitted namespace/SDK from supplied changes**. The full control also knows the prior namespace and supplied additions/removals; it is not a directory crawl or repeated dependency discovery. Event discovery/creation, initial SDK admission, source-edit application and cache-reset setup are outside timing. Fresh CLI reference compilation costs 45.09 seconds during setup, and initial cache population requires a full build per policy. No filesystem watcher is implemented. New configurations that need additional SDK inputs require readmission; this does not make the earlier discovery cost disappear for arbitrary projects.

### Correctness and follow-up

All **4,960 timed object identities and 160 shared libraries** match their independently rebuilt CLI references, and runtime probes confirm the source/header/search-order changes. Global flags invalidate all actions in a separate check. **246 upstream byte-exact round trips** cover every final native-control library and all nine CLI references, checking real loader resolution and unchanged library hashes.

Seventeen post-run groups inspect the seed's actual negative optional/shadow/directory queries; validate used-header edits and unused-content reuse; check positive shadow disappearance, used-header deletion, corrupt journal/object/opcode repair, concurrent different-input publication, reordered requests with remapped views and fixed link order, repeated diagnostics, invalid producer input rejection before publication, and equivalent removal/zero-byte updates. Reordering requests still yields 31 hits, demonstrating that action identity does not depend on job slots. Invalid base/view/result pins, truncation and unsafe paths leave prior private producer outputs unchanged. Snapshot publication is a successful-receipt handoff, not a crash-durable multi-file transaction.

A separate [real shared-header check](results/dependency-cache/fanout-check.json) edits Zstandard's `common/compiler.h` with an emitted marker. Independent CLI dependency discovery identifies 26 readers, and fresh CLI compilation changes exactly those 26 object files. Journal validation recompiles **26 units and reuses five**, with every object/library matching that fresh reference. This verifies actual high-fanout behavior without implying a one-unit rebuild for widely used headers; it is a correctness check outside the timing tables.

The next useful optimization is an **exact-view fast path followed by journal validation on mismatch**: unchanged views and unaffected source siblings need not pay replay cost, while header/namespace edits retain selective validation. Shared observation batching, metadata/content-ID snapshots that avoid full materialization, and resident consumers are further separate experiments. The current result supports an optional compiler-observation capability and explicit incremental input updates; neither the LLVM-specific journal nor these snapshot/cache encodings are standardized protocols.

## Matched Ninja incremental builds

The [matched comparison](results/ninja-comparison/REPORT.md) uses seven randomized blocks across three engines and nine cases: 189 builds, 5,859 object identities and 189 libraries matching independent CLI references. All runtime probes and expected incremental compile/link counts pass. Ninja 1.13.2 and ccache 4.14.1 use the same Clang/LLVM/LLD 22.1.8 and eight-worker library configuration as the Gaia journal host. The fixed admitted namespace includes a real 26-reader project header.

Gaia narrowly wins plain Ninja's clean-build median (4.745 versus 4.855 s; 6/7 paired blocks) and the global-flag rebuild (4.807 versus 4.971 s; 7/7). High-fanout results are mixed against Ninja. These are small compile-heavy gains, not an overall incremental-build win: Ninja no-op is 5.17 ms versus Gaia's 109.82 ms, and an implementation edit is 125.31 versus 171.15 ms. Ninja also skips linking when unchanged; Gaia always links.

ccache's edit/revert is 43.63 ms versus Gaia's 159.45 ms. On the tested global flag, 30 preprocessing hits and one miss reduce Ninja+ccache to 378.17 ms; the flag affects only the probe, so arbitrary optimization/ABI flags are not covered. Gaia currently binds exact argv and one latest journal candidate per action.

Gaia timing includes stat-scanning the known admitted namespace, changed-file reads/delta encoding, producer publication, receipt validation and the native consumer. Initial SDK admission, Ninja graph generation, editor writes, state restoration and parent validation are outside timing. Source edits must be stat-visible; new directory membership and preserved-timestamp mutations are not tested. Full clocks, ccache statistics, paired comparisons and host context are in the report and [compact summary](results/ninja-comparison/summary.json); [validation](results/ninja-comparison/validation.json) includes the ignored raw-observation checksum. Raw files remain local-only. Reproduction uses [ninja_benchmark.py](ninja_benchmark.py) with explicit tool selection and a fresh native build.

The next priority is an unchanged-request decision path that avoids both LLVM startup and unnecessary linking. Exact-view journal bypass is still useful, but insufficient alone to close the roughly 100 ms no-op gap. Historical result variants are another bounded, tool-independent reuse experiment.


## Lightweight receipts and bounded historical journal candidates

The [follow-up](results/build-decisions/REPORT.md) remeasures Ninja, Ninja + ccache, the single-candidate journal, three-candidate history and history plus a fresh-process receipt gate across six incremental cases and seven randomized blocks. All 210 libraries and 6,510 object identities match CLI references, along with runtime and compile/link checks. Seventeen native/configuration/graph tests pass. [Compile-heavy boundary checks](results/build-decisions/BOUNDARIES.md) add nine libraries and 279 object identities for clean builds, global flags and the real 26-reader header.

The gate reduces unchanged medians from the journal's 186.03 to 7.96 ms, avoiding producer/LLVM launches and linking. Ninja is 8.63 ms, but fast wins only 4/7 paired blocks; the result establishes similar latency rather than a reliable lead. Request/watch-list preparation, fresh-process startup, metadata validation and retained-result loading are timed. The checker links libc and the ELF loader, with no LLVM or C++ runtime dependency. Absolute timings shifted from the earlier run, so compare controls within this run.

Three candidates eliminate the revert compilation: history-only takes 184.42 ms versus journal's 289.12 ms. Fast takes 202.88 ms because its receipt misses and is republished; Ninja + ccache remains faster at 69.28 ms. Every historical candidate still validates action identity, record checksums and actual filesystem observations; each replay resets logical cwd. Eviction and negative header appearance/absence are tested, as is concurrent atomic publication.

The whole admitted namespace remains watched. Unused-header edits therefore still invoke the native pipeline (198.20 ms fast versus Ninja's 8.31 ms), and gate/publication overhead regresses some real edits. Receipts assume stat-visible changes, a fixed admitted namespace and serialized workspace mutation. They do not establish arbitrary directory discovery, preserved-timestamp or watcher correctness. Missing/corrupt receipts and outputs, changed requests and mutations during compilation invalidate or prevent publication. The three-candidate bound is per action, not a global byte quota.

Next investigate a selective observed-condition decision index and bounded reuse of linked results on reverts. Raw observations remain ignored/local-only; versioned [statistics](results/build-decisions/summary.json), [validation](results/build-decisions/validation.json) and test output identify and summarize them.


## Selective observed-condition decisions

The [selective comparison](results/selective-conditions/REPORT.md) runs Ninja, Ninja + ccache, whole-namespace gating and selective gating across six cases and seven randomized blocks. All 168 libraries and 5,208 object identities match CLI references and expected work counts. [Compile-heavy checks](results/selective-conditions/BOUNDARIES.md) add six libraries and 186 objects for clean builds, global flags and the real high-fanout header. All 27 tests pass.

Unused-header edits improve from 197.84 to 12.47 ms (15.9×; 7/7 paired wins), with no producer, LLVM or link. Selective no-op is 10.83 ms versus whole-namespace 6.83 ms and Ninja 8.60 ms. Ninja's unused-header median is 8.19 ms. The conditional boundary works, but this is not a general latency lead.

The current exporter compacts 5,266 selected queries into 275 conditions: 187 positive regular files, 58 missing paths and 30 directory-kind guards. Native results identify the exact selected journals, including historical cache hits; extraction verifies action, journal, record checksum and object identity. Conditions are interpreted against the caller's explicit namespace and per-job masks, not physical host existence. Native tests cover optional-header appearance, include shadowing, invisible physical files, unrelated admission changes, content-preserving touches and positive mutation/removal. Directory listing/cwd-route tests use synthetic provider journals; the timed compiler does not enumerate directories.

Changed builds regress: implementation edits are 376.67 versus 294.56 ms, and shared-header edits 294.14 versus 221.60 ms. Index construction/publication stays inside timing, including full journal parsing, condition reconstruction and positive backing-file verification; the Python export phase costs about 62–65 ms. Native lookup, namespace construction and post-build receipt publication add further costs. Read [compact statistics](results/selective-conditions/summary.json) and [validation](results/selective-conditions/validation.json) for the separate outcomes and raw-data identities.

The next research angle is incremental or batched condition production using per-action fragments and job bitsets, or a native producer working from admitted content identities. Retain the existing producer as a control and preserve negative/membership correctness. A whole-view equality shortcut may avoid selective no-op overhead. Fixed virtual metadata, regular files/implicit directories and ordinary stat-visible backing changes remain explicit limits; no general POSIX or watcher protocol is established.


## Batched and incremental condition production

The [producer comparison](results/incremental-conditions/REPORT.md) remeasures Ninja, Ninja + ccache, whole-namespace gating, original selective production, batched production and incremental production across six cases and seven randomized blocks. All 252 libraries and 7,812 object identities match CLI references, with expected compile/link and fragment-reuse counts. [Compile-heavy checks](results/incremental-conditions/BOUNDARIES.md) add nine builds and 279 objects. All 51 tests pass.

Bitset aggregation reduces condition merges to 1,950 versus the diagnostic profile's 28,691 calls. Incremental parsing additionally reuses 30/31 action/journal/cwd fragments: a source edit/revert parses 170 queries and an audit-header edit 62, instead of all 5,266. The final index is byte-for-byte equivalent; namespace classification and positive backing-file verification still run. The current-request fragment cache is 37,210 bytes for the fixture, capped at 64 entries and 8 MiB. Missing/corrupt state recomputes, and optional cache publication failure does not discard a valid index.

Source-edit export medians are 20.09 / 13.63 / 9.28 ms for original / batched / incremental production. Complete source edits improve 121.81 → 111.31 ms; shared-header edits 99.95 → 88.67 ms; generated-header edits 99.81 → 88.26 ms; reverts 91.22 → 80.31 ms. Incremental wins all seven paired blocks against both older producers on each changed case. Every cache read/checksum, new extraction, aggregation, verification and publication remains timed. Cold construction is separately recorded and parses every action.

Lookup is unchanged: incremental no-op and unused-header medians are 3.62 and 3.78 ms. Ninja still wins source edits at 68.05 ms, and Ninja + ccache reverts at 25.50 ms. Absolute timings shifted materially from earlier runs; compare the controls remeasured together. Raw samples remain ignored/local-only. Versioned [statistics](results/incremental-conditions/summary.json), [validation](results/incremental-conditions/validation.json), [test output](results/incremental-conditions/correctness-tests.txt) and [diagnostic function counts](results/incremental-conditions/publication-profile.json) retain reviewable evidence.

The next research question is the remaining complete-pipeline gap: snapshot preparation/authentication, process lifetime, dependency/view construction, object import and linking. A native producer can remain a control, but the residual export cost alone no longer explains the latency difference.


## Shared immutable validation

The [matched validation comparison](results/shared-validation/REPORT.md) shares equal-visibility LLVM trees during serial cache validation and memoizes supported immutable observations by view/op/cwd/path. Compiler workers stay private. Native source-edit setup falls from 27.42 to 15.12 ms; replay from 13.04 to 1.28 ms. Complete source edits improve from 117.16 to 102.86 ms versus Ninja's 71.13 ms, closing about 31% of the gap. Header/revert medians improve roughly 15%; no-op/unused-header decisions stay around 3.5 ms. Ninja remains faster on source/header edits, ccache on reverts. Memo's smaller extra win over tree sharing varies by block.

Across the main run, separate pilot and compile-heavy checks, 387 libraries and 11,997 object identities match independent references and runtime probes. Sixty-three tests include equal/distinct masks with parallel misses, negative queries, native cwd transitions, cache corruption/history and memo saturation. The memo cap accounts for key/path/record costs up to 8 MiB rather than enforcing measured allocator/RSS usage. These are fresh-process requests over an immutable explicit provider, not general mutable POSIX workspaces. Snapshot preparation, native process lifetime and export/publication remain useful targets; see [compiler prospects](../../research/compiler/prospects.md).


## Remove redundant snapshot handoff and retain the native process

The [pipeline comparison](results/pipeline-handoff/REPORT.md) reduces source edits from 96.26 to 67.44 ms versus Ninja's 65.45 ms, removing about 94% of the excess in the same run. Direct snapshot publication removes a producer round trip; a serial native worker retains process/library initialization while releasing per-request pools, input mappings, dependency state and compiler filesystems before acknowledgement. Headers remain roughly 4–5 ms slower than Ninja; reverts beat plain Ninja but remain slower than ccache. Native publication/reporting cost about 0.1/2.4 ms and were not the large residual.

The main run plus compile-heavy checks validate 219 libraries and 6,789 object identities against independent references. All 74 tests pass, including exact snapshot bytes, corrupted admission, worker repetition, failure/restart and recreated output-directory handling. Residency has an explicit cost: 218.34 MiB cumulative peak in the main run, with startup included in a separate seed. This is not current idle RSS or a production memory quota. Native setup and condition export still cost about 14/9 ms; see the report for paired comparisons, cold setup, scope and remaining work.


## Digest providers remove more native setup cost

The [digest report](results/digest-providers/REPORT.md) splits setup and finds roughly 6 ms in admission plus 5.5 ms per-file hashing with LLVM SHA-256. OpenSSL SHA-256 keeps the same identities/checks and reduces setup to about 6 ms. A second matched comparison uses explicitly tagged/versioned BLAKE3 snapshots/query fingerprints, reducing setup to about 4.3 ms. Source edits take 57.27 ms versus optimized SHA-256's 59.13 ms and Ninja's 65.52 ms; headers take about 36 ms versus Ninja's 42 ms. All seven paired source/header comparisons beat Ninja. Reverts improve to 31.15 ms but ccache remains faster at 24.50 ms.

SHA-256 cache-envelope, selected-journal, object, condition and receipt contracts remain unchanged. BLAKE3 uses `GAIACIN3`/`blake3:` roots, `GAIAJR02` and a separate action namespace. Both algorithms can alternate within a worker without mixing candidates. All 92 tests pass; both matched runs plus nine compile-heavy checks validate 345 libraries/10,695 object identities. The provider libraries/helper and measured sources are pinned. Main native peaks are around 224–227 MiB; startup, single-target scope, stat-visible edits and virtual provider limitations remain explicit. Condition export/preparation remain substantial, so this is no final floor claim.


## Complete-result reuse and resident lightweight decisions

The [linked-result comparison](results/linked-results/REPORT.md) now wins all seven paired blocks against Ninja and Ninja + ccache in all six measured scenarios. The latest path takes 2.51 ms unchanged, 60.94 ms on a source edit, about 38 ms on headers and 9.43 ms on revert (ccache: 24.74 ms). Retaining linked results avoids snapshot admission/import/link/export on a proven historical hit. Reusing successful completion records avoids redundant retention validation, and a small resident checker resets all request allocations before acknowledgement. No request/graph work moves outside the operation clock.

Retention still adds about 3–5.5 ms to ordinary source/header misses versus unretained BLAKE3. The cache is bounded to three entries/16 MiB committed payloads per output directory, with staging/metadata accounted separately and a single-writer contract. Copied outputs are always hashed; native conditions/request/tool/stability checks remain. Current descriptor version `GAIALR02` also preserves regular mode bits. The checker finishes at 2.89 MiB RSS; native compiler residency is separate. All 113 tests and 387 libraries/11,997 object checks pass across the two matched runs and compile-heavy correctness checks. Broader linker input capture, cold workflows, full history horizons, long-run resource behavior and durable multi-file transactions remain open.
