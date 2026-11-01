# Does the shared compiler work beyond Ninja?

The frozen shared compiler helps three of these four selected build-plus-facts traces, but the backend queue does not improve them consistently. Diagnostic handling and cache working-set limits create large avoidable regressions. The earlier single-project win supports further work on sharing; these workloads identify policies that must improve first.

All **333 operation replays** pass object-byte, dependency-file and complete declaration-digest checks against physical Clang. The trace contains controlled source/header probes and configuration changes; its operation frequencies are artificial. There is no combined speedup across projects.

## Complete controlled traces

Seconds, median [minimum–maximum] across three matched traces. Each trace has nine operations, or ten for re2c. Setup is excluded. The control runs Ninja + ccache and an independent index concurrently.

| Selected target | Units | Shared serial | Shared queue | Ninja + ccache + index |
| --- | ---: | ---: | ---: | ---: |
| xxHash | 7 | 2.553 [2.552–2.568] | 2.500 [2.486–2.524] | 2.848 [2.840–2.852] |
| spdlog | 8 | 39.731 [36.805–40.062] | 35.736 [33.089–35.775] | 44.183 [43.925–49.646] |
| re2c | 66 | 184.422 [177.081–188.607] | 198.038 [196.851–199.778] (fallback) | 165.628 [163.337–210.693] |
| curl | 222 | 110.203 [109.776–111.090] | 137.210 [135.694–138.573] | 124.859 [119.245–127.694] |

The queue executes backend children for xxHash, spdlog and curl. Every re2c request falls back to serial execution under its upstream options; that column is not evidence for or against pipelining. Curl performs real pipelining but its summed queue trace is about 25% slower than shared serial. The small xxHash queue difference is not a strong reason to choose the more complex lifecycle.

The selected header fanouts are 5/7, 8/8, 56/66 and 222/222 units. The admitted closures contain 14, 79, 131 and 443 files respectively. These cover different compilation and invalidation structures, while remaining four deliberately selected C/C++ targets on one laptop.

Full operation medians/ranges are in [the tables](TABLES.md); counts, component clocks, fallback counts and physical-build-only references are in [the summary](summary.json).

## Why the result changes by operation

- spdlog’s unused numeric definition takes **148 ms** shared serial versus **951 ms** in the combined control, while xxHash takes **651 ms** versus **277 ms**. The same reuse rule does not cover both equally.
- A spdlog header comment takes **7.36 s** shared serial versus **4.57 s** in the control. Adding the controlled inline function instead takes **5.72 s** versus **12.21 s**. Preprocessed-input reuse and IR-level reuse catch different classes of equivalence.
- Curl returns to its earlier state in **18.26 s** shared serial, **24.70 s** queued and **9.91 s** in the control. Broad edits exceed the retained history’s entry capacity; pipelining cannot replace missing history.

Every system must produce the same outputs for each probe. The operation mix does not estimate how often developers make these changes. The header function is a declaration/facts change and may leave emitted machine code unchanged. This study does not replay natural upstream commits or establish significance for small timing differences.

## First requests and resource cost

The separate [first-request and resource tables](LIFECYCLE.md) preserve different lifetimes. Fresh shared workers complete the prepared initial graph faster than the combined control on all four targets. For spdlog, medians are **11.62 s serial**, **9.44 s queued**, and **12.60 s control**. For curl they are **17.19 s**, **16.48 s**, and **30.18 s**. These include process creation and source admission, with warm OS caches and generated inputs already prepared. Download, configuration and cold-storage performance are outside this clock.

The resource scenario removes `NDEBUG` after the initial version. On curl, serial and queue peaks are similar—**515 and 508 MiB** aggregate descendant PSS—but CPU rises from **18.72 to 28.97 seconds** with the queue. For spdlog, the queue uses **428 MiB** versus **340 MiB** serial and **393 MiB** in the control. The controller is separate, reaching approximately **42 MiB** for curl. These are single instrumented observations, not hard bounds or peaks over the entire edit trace.

The queue therefore needs ownership/handoff profiling before broader use. The measurements establish additional CPU cost in the curl scenario; they do not isolate how much comes from fork, copy-on-write, compiler state, staging or cache bookkeeping. Startup and edit-session benefits also differ. The sequential priming times in the main matrix are preparation costs, not comparable startup estimates, and no repeated-session break-even is inferred.

The baseline is an AMD Ryzen AI 7 PRO 450 laptop under WSL2 Linux, with 16 available logical CPUs, approximately 11.5 GiB VM RAM and 3 GiB swap. Compiler work uses the declared one/two-worker budgets; CPU affinity and frequency are not fixed. Clang is 22.1.8, CMake 4.1.2, Ninja 1.13.2 and ccache 4.14.1. Timings are descriptive three-observation ranges on this machine.

## Scope and rejected attempts

The [reproduction guide](../../../experiments/integration/generalization/README.md) defines the admitted namespace, source acquisition, controls, operation clocks and output oracles. These are complete selected target builds and controlled invalidation probes, rather than sampled natural development histories. Source trees, compiled hosts and full raw data remain ignored.

xxHash was also used to debug the graph adapter. The frozen reuse algorithm was not changed to fit it. Linker dependencies were initially mistaken for compiler source dependencies; an unrelated test header exceeded the request limit; and the physical facts oracle initially omitted the agreed source root. Those adapter attempts were rejected before the final replay. The other selected targets were not used to tune reuse eligibility or the cache budgets.

The first matrix's CMake launcher insertion also failed: compiler commands contain `${LAUNCHER}${CODE_CHECK}`, so a replacement anchored immediately before the compiler matched nothing. The paths labelled Ninja + ccache in `matrix-v1` actually ran Ninja without ccache. That matrix was stopped and its control comparisons are rejected. The corrected adapter verifies rendered commands, cache calls and stored results; a separate real-CMake test requires a restored identical object and a genuine hit. Only the corrected `matrix-v2` is eligible for the reported comparison. These repairs changed the adapter and control, not native reuse rules or cache limits.

The queue can overlap one backend child with the next frontend. It retains the earlier source, observation, fact and history rules. It requires an explicit drain before source admission, scans and linking. It does not establish thread-safe concurrent use of Clang ASTs, a stable compiler ABI, arbitrary request concurrency, or a production cancellation model. Distinct target outputs are submitted until each drain; competing writes to one target are outside this replay's request contract.

The fixed limits matter to the interpretation: 256 result entries, eight versions per group, 128 MiB counted history payload, and the existing separate IR cache are unchanged. A project can fit its current version while losing older versions during broad edits. Capacity and eviction effects are part of the test, rather than reasons to silently raise the limits.

This is a build-plus-declaration-facts comparison. The control runs Ninja + ccache alongside a separate cached frontend, using the same fact extractor and reuse policy. It is not a comparison against a complete editor such as clangd, and a build-only Ninja invocation performs less work. The raw rows retain the physical build-only clock separately. The fact consumer still uses the earlier summary/`gaia_` prefix probe; widening source projects does not establish general editor-query or index-transfer performance.

re2c exposes a policy failure before any lower-level tuning: its first shared serial no-op reconsiders 38 of 66 units, all 38 emit diagnostics, and none hits the IR cache. The operation takes 20.80 seconds, with reported frontend and backend phases summing to approximately 11.43 and 7.45 seconds respectively. The existing observation cache deliberately excludes results that emitted diagnostics, while the initial full working set exceeds the separate IR cache's entry limit. Avoiding diagnostic reuse has a serious performance cost here. The queue's admitted argument subset also rejects the upstream options and records serial fallbacks; those rows cannot demonstrate pipelining gains.

The first startup export also stopped because its validator removed reference fields before checking every result in the reversed order. No object mismatch was reported. That attempt is excluded; the repaired validator checks all outputs before stripping evidence fields. A complete three-order xxHash pilot passed before the accepted `startup-v2` measurement. The resource sampler is separately tested against a subprocess created by a pool thread so that the physical compiler subtree cannot silently disappear from its accounting.

## Next concrete work

1. **Retain diagnostics with their validated result.** Start with exact command/input matches, current diagnostic locations and explicit failure cases. Removing repeated frontend/backend work from an unchanged repository has a much larger opportunity than another scan kernel. Preserve the frozen-policy results as the baseline.
2. **Make cache admission fit the working set under a byte budget.** Measure current versus historical results, IR-cache admission and disk-backed immutable objects. Use these same traces plus a longer natural edit history; avoid raising a count until this corpus happens to fit.
3. **Separate object reuse from facts freshness earlier.** The header-comment and inline-function results show that preprocessed-input and IR equivalence catch different work. Measure a generic reuse gate before expensive lowering, alongside unchanged object publication and link avoidance, while retaining full physical oracles.
4. **Profile native module ownership and test a real consumer.** Attribute the queue’s extra CPU before replacing fork with another transfer model. Add natural upstream patches and an editor/analyzer workload with varied queries; the fixed-prefix fact probe remains a limitation even after adding projects.

The [validation record](validation.json), [provenance](provenance.json) and [raw identities](raw-identity.json) distinguish accepted measurements, rejected attempts, source pins and locally available evidence. No reuse rule or cache constant was tuned to these projects during the accepted matrix.

The compiler study passes **26 regression tests**, the complete **333/36/12** edit/first-request/resource comparisons, its recorded evidence hashes, and a source-only checkout without retained tools or observations. The [repository checker](../../../tools/check_repository.py) verifies the consolidated evidence manifest. New and modified files have no trailing whitespace; existing text fixtures are preserved. Raw observations and rejected attempts remain ignored, with their identities recorded for local inspection.
