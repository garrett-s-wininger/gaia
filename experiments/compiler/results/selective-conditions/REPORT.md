# Incremental build decisions and history

Run `20261030T185318.921520Z`; **complete**; 7 randomized blocks; warm page cache.

Same Zstandard 1.5.7 portable C library plus one probe, eight workers, exact compiler flags and ordered linker inputs. Ninja retains normal no-op/link skipping. Gaia journal always runs the producer and LLVM host; history adds up to three validated journal candidates per action; fast checks the whole namespace; selective checks conditions derived from the exact successful journals.

| Scenario | ninja ms | ninja-ccache ms | gaia-fast ms | gaia-selective ms |
| --- | ---: | ---: | ---: | ---: |
| unchanged | 8.60 | 8.09 | 6.83 | 10.83 |
| implementation | 206.73 | 316.98 | 294.56 | 376.67 |
| shared-header | 125.34 | 187.53 | 221.60 | 294.14 |
| generated-header | 122.91 | 191.38 | 222.79 | 293.06 |
| unused-header | 8.19 | 8.02 | 197.84 | 12.47 |
| revert | 209.51 | 76.12 | 199.58 | 276.62 |

Clock starts after the editor applies a change and before the build request. Every fast-path sample includes request identity creation, watch-list preparation, a fresh lightweight Odin process, input metadata checks, receipt validation and retained-result loading. A hit launches no producer/LLVM process and performs no link. A miss includes the original stat scan, delta/plan encoding, producer publication, receipt handoff, native compilation/cache/linking and new receipt publication. Selective misses also include journal extraction, index construction and publication.

The whole-namespace gate watches every admitted file. The selective gate checks per-job virtual membership, path ancestors and queried directory listings, and watches contents of queried regular files plus native tools. Missing/corrupt receipts or outputs and changed requests fall back. Output contents are rehashed if their metadata changes; preserved-metadata mutations are outside this stat-visible contract. Inputs must match the preflight stamp again before a receipt can be published after success. LLVM libraries are not linked into the lightweight checker. No daemon or hidden compiler residency is assumed.

Each observation restores independent output/cache/Ninja log state outside timing. Revert starts from an edited build after visiting baseline and edited states. History retains at most three complete records per action, including the latest; this is not a global cache quota. Every candidate still validates framing, checksum, action identity and recorded filesystem observations. Concurrent rotation may lose reuse opportunities, but incomplete/corrupt candidates must miss.

All object identities and libraries match independent CLI references, and runtime probes follow each build. The high-fanout header has 26 independently identified readers. Expected compiler/link counts are checked. Initial SDK admission, graph generation, editor writes, state restoration and parent validation are excluded for all engines. Fixed known namespace, ordinary stat-visible edits, one C target and a warm-cache virtualized Linux host limit generalization. Native compiler tests cover optional-header and earlier-include appearance. Directory listing and visibility semantics are tested against synthetic query journals for the explicit provider. No physical watcher, arbitrary SDK or POSIX/symlink equivalence is claimed.

Tool versions, source/tool identities, native counters and samples are in ignored `results.json`. Reports and compact validation/summary files can be retained in version control.

## Interpretation

The selective index achieves the intended irrelevant-edit behavior. Unused-header changes take 12.47 ms, versus 197.84 ms for the whole-namespace gate, a 15.9× improvement and 7/7 paired wins. Selective unchanged requests take 10.83 ms. Neither case beats Ninja: its medians are 8.19 and 8.60 ms respectively. The index adds about 4 ms to unchanged requests compared with the simpler whole-namespace gate.

Changed builds regress because index publication is real work. Implementation edits take 376.67 ms versus the whole-namespace gate's 294.56 ms; shared-header edits take 294.14 versus 221.60 ms. The Python exporter takes roughly 62–65 ms per changed build. It extracts all selected journals, rebuilds conditions, verifies positive backing files and publishes a new index. These costs remain inside the pipeline clock. Moving repeated work out of lookup alone does not establish a general build-time improvement.

The initial index collapses 5,266 selected queries into 275 conditions: 187 positive regular files, 58 missing-path conditions and 30 directory-kind conditions. Its serialized size is 37,018 bytes. The measured compiler does not enumerate directories; listing conditions have explicit model tests instead. Positive-only dependency lists would miss the negative/include-shadowing behavior covered by the native compiler tests.

The next useful experiment is incremental or native condition production, reusing unaffected per-action structures and admitted content identities. A whole-view shortcut could also avoid the selective lookup overhead on unchanged requests. The current evidence supports the conditional-result boundary; the Python publication implementation is not a production performance result.

## Paired comparisons

Negative differences favor the selective gate. Pairs are observations in the same randomized block, not simultaneous execution.

| Scenario | Selective − whole gate median delta ms | Selective wins | Selective − Ninja median delta ms | Selective wins |
| --- | ---: | ---: | ---: | ---: |
| unchanged | +3.42 | 0/7 | +2.89 | 1/7 |
| implementation | +81.90 | 0/7 | +169.95 | 0/7 |
| shared-header | +76.67 | 0/7 | +168.20 | 0/7 |
| generated-header | +71.60 | 0/7 | +170.15 | 0/7 |
| unused-header | -187.31 | 7/7 | +3.65 | 0/7 |
| revert | +75.05 | 0/7 | +66.58 | 0/7 |

## Evidence and scope

All 168 timed libraries and 5,208 object identities match independent CLI references. Every runtime probe and expected compile/link count passes. The selective gate skips producer, LLVM and linking for all seven unchanged requests and all seven unused-header edits. The full suite passes 27 tests, including real compiler-journal tests for optional-header appearance, earlier include shadowing, invisible physical files, per-job masks, positive mutation/removal, identical-content touches, malformed/corrupt state, tool/request changes and refusal to publish after mutation. Directory listing and cwd-route boundary tests use synthetic query journals for the explicit provider; they are not claims that directory enumeration occurred in the timed compiler workload.

The namespace is explicitly supplied by the caller; arbitrary POSIX discovery, symlinks, hardlinks, preserved-metadata edits and concurrent workspace mutation remain outside the experiment. The provider has fixed virtual metadata and sorted direct directory entries; see the pinned [LLVM implementation](https://github.com/llvm/llvm-project/blob/llvmorg-22.1.8/llvm/lib/Support/VirtualFileSystem.cpp). Guarding full file contents for metadata-only queries is conservative and can still cause unnecessary invalidation.

See [validation](validation.json), [compact statistics](summary.json), [correctness tests](correctness-tests.txt), and [fresh-build instructions](../../README.md#selective-observed-condition-decisions). Full samples in ignored `results.json` are local-only, with their checksum retained in the manifests. Frozen measured sources are retained in the ignored run directory. Compare controls within this run; earlier absolute medians shifted with host conditions.

[Compile-heavy checks](BOUNDARIES.md) add six libraries and 186 objects for the real 26-reader header, changed global flags and clean builds. These are correctness regressions, not additional latency claims.
