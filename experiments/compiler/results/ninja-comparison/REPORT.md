# Ninja incremental-build comparison

Run `20261030T030550.682856Z`; **complete**; 7 randomized blocks; warm page cache.

Same Zstandard 1.5.7 portable C library plus one probe, Clang/LLD identities, optimization flags, eight workers and ordered link inputs. Ninja uses compiler depfiles and its normal no-op/link skipping. Ninja+ccache uses a private default-policy cache with content-based compiler identity and no remote storage. Gaia uses the existing dependency-journal host and always links.

| Scenario | Ninja ms | Ninja+ccache ms | Gaia pipeline ms | Gaia / Ninja |
| --- | ---: | ---: | ---: | ---: |
| unchanged | 5.17 | 5.52 | 109.82 | 21.26× |
| implementation | 125.31 | 182.01 | 171.15 | 1.37× |
| shared-header | 81.85 | 126.84 | 122.36 | 1.49× |
| generated-header | 78.93 | 121.09 | 125.06 | 1.58× |
| unused-header | 5.47 | 6.02 | 108.75 | 19.88× |
| high-fanout-header | 4750.66 | 5060.23 | 4777.14 | 1.01× |
| flags | 4970.94 | 378.17 | 4806.62 | 0.97× |
| revert | 127.20 | 43.63 | 159.45 | 1.25× |
| clean | 4854.50 | 5133.55 | 4744.87 | 0.98× |

Clock starts after the editor applies a change and before the build request. Gaia includes a stat scan of every file in the already admitted namespace, changed-file reads/delta encoding, snapshot producer invocation/publication, receipt validation, native consumer, dependency validation and actual linking. Ninja includes graph/dependency checking, subprocess compilation/cache access and linking when needed. Parent artifact/runtime validation follows timing for every engine.

Each observation restores the same baseline build/cache state outside timing. Revert starts from the edited build, with the baseline and edited history visited for both caches. Clean starts with no outputs or object cache. Initial graph/SDK admission, reference builds, tool builds, cache-state restoration and editor writes are excluded for all engines. Fixed configured namespace: no general SDK discovery, filesystem watcher, new-directory or negative-lookup comparison is claimed.

All timed libraries and per-object identities must match independent CLI references; observable probe/version checks run after each build. The high-fanout header has 26 independently identified readers. Tests use a small single-target C library on one host; results do not establish multi-target/C++ behavior. Gaia consumer clocks include its own object hashing and reporting; Ninja output validation is performed by the parent after timing.

Tool versions, exact commands, source/tool pins, cache statistics and raw samples are in ignored `results.json` (local-only; no published download). [Validation](validation.json), [summary statistics](summary.json) and [comparison-tool acquisition pins](comparison-tool-provenance.json) are versioned.

## Interpretation

Gaia does not beat Ninja across incremental work. It wins the clean-build median by 2.3% (6/7 paired blocks), and the global-flag median by 3.3% (7/7). High-fanout edits are mixed against Ninja (4/7 paired wins, slightly slower overall median). These are small single-target gains on the available virtualized Linux host, not a general build-system advantage.

Ninja skips both compilation and linking for unchanged and unused-header cases. Gaia still scans inputs, constructs/authenticates a snapshot, loads LLVM, replays observations, imports every object and links. That leaves roughly a 100 ms gap even when no compilation is needed. Low-fanout edits are also slower than plain Ninja.

ccache retains historical object variants and can reuse results when preprocessing removes an irrelevant flag change. The tested flag is observable only in the probe, so this is a deliberately narrow global-flag case, not arbitrary optimization/ABI changes. Gaia currently keys exact command lines and retains one latest journal candidate per action; reverts recompile the edited unit. ccache statistics below distinguish actual reuse from a faster compiler.

## Paired comparisons

Pairs are randomized engine observations within the same block, not simultaneous execution. Difference of medians can differ from median paired difference. Negative deltas favor Gaia.

| Scenario | Gaia − Ninja median delta ms | Gaia wins | Gaia − Ninja+ccache median delta ms | Gaia wins |
| --- | ---: | ---: | ---: | ---: |
| unchanged | +104.45 | 0/7 | +104.49 | 0/7 |
| implementation | +37.95 | 1/7 | -12.86 | 4/7 |
| shared-header | +40.30 | 0/7 | -6.27 | 5/7 |
| generated-header | +45.84 | 0/7 | +5.45 | 2/7 |
| unused-header | +103.00 | 0/7 | +101.21 | 0/7 |
| high-fanout-header | -83.33 | 4/7 | -244.21 | 7/7 |
| flags | -156.99 | 7/7 | +4412.31 | 0/7 |
| revert | +32.98 | 0/7 | +116.49 | 0/7 |
| clean | -109.64 | 6/7 | -409.72 | 7/7 |

## ccache behavior

| Scenario | Ninja compile edges | Direct hits | Preprocessed hits | Cache misses |
| --- | ---: | ---: | ---: | ---: |
| unchanged | 0 | 0 | 0 | 0 |
| implementation | 1 | 0 | 0 | 1 |
| shared-header | 1 | 0 | 0 | 1 |
| generated-header | 1 | 0 | 0 | 1 |
| unused-header | 0 | 0 | 0 | 0 |
| high-fanout-header | 26 | 0 | 0 | 26 |
| flags | 31 | 0 | 30 | 1 |
| revert | 1 | 1 | 0 | 0 |
| clean | 31 | 0 | 0 | 31 |

## Reproduction and boundaries

See the [driver instructions](../../README.md#ninja-incremental-build-comparison) for a fresh host/producer build and portable tool selection. Measurement versions: Ninja 1.13.2, ccache 4.14.1, Clang/LLVM/LLD 22.1.8. Observed CPU: AMD Ryzen AI 7 PRO 450, 16 logical CPUs exposed by a Microsoft hypervisor; eight compiler workers, warm page cache, no affinity/power tuning. No raw results from discarded smoke runs are included.

Clock qualifications: Ninja graph generation (including a flags edit) precedes its build-request clock; Gaia plan/delta encoding stays within its clock. SDK and initial namespace admission are setup. Source mutations are ordinary stat-visible edits in a fixed namespace; new directory discovery and preserved-timestamp changes are not tested. State restoration precedes each observation. Headers are not artificially declared as dependencies of every Ninja job.

The first smoke harness accidentally shared Ninja logs across engines; it was corrected before this run. Integration tests verify private `.ninja_log`/`.ninja_deps`, and every timed sample enforces expected compile/link counts. The corrected smoke and this full run are separate datasets.

References: [Ninja depfile/dependency documentation](https://ninja-build.org/manual.html#_c_c_header_dependencies), [ccache operation](https://ccache.dev/manual/latest.html#_how_ccache_works).
