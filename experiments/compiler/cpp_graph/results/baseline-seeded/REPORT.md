# A real fmt library in a baseline-seeded C++ graph

Run `20261031T033811.923406Z`. Three paired blocks, 24 timed whole-graph operations, two clean boundaries. This is **unmodified fmt 12.2.0 plus a labelled integration fixture**, not a broad production application or the full upstream fmt test suite.

## Result

| Whole graph, milliseconds | Ninja + ccache | Programmatic host | Host paired wins |
| --- | ---: | ---: | ---: |
| No-op | 24.42 | 23.84 | 2/3 |
| Fresh implementation edit | 397.91 | 293.49 | 3/3 |
| Fresh used-header edit | 423.45 | 382.32 | 3/3 |
| Revert to baseline | 71.18 | 55.10 | 3/3 |

The host improves implementation edits about **26%**, used-header edits **10%** and reverts **23%** in these three pairs. No-op differences are small and change sign; this does not establish a general no-op win. The single clean boundary favors Ninja: **1,931.63 versus 2,201.57 ms**. The initial integration is useful evidence for incremental work, not a universal replacement for Ninja.

The source/header cases compile **one/four actual translation units in every block**. After clean baseline builds, both engines' compiled-object caches are copied to baseline-only seeds, then restored before each block outside timing. Source/header results cannot therefore be supplied by previously compiled edited variants. The original [continuous-history trace](../repeated-trace/REPORT.md) is preserved separately; its blended medians are not called ordinary edit compilation.

## Graph and equivalent work

The upstream library compiles `format.cc` and `os.cc`. A two-TU fixture shared library uses real fmt formatting, strings, arrays and numeric algorithms. Two one-TU fixture executables depend on that library and fmt. There are **four target nodes, three dependency levels and six translation units**. The used fixture header and implementation changes alter observable results.

Both engines use the same explicit C++17/O2/PIC compiler flags and captured ordered LLD arguments. Ninja 1.13.2 uses ccache 4.14.1 with content compiler checking, normal dependency/command logs, a 1 GiB cache and no remote cache. The programmatic adapter uses the existing pinned Odin/Clang 22.1.8 host per target. Each target has private compiler/linker process state, at most four workers and a global maximum of eight; the two independent leaves overlap. The upstream fmt sources are unchanged and [pinned by archive SHA-256](provenance.json).

| Per operation | Native actual compiler executions | Ninja ccache commands scheduled | Links, both |
| --- | ---: | ---: | ---: |
| No-op | 0 | 0 | 0 |
| Source | 1 | 1 | 3 |
| Used header | 4 | 4 | 3 |
| Revert | 0 | 4 | 3 |

Ninja's scheduled compiler commands include ccache hits; they are not interpreted as actual compiler executions. The final block's [ccache counters](ccache-stats.txt) show 11 misses including the six baseline clean objects and five edited objects, plus four direct hits for the revert. They are final-block seeded counters, not an aggregate across reset blocks. Native execution/link counts are asserted exactly in every block. Both engines retain object history within a trace but **neither restores historical whole linked results**: all three dependent targets relink after each change and revert. The unaffected fmt target skips every incremental operation.

## Input, linker and output checks

The immutable compiler view contains **1,363 source/SDK files, 31,894,193 payload bytes**: project headers, complete selected C++/Clang header roots and positive C SDK dependencies. Clang search paths are explicit. Recursive LLD trace and runtime/tool discovery pin **63 external SDK/tool/link inputs**, including scripts and their resolved libraries. Linker `-l` lookups become selected absolute inputs. Dependent target outputs are separately pinned before and after each link; their identity changes the derived result/link key without changing compilation context.

Both engines include the **same physical source/SDK/link pre/post guard**. It stats admitted files and rehashes changed inode/time/size identities. Thus the 24 ms no-op numbers are guarded whole-operation costs, **not raw Ninja launch time**; common metadata scanning is substantial. This is trusted local stat reuse with a closed admitted namespace, not hostile-writer protection or automatic arbitrary SDK namespace updates.

The existing direct-handoff interface rejects foreign `.o` names. The adapter copies only pinned CRT startup objects to immutable `.input` aliases, uses the same aliased argv for both engines and checks originals/copies. Independent original-versus-aliased CLI links are **byte-identical for all four public outputs**. No shared native backend/header was changed.

Every measured operation checks all four public output hashes against independent CLI references and runs both executables. Every produced/imported native object is checked against the corresponding CLI object hash: **42 native intermediate-object comparisons** including the clean boundary. All six final baseline Ninja objects also match the independent CLI bytes in a [supplemental check](supplemental-checks.json). Runtime checks validate version, formatting, header bias and numeric results; they run after the operation timer. Public artifact hashing and input/link guards remain inside the timer. Native intermediate objects stay private in-memory/cache artifacts rather than exported user files; the named graph contract is the two libraries and two executables.

## Cache lifetime and startup costs

Only **compiled-object caches** are reset to baseline seeds per block. Resident native processes, sealed input segments and authenticated input-digest caches stay warm, as do filesystem pages. Current baseline outputs and receipts persist after each revert. This separates unseen edited-object work from input-session authentication; it does not claim a cold process/toolchain for every edit.

Engine setup separately costs **633.97 ms Ninja / 638.81 ms host**, including initial physical SDK/tool admission and native process creation where applicable. The single clean operations above include first snapshot publication, six compilations, four links and artifact checks. These startup/admission costs are retained, not hidden as incremental gains. They are single boundaries and are not added to unrelated run medians as a new measurement.

The changed-operation paired host-minus-Ninja deltas are **−108/−94/−102 ms source**, **−32/−61/−39 ms header**, and **−17/−14/−16 ms revert**. No-op deltas are **+1.07/−0.58/−1.62 ms**. Three blocks are an initial Linux developer-laptop proof, not a cross-platform or production-scale result.

[Summary](summary.json), [validation](validation.json), [helper-test log](correctness-tests.txt), [provenance](provenance.json) and the ignored raw observations retain evidence. Exact machine paths and toolchain/source snapshots stay in ignored raw/work data; compact summaries are portable. No source-control, compiler-service standard, generated-header behavior or general multi-project build correctness is established beyond this explicit graph.
