# Share immutable validation trees and observations

Run `20261030T202047.020103Z`; **complete**; 7 randomized blocks; warm page cache.

Same Zstandard 1.5.7 portable C library plus one probe, eight workers, exact compiler flags and ordered linker inputs. Ninja retains normal no-op/link skipping. Gaia journal always runs the producer and LLVM host; history adds up to three validated journal candidates per action; fast checks the whole namespace; selective checks conditions from successful journals; batched combines job masks; incremental reuses parsed per-action fragments. Shared also shares equal-visibility trees during serial validation; memo additionally reuses immutable observation fingerprints within that request.

| Scenario | ninja ms | ninja-ccache ms | gaia-incremental ms | gaia-shared ms | gaia-memo ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| unchanged | 3.31 | 3.07 | 3.61 | 3.64 | 3.53 |
| implementation | 71.13 | 106.18 | 117.16 | 106.26 | 102.86 |
| shared-header | 46.28 | 70.63 | 92.67 | 82.07 | 78.88 |
| generated-header | 44.54 | 70.20 | 91.96 | 80.50 | 78.15 |
| unused-header | 3.15 | 3.25 | 3.64 | 3.53 | 3.53 |
| revert | 69.90 | 25.72 | 83.39 | 72.51 | 71.18 |

Clock starts after the editor applies a change and before the build request. Every fast-path sample includes request identity creation, watch-list preparation, a fresh lightweight Odin process, input metadata checks, receipt validation and retained-result loading. A hit launches no producer/LLVM process and performs no link. A miss includes the original stat scan, delta/plan encoding, producer publication, receipt handoff, native compilation/cache/linking and new receipt publication. All condition producers include extraction, cache validation, construction and publication in this clock.

The whole-namespace gate watches every admitted file. The selective gate checks per-job virtual membership, path ancestors and queried directory listings, and watches contents of queried regular files plus native tools. Missing/corrupt receipts or outputs and changed requests fall back. Output contents are rehashed if their metadata changes; preserved-metadata mutations are outside this stat-visible contract. Inputs must match the preflight stamp again before a receipt can be published after success. LLVM libraries are not linked into the lightweight checker. No daemon or hidden compiler residency is assumed.

Each observation restores independent output/cache/Ninja log state outside timing. Revert starts from an edited build after visiting baseline and edited states. History retains at most three complete records per action, including the latest; this is not a global cache quota. The incremental fragment cache retains only the current request, with at most 64 entries and 8 MiB, validates its checksum, and keys reuse by action, selected journal and logical cwd. Namespace classification and backing-file verification are always rebuilt. Every object candidate still validates framing, checksum, action identity and recorded filesystem observations. Concurrent rotation may lose reuse opportunities, but incomplete/corrupt candidates must miss.

All object identities and libraries match independent CLI references, and runtime probes follow each build. The high-fanout header has 26 independently identified readers. Expected compiler/link counts are checked. Initial SDK admission, graph generation, editor writes, state restoration and parent validation are excluded for all engines. Fixed known namespace, ordinary stat-visible edits, one C target and a warm-cache virtualized Linux host limit generalization. Native compiler tests cover optional-header and earlier-include appearance. Directory listing and visibility semantics are tested against synthetic query journals for the explicit provider. No physical watcher, arbitrary SDK or POSIX/symlink equivalence is claimed.

Tool versions, source/tool identities, native counters and samples are in ignored `results.json`. Reports and compact validation/summary files can be retained in version control.

## What changed and why

The existing native host reconstructed one LLVM in-memory filesystem per cached action. Equal visibility can share the tree during serial validation. Full input-mask membership defines the group; each candidate starts at the original cwd. Compiler workers always get private filesystems and never access the shared validation map.

A second mode memoizes supported observation fingerprints by filesystem, operation, cwd and original query path. Cwd mutations always execute and update the next key. Cache records still validate complete framing, checksums, action identity and object integrity, and every journal entry still compares its expected fingerprint. The request-local memo stops inserting at 8 MiB of accounted key/path/record costs; this is not a strict allocator/RSS bound. Unsupported observations are never inserted. Journals, object records, condition bytes, producer and lightweight checker retain their formats and behavior. No long-lived process is used.

## Complete-operation results

| Operation | Previous ms | Shared trees ms | Shared + memo ms | Ninja ms | Ninja + ccache ms | Memo wins vs previous |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| unchanged | 3.61 | 3.64 | 3.53 | 3.31 | 3.07 | 5/7 |
| implementation | 117.16 | 106.26 | 102.86 | 71.13 | 106.18 | 7/7 |
| shared-header | 92.67 | 82.07 | 78.88 | 46.28 | 70.63 | 7/7 |
| generated-header | 91.96 | 80.50 | 78.15 | 44.54 | 70.20 | 5/7 |
| unused-header | 3.64 | 3.53 | 3.53 | 3.15 | 3.25 | 5/7 |
| revert | 83.39 | 72.51 | 71.18 | 69.90 | 25.72 | 7/7 |

Source edits improve from 117.16 to 102.86 ms (12.2%). Against the remeasured Ninja median of 71.13 ms, the excess falls from 46.04 to 31.74 ms: about 31% of the gap closed. The new path remains about 45% slower than Ninja. Header edits improve about 15%; reverts about 15%. Memo's incremental benefit over shared trees is smaller (roughly 1–3 ms), with only 4–6 paired wins out of seven depending on the changed scenario. Generated-header comparisons include noisy blocks: memo beats the previous path in five of seven. Do not infer that every observation improved.

No-op and irrelevant-header requests continue to bypass the producer, LLVM and linker, around 3.5 ms. The gate is identical across the three Gaia modes; tiny differences do not establish a gate optimization. The source-edit memo median is slightly below ccache, with 6/7 paired wins; Ninja is still faster in every source/header-edit block. Reverts are approximately tied with plain Ninja and much slower than ccache's 25.72 ms.

## Attribution and remaining work

| Source-edit stage/counter | Previous | Shared trees | Shared + memo |
| --- | ---: | ---: | ---: |
| Native setup ms | 27.42 | 18.45 | 15.12 |
| Journal validation ms | 13.04 | 4.59 | 1.28 |
| Tree construction ms | 8.39 | 0.68 | 1.13 |
| Compile wall ms | 30.14 | 31.39 | 30.84 |
| Link ms | 4.53 | 4.16 | 4.45 |
| Trees built | 31.00 | 2.00 | 2.00 |
| Memo hits | 0.00 | 0.00 | 4779.00 |
| Accounted memo bytes | 0.00 | 0.00 | 193104.00 |

Tree counts drop from 31 to two for a one-action miss, and to one on a fully cached revert. The source-edit memo reuses 4,779 observations. The accounting footprint is about 193 kB. Validation falls from 13.04 to 1.28 ms, and native setup from 27.42 to 15.12 ms. Tree construction includes the compiler's private tree; validation and setup are nested clocks, so these counters must not be added.

The optimized source-edit request still spends about 17.10 ms in preparation/snapshot production, 9.93 ms exporting conditions, 15.12 ms native setup, 30.84 ms compile wall and 4.45 ms linking. These are independent medians and do not sum into an exact partition. Fresh process loading, publication, reporting and teardown also contribute outside the native workload clock. The next useful experiment should attribute those residual costs and test a cheaper snapshot/update handoff or bounded native residency, retaining full request timing and request isolation.

## Verification and limits

The main run checks 210 libraries and 6,510 object identities against independent CLI references, with runtime probes and exact compiler/link/fragment counts. [Summary](summary.json) retains native diagnostics, min/max and paired results; [validation](validation.json) binds the ignored raw observations. Sixty-three [correctness tests](correctness-tests.txt) pass, including both new policies, eviction, corruption, negative lookups, equal/distinct virtual visibility with parallel compiler misses and CLI object/library byte comparisons. A synthetic native journal exercises repeated cwd transitions and opposite existence results for the same relative path. A 50,001-query case verifies saturation falls back to observation without exceeding the accounting cap. Directory enumeration is not exercised by the real compiler fixture.

An earlier independent [sharing pilot](sharing-pilot/summary.json) checks another 168 libraries and 5,208 objects; its controls used the pre-memo binary. It supports tree sharing but must not be pooled into the main randomized comparison. Its [validation](sharing-pilot/validation.json) pins that binary and raw artifact. [Compile-heavy checks](BOUNDARIES.md) cover the 26-reader header, changed flags and clean builds separately; their single observations support correctness only.

This remains one portable C target, an explicitly admitted namespace, canonical regular files/implicit directories, fixed virtual metadata and ordinary stat-visible backing changes on a warm-cache virtual Linux machine. Sharing depends on immutable request inputs and serial validation; extending it across concurrently mutable workspaces would need a different isolation contract. Initial SDK admission, graph generation, editor writes, state restoration and parent verification are excluded equally. Full local observations and frozen measured sources are ignored; portable reports and compact evidence stay versioned. See [reproduction and policy details](../../README.md#share-immutable-validation-work).
