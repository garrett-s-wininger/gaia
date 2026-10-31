# Actual pack reads favor simple clustering over the first force/local-decay policies

Input comes from two actual fresh Django consumer traces: 560 training and 560 held-out 64 KiB chunk access events, 437 payload chunks and 1,629 training-only co-access edges. Another held-out phase reverses requests synthetically. The two original consumers repeat the same workload, so the split does not establish unseen-project generalization. Input reconstruction from the pinned earlier trace is byte-identical.

Each policy creates a complete 28,590,237-byte pack with its own ordering. Actual warm file reads verify every fetched chunk before cache visibility. The per-chunk cache retains at most 8 MiB; a demanded chunk becomes most recent after prefetched siblings. Existing producer payload and Python metadata are outside that logical reader budget; transient group buffers are reported separately. No RSS quota, storage-device stress or active mapped-reader lease is established.

| Held-out policy | Warm read/verify median | Read bytes | Calls | Policy + repack |
| --- | ---: | ---: | ---: | ---: |
| Physical contiguous groups of 8 | 189.80 ms | 167,280,954 | 320 | 23.85 ms |
| Static greedy co-access groups | 121.03 ms | 92,651,991 | 177 | 90.46 ms |
| Local reinforcement/decay | 178.56 ms | 135,823,674 | 260 | 132.98 ms |
| Individual chunks, cost/size retention | 73.08 ms | 27,672,733 | 423 | 40.66 ms |
| BFS groups from parallel graph study | 182.00 ms | 132,350,894 | 253 | 24.53 ms |
| Native 1D force groups | 200.00 ms | 158,090,001 | 302 | 62.98 ms |
| Native 3D force groups | 178.52 ms | 150,602,984 | 288 | 97.19 ms |

All 48 operations return the same ordered content digest and respect the logical cache bound. Force layout improves lexical read counts while losing BFS and static greedy clustering. Reinforcement also loses the simpler static candidate. Individual chunks reduce bytes but increase calls; modeled call latency can change that tradeoff. The separate 1 ms/call+16 MiB/s prediction is explicitly a service-cost model, not measured device time.

The graph study supplies frozen native construction/permutation identities from training only; its construction time is included here. Its group-cache model has different replacement semantics, so its byte totals must not be merged with this per-chunk evaluator. All orders are checked as full permutations tied to the exact input hash. Policy/repacking cost and full producer/index/trace acquisition remain distinct. Original Django trace collection is prior research, not included as a free complete workflow speedup.

The first developer-only cache variant did not promote a demanded chunk after prefetch; it remains ignored exploratory data. This report and source pins refer to the corrected frozen rerun. Placement is not automatically an improvement after maintenance/amortization, and no biologically faithful slime-mould optimizer is claimed: reinforcement/decay is a small inspired heuristic.

[Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), [reproduce](../../README.md).
