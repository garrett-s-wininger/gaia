# Which mathematical directions deserve another experiment

Prioritize mechanisms that remove repeated work across real consumers. The [findings overview](README.md) and [coverage map](coverage.md) distinguish executed measurements from checked laws and simulations. None establishes a production protocol or a universal performance limit.

| Priority | Direction and evidence | Next bounded experiment | What would justify continuing |
| --- | --- | --- | --- |
| First | Incremental observations: the actual small Clang trace falls from 261 to 116 ms with matching objects and refreshed dependency facts. | Integrate current positive/negative observations into the existing production build graph, then share a generation with an editor or test consumer. | Correct invalidation and lower complete-operation cost against matched caches, including observation construction and updates. |
| Next | Set reconciliation: 608 bytes replace a 251,632-byte inventory, but cold sketch construction costs more CPU. | Maintain summaries across updates and perform actual synchronization; compare full hash batches, incremental Merkle summaries and sketches. | Lower complete synchronization cost after updates, exact verification and underestimated-sketch fallback. |
| Next | Dependency-aware retention: a tiny pebbling model exposes downstream recomputation missed by immediate cost/size heuristics. | Replay actual compiler/analysis requests under a declared payload budget; compare recency, dependency-aware retention and a small offline oracle. | Less executed work without worse useful latency or excessive coordination; measure scratch and whole-process memory separately. |
| Architectural | Patch algebra and information lattices: supported contextual operations and joins satisfy their finite oracles. | Classify independent workspace operations, retain conflicting facts and publish through an explicit expected-generation boundary. | Less unnecessary coordination under equivalent snapshot/publication semantics; no claim of semantic independence from disjoint paths alone. |

Queueing remains useful for batching, canceling obsolete work and preserving fairness. The first feedback controller loses to competent fixed batching. Test adaptation only where an actual changing workload makes a fixed policy inadequate, and charge observation and control costs.

Force layouts, reinforcement and bounded evolutionary search do not yet justify replacing cheaper controls. Preserve static clustering, BFS, single-chunk retention, grid and random search. A different application or changing hot set would supply new evidence; another fresh process of the same application does not establish broad generalization.

GPU dispatch is verified, but native sparse traversal wins the tested one-step frontier through 8.4 million edges. A separate accelerator question is heavier repeated computation with device-resident state. Compare equally optimized CPU algorithms and charge initialization, transfers, synchronization and retained resources. Other devices require successful capability and execution checks.

Real LLVM analysis overlap is correct in the bounded private-snapshot contract, without a robust speedup. Broader speculation is a lower priority: first identify an expensive guarded operation where overlap can exceed fork/coordination and discarded-work costs. Arbitrary optimizer passes need explicit dependency, mutation and invalidation contracts.

Track-specific details: [graphs and observations](graphs/README.md), [sets and data policies](data/prospects.md), [compiler lifetimes and passes](compiler/prospects.md), and [actual workflow consumers](workflows/prospects.md).
