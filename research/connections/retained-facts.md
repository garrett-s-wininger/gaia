# Second experiment: useful facts must earn their retention

The [first pass experiment](pass-experiments.md) found that changing propagation algebra did not beat a native block worklist, and that fact production dominated much of the wider pass. The follow-up tests the next hypothesis: emit a second useful relation during that production, retain it, and reuse it across consumers.

The [implemented experiment](../../experiments/pass_algebra/retained/README.md) couples liveness with syntactic forward data-use queries from function parameters. One policy emits compact CSR def-use edges during the liveness operand walk; another waits for query demand. The control traverses LLVM's existing use lists. All three cache unchanged liveness and query results, invalidate the same functions, and reject stale generations.

This joins the [bounded representation](connections.md#9-unify-a-bounded-working-representation), [demand](connections.md#1-demand-is-an-input) and [preparation expiry](connections.md#21-preparation-has-an-option-value-and-an-expiry-risk) hypotheses. It also makes the duplicate-representation risk concrete: LLVM already maintains the relation that a compact graph would encode again.

## Result

Across a constructed ten-request trace on real upstream IR, eager compact production increased median total request time by 38.5% for Zstandard lazy compression and 30.7% for zlib deflate, losing all seven paired comparisons for each. On-demand compact production reduced the penalty to 2.7% and 16.9%, winning one of seven and zero of seven pairs. The small common-code control had mixed outcomes at microsecond durations.

Compact graphs did help new-query traversal. In the exploration phase, eager CSR reduced the query phase from 0.343 to 0.207 ms for Zstandard and 0.089 to 0.058 ms for zlib. Graph production and rebuilding after edits cost more than that saving. The [report](../../experiments/pass_algebra/retained/results/initial/REPORT.md) includes complete-request timings, retention counts, exact checks and limitations.

Caching changes the amortization question. Repeating an identical query does not repeatedly repay a faster graph traversal because the native control also returns a cached final result. Extra representation work has to be repaid by distinct demands before invalidation, lower memory costs at a later lifetime boundary, or capabilities the existing representation cannot provide.

## What this changes for Gaia

The evidence favors a native structure plus precise result lifetime as the current default for these two analyses. A common producer can still be useful, but eager emission of every potentially useful relation is not justified by this trace. Sharing an operand walk is insufficient when the extra graph duplicates an already maintained relation and many functions never receive a slice query.

The experiment exposes a sharper next question: can a consumer continue using compact immutable facts **after the compiler IR is released**, or does a measured stream of distinct queries repay construction before the next edit? That would test a different lifetime or demand boundary. A query-volume crossover should use observed or explicitly varied distinct demands, not repeated identical requests whose cache hits erase the traversal difference.

This work supplies an analysis-level cost and validity boundary alongside the [compiler integration](../integration/README.md). It does not establish frontend integration, complete development-session acceleration, sound test exclusion, or a reason to offload this workload to a GPU/NPU.

The implementation, raw-identity pins and complete validation are indexed in [experiments.json](experiments.json). Generated inputs, tools and raw observations remain in ignored experiment directories.
