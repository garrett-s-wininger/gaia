# A geometric embedding helps lexical layout but loses to simpler clustering

The input is an actual Django dependency payload represented as 437 chunks, with 1,629 weighted co-access edges from training only. The native Odin kernel builds bounded force layouts in one and three dimensions; one coordinate sort or a Morton order converts the layout to fixed eight-chunk groups. The test is logical placement, not physical 3D hardware geometry. [Summary](summary.json), [provenance](provenance.json), [validation](validation.json), [raw identity](raw-identity.json), ignored [observations](results.json), [reproduction](../../README.md).

The force rule combines weighted attraction, pairwise repulsion, capped updates and centering for 80 iterations. One deterministic seed is used. No parameter search or global optimum is claimed. Lexical and weighted BFS are conventional controls.

| Ordering | Construction CPU | Held-out whole-group-cache read bytes |
| --- | ---: | ---: |
| Lexical | 0.014 ms | 164,659,514 |
| Weighted BFS | 3.57 ms | 126,583,726 |
| Force 1D | 38.05 ms | 148,177,524 |
| Force 3D + Morton | 62.19 ms | 143,836,235 |

Construction includes edge-matrix allocation, initialization, native iterations and ordering. It is a single construction observation per method. The local cache model uses whole eight-chunk groups as LRU entries with an 8 MiB payload budget; these read bytes are modeled, not measured storage throughput. The independent fresh-start held-out trace has the same access pattern for this application, so it is not evidence of generalization to an unseen workload. Reverse order is an explicitly synthetic stress case.

The geometry candidates improve modeled lexical access but both cost more and read more than weighted BFS. Three dimensions do not establish a superior representation in this fixture.

## Common actual-reader comparison

The data lane separately evaluates these exact permutations through its verified physical group reader with per-chunk LRU. Its cache semantics differ from the whole-group model, so its counts must remain separate. All layouts repack the full 28,590,237-byte payload and charge their construction/repacking before useful reads.

The common reader's held-out counts are lexical 167,280,954 bytes / 320 group reads, BFS 132,350,894 / 253, force 1D 158,090,001 / 302, and force 3D 150,602,984 / 288. These are the final demanded-MRU-after-prefetch results. A simple static greedy training cluster reaches 92,651,991 bytes / 177 reads. Requested content and each loaded chunk's SHA-256 are verified. The geometry candidates again lose to both simpler alternatives; a geometry visualization would not change that result.

The parent data study owns those actual-reader observations and its full readiness/repacking timing. This report owns the frozen geometry construction, permutations and local model only. A future improvement needs new held-out workloads, equal tuning budgets and complete consumer benefit after maintenance—not merely a better layout score.
