# Incremental build decisions and history

Run `20261030T134240.386169Z`; **complete**; 7 randomized blocks; warm page cache.

Same Zstandard 1.5.7 portable C library plus one probe, eight workers, exact compiler flags and ordered linker inputs. Ninja retains normal no-op/link skipping. Gaia journal always runs the producer and LLVM host; history adds up to three validated journal candidates per action; fast adds a lightweight successful-build receipt check before the same history pipeline.

| Scenario | ninja ms | ninja-ccache ms | gaia-journal ms | gaia-history ms | gaia-fast ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| unchanged | 8.63 | 8.41 | 186.03 | 190.28 | 7.96 |
| implementation | 207.11 | 300.28 | 283.98 | 304.94 | 294.32 |
| shared-header | 121.58 | 194.83 | 208.39 | 207.49 | 231.36 |
| generated-header | 127.86 | 189.71 | 213.32 | 217.10 | 216.39 |
| unused-header | 8.31 | 8.77 | 177.85 | 180.07 | 198.20 |
| revert | 206.68 | 69.28 | 289.12 | 184.42 | 202.88 |

Clock starts after the editor applies a change and before the build request. Every fast-path sample includes request identity creation, watch-list preparation, a fresh lightweight Odin process, input metadata checks, receipt validation and retained-result loading. A hit launches no producer/LLVM process and performs no link. A miss includes the original stat scan, delta/plan encoding, producer publication, receipt handoff, native compilation/cache/linking and new receipt publication.

The complete admitted namespace and native tools are watched. Missing/corrupt receipts or outputs and changed requests fall back. Output contents are rehashed if their metadata changes; preserved-metadata mutations are outside this stat-visible contract. Inputs must match the preflight stamp again before a receipt can be published after success. LLVM libraries are not linked into the lightweight checker. No daemon or hidden compiler residency is assumed.

Each observation restores independent output/cache/Ninja log state outside timing. Revert starts from an edited build after visiting baseline and edited states. History retains at most three complete records per action, including the latest; this is not a global cache quota. Every candidate still validates framing, checksum, action identity and recorded filesystem observations. Concurrent rotation may lose reuse opportunities, but incomplete/corrupt candidates must miss.

All object identities and libraries match independent CLI references, and runtime probes follow each build. The high-fanout header has 26 independently identified readers. Expected compiler/link counts are checked. Initial SDK admission, graph generation, editor writes, state restoration and parent validation are excluded for all engines. Fixed known namespace, ordinary stat-visible edits, one C target and a warm-cache virtualized Linux host limit generalization. No new-directory, watcher, arbitrary SDK or negative-query extension is claimed.

Tool versions, source/tool identities, native counters and samples are in ignored `results.json`. Reports and compact validation/summary files can be retained in version control.

## What changed

The successful-build gate closes the large unchanged-build gap: 186.03 ms for the journal control versus 7.96 ms for the gate, a 23.4× reduction in the same run. Producer, LLVM and link counts are zero for all seven fast no-ops. Ninja is 8.63 ms, but the fast path wins only 4/7 paired blocks; this establishes similar latency on this fixture, not a dependable advantage over Ninja.

Three validated candidates per action eliminate the revert compilation: history-only takes 184.42 ms versus the journal control's 289.12 ms (36.2% lower medians). The full fast path takes 202.88 ms including its failed gate and new receipt publication; Ninja + ccache remains faster at 69.28 ms. Objects are reused, but the producer, LLVM startup, validation and link still run.

The whole admitted namespace remains the gate's invalidation boundary. An unused-header edit therefore still enters the native pipeline: 198.20 ms for fast versus Ninja's 8.31 ms. Gate and publication overhead also make some changed builds slower; shared-header medians are 231.36 versus 208.39 ms for the journal control. This is a focused no-op/history improvement, not a general incremental-build win.

Absolute timings shifted from the earlier Ninja run. Compare the simultaneously remeasured controls here, rather than subtracting timings across runs. Build-request clocks exclude starting the Python research driver for every engine; the lightweight decision executable is a fresh timed process, not a daemon. Toolchain identity checks and gate preparation remain timed. The checker links only libc and the ELF loader; it does not load LLVM or the C++ runtime.

## Paired fast-path comparisons

Negative differences favor the fast path. Pairs are engine observations within the same randomized block, not simultaneous execution.

| Scenario | Fast − Ninja paired median ms | Fast wins | Fast − journal paired median ms | Fast wins |
| --- | ---: | ---: | ---: | ---: |
| unchanged | -0.74 | 4/7 | -179.48 | 7/7 |
| implementation | +87.21 | 0/7 | +6.17 | 2/7 |
| shared-header | +112.24 | 0/7 | +28.98 | 1/7 |
| generated-header | +90.33 | 0/7 | +5.49 | 3/7 |
| unused-header | +188.93 | 0/7 | +24.60 | 0/7 |
| revert | -12.85 | 4/7 | -96.49 | 7/7 |

## Evidence and reproduction

All 210 timed libraries and 6,510 object identities match independent CLI references. All runtime checks and expected compile/link counts pass. Native tests additionally cover missing/corrupt receipts and outputs, changed requests/membership, input mutation during compilation, exact flags, eviction, concurrent publication and historical negative header lookups.

See [validation](validation.json), [compact statistics](summary.json), [17 correctness tests](correctness-tests.txt), and the [fresh-build instructions](../../README.md#lightweight-build-decisions-and-bounded-history). Full observations in ignored `results.json` are local-only; no download is published. Their SHA-256 is retained in the validation and evidence manifests. The optional-header test does not extend the full-build gate to arbitrary new directory membership: the request explicitly binds the admitted namespace, and the benchmark remains a stat-visible fixed-namespace experiment.
