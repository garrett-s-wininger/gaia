# Compact facts lose to the cached native control in this trace

Producing an extra compact def-use graph alongside liveness did not recover its cost in the tested sequence of parameter queries and IR edits. Building that graph only on demand reduced the penalty. LLVM's existing use lists, with the same function-level invalidation and result caches, were the strongest complete-request control.

These are sums of ten measured request spans on already resident LLVM IR, including declared edits and analysis/query work. They are not compiler build times or uninterrupted interactive-session latencies. Values are medians in milliseconds across seven blocks with shuffled policy order.

| Input | Functions | Native cached | Compact eager | Eager paired wins | Compact lazy | Lazy paired wins |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Zstandard common | 6 | 0.01390 | 0.01704 | 2/7 | 0.01753 | 1/7 |
| Zstandard lazy compression | 89 | 11.67947 | 16.17140 | 0/7 | 11.99953 | 1/7 |
| zlib deflate | 26 | 1.90793 | 2.49290 | 0/7 | 2.23004 | 0/7 |

Eager materialization increased the median sum by 38.5% on Zstandard lazy compression and 30.7% on zlib. Lazy materialization increased it by 2.7% and 16.9%, respectively. The small common module is an overhead control; its microsecond durations and mixed paired outcomes do not support a strong ranking. The 2.7% Zstandard lazy-policy difference is also modest and should not be generalized beyond this run.

## Where compact traversal helped

The exploration event asks previously unseen parameter queries after initial liveness. Eager production has already built all graphs by then. Its query phase is faster, but its initial liveness phase paid to build those graphs.

| Input | Initial complete request, native / eager / lazy | Exploration query phase, native / eager / lazy |
| --- | ---: | ---: |
| Zstandard lazy compression | 4.98566 / 7.23580 / 5.05935 ms | 0.34345 / 0.20655 / 0.39184 ms |
| zlib deflate | 0.56308 / 0.84139 / 0.61612 ms | 0.08918 / 0.05785 / 0.12768 ms |

The prepared CSR makes new slice traversal cheaper here. Its creation and invalidation cost outweigh that saving in the complete trace. A repeated identical query cannot keep amortizing traversal setup: all policies retain the final result and stop traversing. An opportunity for CSR would therefore need enough **distinct** demanded queries before invalidation, or a consumer boundary that makes LLVM's existing representation unavailable. Neither is established by this experiment.

## Work and retention

All policies perform exactly 182 liveness productions/solves and 46 slice misses per Zstandard lazy trace, and 56 productions/solves and 19 slice misses per zlib trace. Eager graphs are built 182 and 56 times, respectively; lazy graphs only ten times per trace. Native builds no extra graph. Unchanged events do zero production, zero solving and zero slice traversal in every policy. Function additions and edits invalidate exactly the intended scope; only explicit context refresh invalidates the whole module.

| Input | Peak logical payload: native | Eager | Lazy |
| --- | ---: | ---: | ---: |
| Zstandard common | 992 B | 1,208 B | 1,168 B |
| Zstandard lazy compression | 1,569,364 B | 1,936,568 B | 1,593,852 B |
| zlib deflate | 190,220 B | 234,692 B | 209,652 B |

These are logical retained element bytes, not RSS. They exclude LLVM IR, allocator/container overhead, spare capacity, transient production/scratch and the test's extra held historical result. All policies keep LLVM resident. This does not measure a compact service that can discard IR.

## Evidence and limits

All 630 measured real-IR responses and 30 fixture-trace responses matched independent liveness and slice oracles exactly. Twenty-four hand-checked slice results passed, as did four prior native-kernel/extraction tests. Stale generations and invalid arguments were rejected; old result vectors remained immutable. LLVM verification ran after every edit. Source, SDK identity, binary and IR pins were verified after execution.

The data-use query excludes alias, control and interprocedural effects. It is a syntactic navigation primitive, not full program-impact analysis. The ten-event demand trace and edits are constructed, not captured user behavior. Context refresh is a declared synthetic event. No GPU, NPU, OS mechanism, source compiler round trip, production language server or frontend fact-emission hook was exercised.

Cloning, initial parsing, oracle generation, exact checking, response cleanup and session teardown are outside request clocks; declared mutation and invalidation-time destruction are inside. Full output hashing is inside, including cache hits. Inter-request checking perturbs caches. The advisory lock excludes cooperating measurement cases only. These conditions limit transfer to production, and the new efficient producer and retained trace make direct speedup comparisons with the older one-pass adapter inappropriate.

The result supports using existing native structures with precise caching as the baseline, and making extra compact facts demand-driven until a measured workload justifies them. It does not reject compact representations in an IR-free service or with a different query mix.

[Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), and [implementation/reproduction contract](../../README.md). Full observations remain in ignored `results.json`.
