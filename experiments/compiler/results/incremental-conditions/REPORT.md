# Incremental build decisions and history

Run `20261030T194327.477685Z`; **complete**; 7 randomized blocks; warm page cache.

Same Zstandard 1.5.7 portable C library plus one probe, eight workers, exact compiler flags and ordered linker inputs. Ninja retains normal no-op/link skipping. Gaia journal always runs the producer and LLVM host; history adds up to three validated journal candidates per action; fast checks the whole namespace; selective checks conditions from successful journals; batched combines job masks; incremental reuses parsed per-action fragments.

| Scenario | ninja ms | ninja-ccache ms | gaia-fast ms | gaia-selective ms | gaia-batched ms | gaia-incremental ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| unchanged | 3.44 | 3.09 | 2.56 | 3.51 | 3.70 | 3.62 |
| implementation | 68.05 | 101.67 | 101.77 | 121.81 | 115.29 | 111.31 |
| shared-header | 44.05 | 67.17 | 77.05 | 99.95 | 93.73 | 88.67 |
| generated-header | 43.70 | 67.07 | 77.09 | 99.81 | 93.32 | 88.26 |
| unused-header | 3.06 | 3.03 | 67.74 | 3.61 | 3.54 | 3.78 |
| revert | 67.88 | 25.50 | 68.59 | 91.22 | 84.21 | 80.31 |

Clock starts after the editor applies a change and before the build request. Every fast-path sample includes request identity creation, watch-list preparation, a fresh lightweight Odin process, input metadata checks, receipt validation and retained-result loading. A hit launches no producer/LLVM process and performs no link. A miss includes the original stat scan, delta/plan encoding, producer publication, receipt handoff, native compilation/cache/linking and new receipt publication. All condition producers include extraction, cache validation, construction and publication in this clock.

The whole-namespace gate watches every admitted file. The selective gate checks per-job virtual membership, path ancestors and queried directory listings, and watches contents of queried regular files plus native tools. Missing/corrupt receipts or outputs and changed requests fall back. Output contents are rehashed if their metadata changes; preserved-metadata mutations are outside this stat-visible contract. Inputs must match the preflight stamp again before a receipt can be published after success. LLVM libraries are not linked into the lightweight checker. No daemon or hidden compiler residency is assumed.

Each observation restores independent output/cache/Ninja log state outside timing. Revert starts from an edited build after visiting baseline and edited states. History retains at most three complete records per action, including the latest; this is not a global cache quota. The incremental fragment cache retains only the current request, with at most 64 entries and 8 MiB, validates its checksum, and keys reuse by action, selected journal and logical cwd. Namespace classification and backing-file verification are always rebuilt. Every object candidate still validates framing, checksum, action identity and recorded filesystem observations. Concurrent rotation may lose reuse opportunities, but incomplete/corrupt candidates must miss.

All object identities and libraries match independent CLI references, and runtime probes follow each build. The high-fanout header has 26 independently identified readers. Expected compiler/link counts are checked. Initial SDK admission, graph generation, editor writes, state restoration and parent validation are excluded for all engines. Fixed known namespace, ordinary stat-visible edits, one C target and a warm-cache virtualized Linux host limit generalization. Native compiler tests cover optional-header and earlier-include appearance. Directory listing and visibility semantics are tested against synthetic query journals for the explicit provider. No physical watcher, arbitrary SDK or POSIX/symlink equivalence is claimed.

Tool versions, source/tool identities, native counters and samples are in ignored `results.json`. Reports and compact validation/summary files can be retained in version control.

## Result

Both optimizations preserve the original `GAIACQ01` condition bytes and the lightweight native checker. The bitset producer merges shared query targets across jobs before classifying their path ancestors. The incremental producer additionally reuses parsed query structure by action identity, selected journal SHA-256 and logical cwd. It still reconstructs conditions against the current namespace and verifies positive backing-file contents on every export.

| Changed request | Original export ms | Batched export ms | Incremental export ms | Original pipeline ms | Incremental pipeline ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| implementation | 20.09 | 13.63 | 9.28 | 121.81 | 111.31 |
| shared-header | 20.27 | 13.44 | 9.09 | 99.95 | 88.67 |
| generated-header | 20.09 | 13.47 | 9.19 | 99.81 | 88.26 |
| revert | 20.20 | 13.37 | 9.33 | 91.22 | 80.31 |

For a source edit, export falls from 20.09 to 9.28 ms (53.8% lower), while the complete pipeline improves from 121.81 to 111.31 ms (8.6% lower). Header-edit pipelines improve about 11–12%, and revert improves about 12%. Incremental wins all seven paired blocks against both original and batched publication on every changed scenario. All extraction, cache parsing/checksum validation, aggregation, positive-file verification and atomic fragment-cache publication remain inside the build-request clock.

The optimization reuses 30/31 fragments and parses only 170 queries for an implementation edit or revert, and 62 for a shared/generated audit header, versus 5,266 queries for the full producer. Bitset aggregation reduces merge operations to 1,950 rather than the original profile's 28,691 calls. The current-request fragment cache is 37,210 bytes for this fixture. Cold creation still parses all 31 journals; cache preparation is not assumed free.

## Limits and remaining gap

The final condition index, namespace classification and backing-file verification are still rebuilt. This is incremental parsing/structure reuse, not an in-place mutable condition index. Only the current request's fragments are retained (maximum 64 entries and 8 MiB); old entries are dropped, and corrupt/incompatible cache state recomputes. Optional fragment-cache write failure does not discard an otherwise valid condition index. Records are local integrity checks, not remote authentication.

Unchanged and irrelevant-edit requests do not run any producer: incremental medians are 3.62 and 3.78 ms. The whole-namespace gate remains faster for unchanged work (2.56 ms), while its unused-header edit still enters the pipeline (67.74 ms). Ninja is 3.44 ms unchanged and 3.06 ms for the unused-header edit. These tiny lookup differences do not establish a new advantage: the native lookup format/algorithm is unchanged.

The pipeline gap remains: an implementation edit is 111.31 ms versus Ninja's 68.05 ms and Ninja + ccache's 101.67 ms. An incremental revert is 80.31 ms versus ccache's 25.50 ms. Once publication is around 9 ms, snapshot preparation, native startup, dependency validation, object import and linking deserve renewed attribution before another rewrite. Historical linked results remain a candidate for revert latency.

All controls were remeasured together. Absolute medians shifted substantially from the previous run; do not attribute that cross-run shift to these changes. Compare paired observations within this run.

## Paired complete-pipeline differences

Negative differences favor incremental publication. Pairs are observations within the same randomized block, not simultaneous execution.

| Scenario | Incremental − original median ms | Incremental wins | Incremental − batched median ms | Incremental wins |
| --- | ---: | ---: | ---: | ---: |
| unchanged | +0.15 | 1/7 | -0.24 | 4/7 |
| implementation | -11.61 | 7/7 | -3.80 | 7/7 |
| shared-header | -10.93 | 7/7 | -4.29 | 7/7 |
| generated-header | -12.14 | 7/7 | -4.64 | 7/7 |
| unused-header | +0.19 | 3/7 | +0.01 | 3/7 |
| revert | -10.17 | 7/7 | -3.77 | 7/7 |

## Evidence and reproduction

All 252 timed libraries and 7,812 object identities match independent CLI references, runtime probes and expected work counts. Stage assertions verify the expected fragment reuse rather than inferring it from timing. Fifty-one tests pass, including byte-for-byte comparison with the original encoder over randomized masks, all query kinds, directory listings, cwd changes, action reorder, one-action changes, cache corruption, publication failure, changed namespaces/backing bytes and the native invalidation suite.

See [validation](validation.json), [compact statistics](summary.json), [test output](correctness-tests.txt), [separate diagnostic call counts](publication-profile.json), and [fresh-run instructions](../../README.md#incremental-condition-production). Profiling adds overhead and supplies mechanism counts only, not timing samples. Full observations in ignored `results.json` are local-only; their checksum and frozen measured source identities are retained. The native regular-file/implicit-directory provider, explicit masks, canonical paths, stat-visible backing changes and normalized identities remain the same experimental contract; no broader POSIX, watcher or SDK-discovery support is claimed.

[Compile-heavy checks](BOUNDARIES.md) add nine builds and 279 objects for the real 26-reader header, changed global flags and clean builds. Expected fragment hits/misses also pass. These are correctness checks, not additional timing conclusions.
