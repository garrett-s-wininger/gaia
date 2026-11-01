# Current source, historical test evidence and real fix replays

The prototype connects current source inspection to native test-execution evidence without changing testmon's selector. It correctly distinguishes historical observations from current source and rejects stale publication. The experiment also exposes an important limit: reduced test counts do not necessarily make a complete validation workflow faster when dependency collection is expensive.

**This is a scripted mechanical replay, not a measured human/agent productivity improvement.** Known upstream patches and predetermined inspection locations drive the requests. Discovery ranking, reasoning time and time to invent a correct fix remain unmeasured. The runnable interface and task cases provide a concrete basis for that next evaluation.

## Measured workflows

| Historical task | Full-suite workflow | Native testmon workflow | Shared-evidence workflow | Shared overhead vs native, paired median |
| --- | ---: | ---: | ---: | ---: |
| Integer filter | 12.200 s | 9.687 s | 10.950 s | +10.79% |
| Async overlay | 12.294 s | 21.531 s | 23.060 s | +3.77% |
| Namespace tuple | 12.614 s | 22.146 s | 25.103 s | +13.35% |

Values are medians of complete six-step traces. Native testmon wins the narrow integer-filter workflow but loses the broader overlay and namespace workflows in all three paired blocks. The source fix executes 14 tests for the integer case, 833 for overlay and 818 for namespace, versus 877, 903 and 907 in the corresponding full suites. Both native and shared testmon execute zero tests on the unchanged step.

The timing ranges include large outliers: integer full-suite traces span 11.994–38.208 s, overlay full-suite traces 12.175–21.221 s, and shared namespace traces 24.132–33.672 s. These are retained, not discarded. Shared overhead is positive in all nine matched comparisons, but precise percentages should not be generalized from this small, noisy sample. [Full ranges and counts](summary.json).

The strong native testmon comparison measures the overhead of adding a new evidence capability. It is not an equal-feature discovery comparison: full-suite and native controls perform the same literal search and structural inspection, while the shared path additionally exports, joins and persists execution observations. Any saving from test selection belongs to testmon, not Gaia's view.

The median shared query batch costs 31.4 ms for integer conversion, 31.7 ms for overlay and 71.7 ms for namespace, compared with 29.8, 30.3 and 63.1 ms for native controls. A batch includes literal search and all task inspections; it runs before and after validation and excludes CLI startup/loading a saved store. The first-block persisted evidence stores occupy 7.0, 22.0 and 22.3 MB. Total shared state, including duplicate per-run exports, logs and native caches, has median sizes of 15.1, 45.2 and 46.0 MB, versus 1.6, 2.8 and 3.0 MB for native testmon. These are file sizes, not resident memory. Child-process high-water RSS is retained but does not establish incremental or total workflow memory cost; controller memory and launch-time inherited memory are not separated. [Derived metrics and scope](analysis.json).

Each complete trace includes private source checkout, initial test/collector preparation, adding regression tests, source fixes/reversions, current-source hashing, search/inspection before and after validation, subprocess startup/exit, and persistence of shared history. It excludes dependency acquisition, shared harness startup/context admission, independent oracle runs, boundary diagnostics, raw observation serialization and final scratch-workspace cleanup. Both initial and subsequent operation costs are reported; a cheap unchanged request cannot hide the preparation cost.

Three randomized blocks run each of three tasks in all three modes. The cooperative lock excludes participating timing experiments, not all host load. These small-sample ranges are descriptive; no confidence interval or general developer-productivity speedup is claimed.

## The historical tasks

| Task | Pinned upstream change | Validation issue |
| --- | --- | --- |
| Scientific-notation integer filter | `3ef3ba885bc7a465b022abfd525d6bb4a1c8dd3c` | Very large scientific notation raises OverflowError instead of returning the filter's default |
| Async environment overlay | `b4b28ec01c60b8753ab53fe60b10d7dbaa55842b` | Omitting `enable_async` should inherit the parent's async mode |
| Namespace tuple assignment | `fbc3a696c729d177340cc089531de7e2e5b6f065` | Tuple assignment to namespace attributes requires parser and compiler changes |

These are a purposive sample of three different changes in one project, not representative edit frequencies. Each starts at the actual first parent. The initial collector sees only that source and its existing tests. The controller later installs the upstream test changes and then the source changes. The replay inspects `do_int`, `Environment.overlay`, `Parser.parse_assign_target` and `CodeGenerator.visit_Assign`; these locations were chosen with knowledge of the fixes, so their retrieval is not a blind localization result. [Task specification](../../tasks.json), [acquisition](../../acquisition.json).

The overlay case has a useful negative control. Its added upstream test passes on the unfixed source. The minimal reproduction in the original PR—an async environment calling `overlay()` without an explicit async argument—fails before and passes after the source fix. The replay includes that additional assertion and preserves both outcomes. A source-to-test association plus green tests would otherwise leave this bug unverified. [Original reproduction](https://github.com/pallets/jinja/pull/2061).

All three traces proceed through initial state, new regression, fix, unchanged rerun, source reversion and source restoration. Reversion retains the regression tests, which must fail again. The unchanged testmon request may execute zero tests; the interface retains the origin of previous observations rather than claiming new execution.

## What the interface adds

The native collector already knows which source lines execute while each test context is active. A read-only wrapper at `TestmonData.get_tests_fingerprints` supplies that information to a second consumer after obtaining the native fingerprint result. Native input/result objects and selection policy are preserved. Python's AST maps lines into innermost named function-body spans; the resulting relation is structural execution evidence, not a resolved call graph. [Implementation](../../observer.py), [Coverage contexts](https://coverage.readthedocs.io/en/latest/contexts.html).

The inspection API returns current source text/ranges, matching observed tests, their recorded outcomes and originating generations. It explicitly reports historical observations, unchanged-function-AST information, coverage limitations and truncation. Literal source/test search uses ripgrep. Default responses show at most 20 execution links and 30 search matches, with total counts. A lexical focus term can prioritize matching test names; this is not a learned retrieval model or a demonstrated task-ranking improvement.

The initial evidence contains only 13 observed test/function pairs for the integer-filter query, one for the overlay query, and 311 across the two namespace queries. The complete export contains about 100,000 pairs per baseline. That disparity is a reason to evaluate how much history users actually need before adopting an eager retained graph. The current prototype stores a bounded six-step history by construction, without a general retention policy.

Source/configuration identities hash admitted source files, tests/resources, test configuration and a declared tool environment. After edits, prior execution links remain explicitly historical; their old coordinates cannot replace current source anchors. Publication checks reject a result for an old source/configuration identity. A changed function AST is recorded separately; unchanged AST alone is not a validation proof.

## Correctness and compatibility evidence

All **162 validation runs** across 27 traces produce the expected failure sets. They execute **95,802 test cases**, including **54 expected failures** when regressions run against unfixed or reverted source. Native and shared paths execute identical test sets with identical outcomes at every matched stage; the full suite independently agrees on the failures. All nine shared traces pass the six source/publication boundary checks. [Validation record](validation.json).

An independent full pytest-cov run checks initial observations. **All 325 relationships for the replay's queried functions match.** Across the complete graphs, the independent runs differ on five test/function pairs out of approximately 304,000 observations. The differences involve `Template.generate` and the weak-reference callback lexically inside `ModuleLoader.__init__`, consistent with delayed cleanup being attributed to the test active when it executes. This is a limitation of treating execution contexts as causal relationships, not evidence that missing links imply no dependency. All differences remain in [oracle-validation.json](oracle-validation.json); whole-graph equality is explicitly false.

Each shared replay checks line insertion/remapping, historical labels after edits, rejection of old query generations and late results, incomplete-source handling and changed configuration. Focused tests cover nested lexical containment, changed bodies, absent/renamed definitions, path admission and the compatibility repair.

The standard environment needed three explicit accommodations. Coverage 7.17.0's `sysmon` core does not support the dynamic contexts used by testmon, so every path receives `COVERAGE_CORE=ctrace`. Pytest's cache plugin remains enabled because testmon expects its `lf` option. Finally, pytest-testmon 2.2.0 crashes on Jinja's extensionless traced template `tests/res/templates2/foo`; a one-line patch uses its existing whole-file non-Python treatment for such inputs. Both testmon controls receive the same repair. The ordinary full suite passes without changing upstream test bodies. [Compatibility record](../../compatibility.json), [patch](../../testmon_compat.patch).

The producer uses a pinned internal method, not a promised public upstream export API. Source/fixture generations are controller owned and serialized. No general filesystem watching, external-service tracking, concurrent edit transaction, unsaved-buffer service or security sandbox is implemented. A matching generation identifies the declared source/configuration context; it does not prove deterministic tests or complete behavioral coverage.

## Decision for Gaia

This establishes a usable source/evidence publication boundary over existing native knowledge. It does **not** establish that a new test-selection engine, a universal fact store or an additional runtime improves development productivity. The strong native control captures test-selection savings already; the shared view must earn its added collection/export/retention cost through useful investigation and safer interpretation of results.

The next decisive evaluation is a held-out developer/agent task comparison with equal tools and budgets, independent correctness grading and both initial preparation and investigation time included. Until then, the supported conclusion is narrower: this interface can expose qualified source/test evidence, ordinary native validation can already be fast, broad dependency collection can be a net loss, and a green related test can fail to check the reported bug.

Evidence: [summary](summary.json), [validation](validation.json), [oracle comparison](oracle-validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), [ignored observations](results.json), [live CLI response from the retained overlay workspace](example.json), [reproduction and CLI](../../README.md). Raw observations and retained runnable workspaces remain local; no download service has been published.
