# Small algebra and graph models expose useful boundaries

These first passes implement operation laws, dynamic observations, scheduling and memory/recomputation models. The strongest measured algorithm result is selective observation maintenance. The scheduling/retention studies expose policy tradeoffs but do not measure a production service. [Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), ignored [observations](results.json), and [reproduction](../../README.md).

## Source-operation laws and information joins

Twenty-five tiny source states combine absence, regular bytes, executable status and symlinks at two independent paths. The exhaustive run checks 625 compositions, 625 inversions and 625 accepted independent commutations. It also checks 27 fact-join triples for associativity/commutativity/idempotence. Conflicting values remain alternatives. Two requests expecting the same target generation demonstrate that a converged request set alone cannot publish both heads; the serialized authority model rejects the second.

On 1,000 known-applicable independent patch pairs over a 500-entry snapshot, footprint classification takes a median 0.259 ms, while reconstructing both complete-state orderings as an oracle takes 1,559.94 ms across three blocks. These are deliberately different operations. The short check assumes validated contexts and returns an independence classification; it does not publish the new state. This is not a claimed 6,000-fold complete-integration speedup. A competent production representation and baseline are still needed.

Only disjoint path domains commute in this small implementation. Same-path and ancestor/descendant cases are rejected as unproven. Inverses require their expected context; they are not a safe undo against arbitrary newer work. The result changes no snapshot-storage, review or landing policy.

## Dynamic observations reduce work in the explicit model

The generated workload contains 200 graph/query nodes, cyclic components, 162 initial file bodies and 24 updates. Updates include earlier include candidates appearing, later candidate edits, disappearance, environment selection, topology rewiring and directory membership. Selected test/editor labels and every derived fact match independent full recomputation after every update.

| Evaluator | Median construction | Median complete 24-update trace | Nodes evaluated in one trace |
| --- | ---: | ---: | ---: |
| Full recomputation | 1.24 ms | 32.76 ms | 4,800 |
| Observed frontier | 1.80 ms | 3.53 ms | 155 |
| Materialized relation | 1.97 ms | 3.59 ms | 155 |

Three blocks charge update admission, observation/index maintenance, affected closure, output aggregation and selection. Construction is recorded separately and is small enough that the selective modes still improve this particular trace. The relational candidate rebuilds reachability after topology changes; it is not a general differential engine. Python allocation diagnostics remain separate from timings and process RSS.

The model explicitly records failed lookup candidates up to the selected file. Editing an unobserved later candidate does no work. Removing a previously selected file or changing environment-selected locations refreshes the observations and can reselect affected roots. Cyclic outputs are unions of declared local facts; this does not prove arbitrary compiler fixed points, effect tracking or test semantics.

## Captured production relations and actual compiler controls

A read-only query extracts the prior Ninja executable's positive relation: 33 compile targets and 336 edges. Hypothetical admitted changes to `version.h`, `util.h` and the generated browse header select exactly the targets in that captured relation. The dependency log itself reports a stale entry; it is retained as historical relation input, not presented as fresh current compiler truth. This does not close dynamic production-scheduler invalidation.

A separate three-TU C fixture uses real Clang compilation and complete object-byte oracles. Across eight changes, it recompiles 3 / 0 / 3 / 3 / 3 / 1 / 3 / 0 TUs for shadow appearance, an unobserved later edit, environment change, shadow removal, optional appearance, one-source edit, optional removal and unrelated membership. All retained objects equal full recompilation. There are 3 initial, 16 selected and 24 oracle compilations. The lookup choices are declared by this fixture; no automatic preprocessor observation extraction is claimed here.

An Odin dense reverse-reachability kernel matches an independent closure oracle on 40 random graphs from 1 to 128 nodes, including cycles. It validates dimensions/values and borrows separate caller-owned buffers. Those kernel timings are not complete observation-engine or compiler timings.

## Scheduling gains depend on cancellation and the objective

The discrete-event model uses four workers, two editing clients, durable bulk jobs, explicit input-group cold costs and safe cancellation quanta. Declared task work is simulated; it is not measured compiler wall time. For the rapid-edit trace with interval 15 model units and accurate estimates:

| Policy | Final-current maximum response | Executed work | Obsolete work |
| --- | ---: | ---: | ---: |
| FIFO with cancellation | 111 | 969 | 340 |
| Critical-path priority | 103 | 979 | 394 |
| Fair client queues | 109 | 960 | 378 |
| Work-stealing deques | 114 | 964 | 317 |
| Decaying affinity/foraging | 109 | 958 | 298 |
| FIFO without cancellation | 642 | 3,157 | 2,579 |

All entries are model units. Every policy preserves dependencies, finishes durable jobs and suppresses stale completion publication. The large benefit in this trace comes from cancellation, which is a separate control; the five cancellation-enabled policies differ much less and trade useful latency against work/fairness. Foraging reduces obsolete work here but does not win response latency. The full raw study includes three arrival intervals and perturbed cost estimates. Python decision overhead is observed separately. No universal scheduler ranking or service-level guarantee follows.

## Retention policies can be worse than simple recency

The sequential six-node DAG model includes source, parse, facts, code, lint and binary intermediates. Computing an output requires all dependency leases, output bytes and producer scratch to fit simultaneously. The tiny offline oracle sees future requests and searches exact pebble states; it is not an implementable online policy.

For an alternating eight-request trace at budget 9, the offline optimum costs 80 work units, recency costs 93, and immediate cost/size retention costs 164. Retain-all reports infeasible rather than exceeding the budget. All complete heuristics cost at least the oracle and respect the modeled payload/scratch bound. This is not an RSS limit or measured compiler cache result. The negative cost/size result shows why local retained value can miss downstream recomputation structure.

## Modularity can contain conservative invalidation

One unchanged fine graph has 160 nodes in 20 independent chains and 20 roots. A single changed leaf affects one exact root. Coarse groups aligned with those chains also select one root. Scrambled level-based groups and a global group conservatively select all 20, adding 19 unnecessary roots. All remain correct supersets.

This changes the partitioning of the same graph, not the program's dependency semantics. It tests the cost of coarse boundaries; it is not proof that biological modularity or a codebase refactor improves performance automatically.

## Limits worth preserving

These are bounded Python models plus two native kernels and a small actual compiler oracle. Warm host pages and the shared advisory timing lock do not eliminate unrelated load. A preliminary scheduler canceled at an arrival instead of waiting for its declared safe point; a regression now rejects that behavior and the primary was rerun with frozen sources. Fifteen unit tests and source before/after hashes pass. Automatic compiler observations, real task queues, persistent state, concurrent publication, actual memory pressure and broad production traces require separate experiments.
