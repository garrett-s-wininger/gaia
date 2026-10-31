# What the broader sharing experiments established

The first passes cover each proposed research question with a bounded prototype or diagnostic. They do not complete the production components behind those questions. Sharing can remove CPU work while leaving wall time unchanged, and an existing combined API is often a stronger baseline than several independent commands.

## Compiler and workspace work

| Question | Evidence | Result and boundary |
| --- | --- | --- |
| Continue current IR instead of reparsing on a miss | [IR continuation](../../experiments/compiler/followthrough/results/ir/REPORT.md) | Heavy unused-type edit 75.62 ms versus seeded ccache 3,710.98 ms; unchanged/comment paths still favor ccache. Current diagnostics/dependencies remain live. |
| Extend shared inputs to a production graph | [Ninja graph](../../experiments/compiler/followthrough/results/graph/REPORT.md) | 33 real TUs; source and generated-input edits win 3/3 pairs against matched single-worker Ninja + ccache. Scheduling uses fixed baseline dependencies, not a sound generic dynamic graph. |
| Share editor/build knowledge | [Generation interaction](../../experiments/compiler/followthrough/results/graph/REPORT.md) | Inspection and compilation consume the same admitted unsaved bytes; stale requests fail. This is not a full editor/diagnostics loop. |
| Identify hidden invocation inputs | [Reproducibility probes](../../experiments/compiler/followthrough/results/reproducibility/REPORT.md) | Paths, environment, timestamps and archive order matter. Six small probes do not establish hermetic production builds. |
| Share parsing and run independent analysis alongside compilation | [Parallel controls](../../experiments/compiler/followthrough/results/analysis-parallel/REPORT.md) | Small-TU sampled CPU roughly halves, but shared parsing barely changes latency against two parallel workers. Analysis uses detached names, not an arbitrary linter or shared mutable AST. |

## Data and retained lifetimes

| Question | Evidence | Result and boundary |
| --- | --- | --- |
| Admit only useful dependency bytes while a consumer runs | [Django admission](../../experiments/artifacts/followthrough/results/admission-frozen/REPORT.md) | Verified chunk granularity trades bytes against calls. Actual code executes before the last fetch; asynchronous network/CPU overlap and physical disk behavior remain unmeasured. |
| Keep a growing cache correct through eviction and failure | [Cache lifecycle](../../experiments/artifacts/followthrough/results/lifecycle/REPORT.md) | 3,931 real objects and publication/corruption probes pass. Reopening the packed index is much costlier than one lookup through an open store. Owned byte views do not prove mapped-reader leases. |
| Consume one structured representation across runtimes | [Fused catalogue](../../experiments/artifacts/followthrough/results/catalogue-fused/REPORT.md) | Python JSON 4.791 ms versus direct Python 2.356 ms; borrowed Odin 0.396 ms. Node also improves. These are bounded read/verify/query operations, not complete starts or physical page sharing. |
| Budget retained compiler, workspace and artifact data together | [Compound retention](../java/followthrough.md#mixed-retention-exercises-admission-and-cache-eviction-not-os-pressure) | Actual chunk-cache pressure and sampled aggregate admission are exercised. The soft gate permits overshoot; no strict resident quota, shared allocator or OS memory-pressure result. |
| Extend compiler lifetimes and native optimization controls | [JVM follow-up](../java/followthrough.md) | Shared JVM traces complete more work before the sampled gate stops admission. Native O3/user-profile improves first compilation and size; sustained gains over O3/inferred profiles are small and noisy. |
| Precompute runtime-image discovery | [Groovy index](../java/followthrough.md#prepared-discovery-helps-lookup-without-a-complete-command-win) | Isolated import queries improve 625 to 481 ms; complete command startup does not. Dynamic behavior remains tested. |

## Work beyond compilation

| Question | Evidence | Result and boundary |
| --- | --- | --- |
| Prepare isolated test environments once | [SQLite fixtures](../testing/findings.md#prepared-sqlite-fixtures-remove-repeated-schema-work) | Sixteen-test sessions fall from 355.5 ms to 24.5–27.4 ms with charged preparation/teardown. Generated SQLite fixture; rollback cannot isolate commits/external effects. |
| Share discovered tests across consumers | [JUnit discovery](../testing/findings.md#junit-already-supports-sharing-a-discovered-plan) | Shared plan improves redundant discovery, but the existing direct API is faster and does less consumer work. Dynamic tests cannot all be pre-sharded. |
| Run repository predicates together | [Query controls](../../experiments/workflows/results/combined-control/REPORT.md#repository-queries-need-a-strong-combined-control) | Combined ripgrep 17.06 ms versus parallel independent ripgrep 43.87 ms; first fused Odin scanner loses. Existing algorithm quality matters. |
| Interpret schemas once for several products | [Reviewed fixture](../../experiments/workflows/results/reviewed/REPORT.md), [production protoc control](../../experiments/workflows/results/protoc-guarded/REPORT.md) | Shared synthetic model saves work. Unmodified parallel protoc beats its combined invocation; descriptor handoff fails exact outputs for one case because implicit/explicit metadata changes. |
| Stop propagation at unchanged intermediate outputs | [Reviewed propagation](../../experiments/workflows/results/reviewed/REPORT.md#one-interpretation-still-removes-repeated-work) | Reorder/description edits avoid downstream work; field-type edits do not. Fixed implementation/configuration context, not a general incremental engine. |
| Start native source-control persistence | [Checkpoint probe](../../experiments/workflows/results/reviewed/REPORT.md#native-persistence-remains-a-structural-probe) | Odin typed immutable objects, authenticated historical reads and publication failpoints work. Discovery/ignores/symlinks/stacks/restore/automatic recovery remain absent; the local-engine milestone is not complete. |

## Where the evidence points

The strongest next integration is a shared immutable input/fact boundary with independent consumers, explicit ownership and sound invalidation. Keep exact-input result lookup ahead of expensive semantic work, preserve parallel generation, and stop downstream propagation only when its full context permits it.

Useful follow-ups now need production consumers and lifecycle guarantees: integrate dynamic/negative dependency observations into the real graph, exercise real test suites, preserve explicit/default/source metadata in any parsed representation, and separate logical cache budgets from enforced process limits. More isolated encodings or sequential-only baselines would answer less.
