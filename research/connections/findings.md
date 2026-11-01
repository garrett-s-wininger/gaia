# What the cross-field experiments established

Retaining useful native work is more promising than eagerly building another representation of it. The measured gains come from avoiding parsing and broad invalidation; additional proof graphs, compact intermediates and forked execution state have to repay their own construction, maintenance and ownership costs.

These are separate experiments with different inputs and clocks. Their percentages cannot be added into a platform speedup. The [run index](experiments.json) identifies reports, validation, acquisition and raw identities. The [connection map](connections.md) and [reading routes](sources.md) supply hypotheses and background rather than measured Gaia improvements.

| Question | Observed result | Evidence and boundary |
| --- | --- | --- |
| Can a different liveness formulation beat native LLVM traversal? | The alternative kernels lose after conversion and production costs. | [Pass formulations](pass-experiments.md); genuine upstream LLVM IR, with the initial unused-name extraction mistake separated from the corrected result. |
| Do compact shared facts help multiple consumers? | Traversal can improve, but producing and maintaining the extra representation loses against LLVM use lists with equal caching. | [Retained facts](retained-facts.md); producer, invalidation and consumer costs remain separate. |
| Can cheaper backend work improve a real edit-to-test loop? | The tested machine-pass policy cuts compilation by 17–20% against `-O2`; stock development settings win the complete tested operations. | [Backend policy](backend-policy.md); actual Zstandard algorithm edits, equivalent exercised outputs and explicit runtime/size tradeoffs. |
| Can derived source analyses be maintained from changes? | Retained native parsing and cached consumers cut the tested trace by 57%; the extra shortest-proof engine adds no established overall benefit. | [Source deltas](delta-analysis.md); Django imports, current navigation and an unmodified Import Linter contract. |
| Can namespace changes avoid full rescans? | Indexing observed names and absences cuts the tested trace by 42% against full rescans. Complete retained references add no established gain over scoped native parsing. | [Namespace rebinding](import-rebinding.md); validate resolution and source lines against a fresh native graph. |
| Can initialized execution state provide faster isolated tests? | Forked requests preserve heap isolation but add no robust gain over native database reuse. Warm reuse is faster under a narrower state contract and leaks the deliberately tested successful mutation. | [Branched tests](branched-tests.md); real django-todo test bodies, private SQLite/media state, interruption and source/settings invalidation. |
| Can source discovery reuse native validation evidence? | The added view preserves native test selection/outcomes and rejects stale evidence, at roughly 4–13% overhead over native testmon. | [Discovery and validation](discovery-validation.md); three historical Jinja fixes. Human/agent task-completion benefits remain unmeasured. |

## How this connects to the compiler integration

The [four-project compiler comparison](../integration/generalization/README.md) finds the same need to distinguish data validity from execution policy. Diagnostic exclusion makes unchanged files expensive, bounded history displaces useful versions, and a backend queue can add CPU despite useful first-request overlap. Those findings complement namespace-scoped invalidation and generation-qualified test observations; they do not establish one universal graph, runtime or cache policy.

The common contract is worth pursuing: retain the native producer's facts, identify the source/configuration/namespace that makes an answer current, and expose ownership and completion to consumers. Compare every extra maintained view against an equally cached native path. Source search, structural navigation, diagnostics and recorded test outcomes remain different kinds of evidence.

## Limits to carry forward

The source-analysis traces are designed edits over real code, and the test-evidence replay applies already known fixes. They are not natural edit-frequency samples or blind bug-fixing studies. Execution observations do not prove complete test impact or semantic equivalence. The native compiler studies validate their stated object/IR/runtime outputs, rather than arbitrary tool internals. No public protocol, production service or general POSIX replacement is selected by these results.
