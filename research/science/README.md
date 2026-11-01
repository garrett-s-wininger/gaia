# Sharing, transformations and heterogeneous computation

This round asks whether changing the unit of work yields more than changing its implementation language: preserve observations, share immutable inputs, reconcile sets, reorder physical data, cancel obsolete work, and overlap independent analyses. Geometry and adaptive policies are candidates with explicit controls, rather than assumed improvements.

The studies run on one developer laptop. Compare numbers within each experiment; they cannot be added into a combined speedup. Timing locks serialize cooperating measurement cases, but preparation and unrelated host activity can overlap. Small differences and three-block measurements do not establish reliable superiority.

| Research boundary | Implemented evidence | What it suggests |
| --- | --- | --- |
| Sets and information | [Exact inventories, Merkle traversal and IBLT](data/README.md) | At low churn, 608 bytes replace 251,632 bytes, but cold Python construction/verification costs 31.8 rather than 3.9 ms. |
| Patches and convergence | [Contextual operations, joins and publication](graphs/README.md) | Small algebraic laws can be checked against snapshots. Converging facts still require coordination for authoritative publication. |
| Changing observations | [Graph models and actual Clang VFS](graphs/README.md) | A three-TU trace improves from 261 to 116 ms with matching objects and depfiles, including refreshed observations after IR reuse. |
| Queueing and feedback | [Real loopback delivery](data/README.md) and [scheduling models](graphs/README.md) | Competent fixed batching beats the tested feedback controller; canceling obsolete work matters more than the modeled queue-policy differences. |
| Geometry and forces | [Native embeddings](graphs/README.md), [actual pack reads](data/README.md) | 3D placement improves lexical order, but static clustering reads 92.7 MB versus 150.6 MB for 3D. Logical distance is not physical hardware placement. |
| Retention and adaptation | [Leased graph pebbles](graphs/README.md), [bounded search and reinforcement](data/README.md) | Include scratch, construction and training costs. Nature-inspired policies do not beat the ordinary controls here. |
| Shared compiler inputs | [Sealed generations and private workers](compiler/README.md) | Four workers share read-only source bytes: sampled worker PSS falls from 94.2 to 59.9 MiB; this is not a total-memory quota. |
| Compiler-pass overlap | [Real LLVM analyses and speculative backends](compiler/README.md) | Output/fact equality holds on the tested units. Fork and discarded-work costs usually outweigh overlap. |
| Actual application work | [Assets, native reload, workspaces, editor and doctests](workflows/README.md) | Shared preparation and safe cancellation help; mature batching remains a strong baseline. |
| Other compute devices | [Capability boundaries](../../experiments/science/devices/README.md) and [actual GPU execution](workflows/README.md) | D3D12 execution works; the tested one-step frontier loses to native CSR through 8.4 million edges. |

The [coverage map](coverage.md) distinguishes executed consumers from simulations and bounded laws. The [follow-up priorities](prospects.md) identify which mathematical directions deserve another experiment. Per-track run indexes link committed summaries, validation and provenance to ignored raw observations registered in the [evidence manifest](../evidence.json). These are research interfaces, not public protocol decisions.

The [first concrete integration](../integration/README.md) now measures shared compiler/editor observations, native SIMD sets and CPU-dispatched identity scans.

The broader integration target remains a real multi-consumer workflow sharing one authoritative generation and current dependency observations. Keep exact-input caches, batching and sparse CPU algorithms as controls. Require gains in the complete operation, including preparation, validation, retained memory, cancellation and publication.

For accelerators, a distinct next question is repeated computation on device-resident state: iterative graph/geometry work or heavier independent analyses, compared with equally optimized native algorithms. The one-step frontier result supplies no general accelerator limit. Compiler parallelism likewise needs declared dependencies and invalidation between passes; separate independent analyses are a safer starting point than concurrent mutation of shared IR.
