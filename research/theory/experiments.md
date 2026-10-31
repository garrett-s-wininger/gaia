# Experiments connecting theory to useful operations

Status: original experiment designs. A [bounded implementation round](../science/README.md) now tests these families; its [coverage map](../science/coverage.md) distinguishes measurements, checked models and remaining gaps. Each set can start with a small deterministic implementation and replay harness. Native implementations use Odin where practical. Existing [empirical findings](../findings.md) supply workloads and controls; the [model guide](README.md) links the supporting literature.

## Shared measurement contract

Declare the input generation, required outputs and correctness oracle before selecting a policy. Distinguish dependency, transfer, lifetime and operation edges. Record task readiness, queue entry/start/end, cancellation, content access and publication through causal IDs. Cross-host clocks need explicit uncertainty; a single global timestamp order is not assumed.

Measure total work, critical-path estimates, first useful/current result, complete readiness, queue delay, bytes requested/transferred/verified, retained and transient memory, and preparation/recovery cost. Separate logical byte limits from sampled or enforced process limits. Instrumentation overhead needs its own comparison. Percentile claims require enough independent samples; a handful of traces should retain their observations instead.

Use real traces plus synthetic cases that expose fanout, cycles, bursts, changing hot sets and failures. An offline oracle may use future knowledge only when clearly labeled. It is a comparison aid, not an implementable policy. Preserve simple conventional baselines and identical validation/publication rules.

## 1. Reconcile mostly overlapping content sets

**Question:** Can synchronization metadata scale with disagreement rather than total inventory size?

Start with two deterministic content-ID collections and a trusted exact set oracle. Compare sorted full lists, a Merkle hierarchy and an IBLT-style reconciliation candidate. Sweep inventory size, overlap, churn and incorrectly estimated difference size. Charge structure construction, updates, decoding, retries and exact final verification.

Report metadata bytes, round trips, CPU, peak memory and total useful acquisition. Decode failures must trigger a bounded fallback; a probabilistic summary must never hide missing required content. An ordinary exact hash-list batch may remain best for small sets. Use this for artifact caches and later source synchronization without coupling the experiment to review metadata.

## 2. Check a small algebra of source changes

**Question:** Can explicit context/dependency laws improve stack manipulation and reconciliation without weakening source correctness?

Begin with add/delete/replace operations on paths, regular bytes and executable status. Specify operation domains, composition and the cases with a valid inverse or commutation. Include same-path edits, absence/type changes and directory/path collisions as explicit unsupported/conflicting cases until modeled. Compare algebraic reordering with reconstructing and integrating complete snapshots.

Exhaustively enumerate tiny states, then generate larger randomized operation sequences. Verify accepted commutations produce equal complete states, invalid contexts are rejected, and conflict alternatives survive. Measure law-checking cost, reorder work and retained context. This tests an operation model; it neither selects diff-based history storage nor proves program/test/review independence.

## 3. Maintain changing repository facts

**Question:** Does incremental graph maintenance reduce complete query work once observation changes and deletions are charged?

Represent file membership, include observations and selected derived facts as relations. Compare full recomputation, a simple affected-frontier queue and an incremental relational/dataflow approach. Exercise source edits, removed edges, optional-file appearance, include shadowing, cycles and configuration changes.

Check every result against independent full recomputation. Measure update admission, graph/index maintenance, affected frontier, query latency and retained state. Apply first to the [fixed-dependency production graph's gap](../compiler/followthrough/findings.md#a-larger-production-graph-works-within-a-fixed-dependency-trace), then to test selection or editor navigation. Reaching fewer nodes is useful only if those are the correct nodes.

## 4. Schedule useful feedback through a changing graph

**Question:** Can priorities, local coordination and cancellation reduce time to current feedback under a fixed resource budget?

Replay rapid edits while analysis, compilation, tests and searches compete. Compare FIFO, critical-path priority, fair per-client queues, work stealing and a bounded decaying-locality score inspired by foraging. Keep the actual worker pool and correctness rules identical; include scheduling/communication overhead.

Record current-generation response latency, total CPU, wasted obsolete work, starvation and memory. Test a hot client, bulk background work, inaccurate cost estimates and changing affinity. Cancellation is allowed only at declared safe points; durable acknowledged operations cannot be dropped. The policy should improve useful feedback without simply shifting unlimited delay to another client.

## 5. Control delivery and retention with feedback

**Question:** Can a bounded controller adapt to latency/bandwidth/working-set changes better than one fixed chunk/window policy?

Extend the [verified demand consumer](../artifacts/followthrough.md) with request-window and prefetch controls. Compare fixed finalists, a simple damped feedback policy and a bounded exploratory policy. Sweep latency, bandwidth, workload phases and burst arrivals independently. Preserve producer identities, requested-content checks and byte-budget enforcement.

Measure time to useful execution and full readiness, overfetch, queue delay, transient memory, controller overhead and oscillation/overshoot. Separate storage-service models from actual network/physical I/O validation. A controller that wins only after uncharged warm-up or exceeds its budget has not improved the same operation.

## 6. Adapt artifact layout and worker locality

**Question:** Can local reinforcement/decay create useful placement with lower maintenance cost than rebuilding a global partition?

Construct a co-access graph from actual content reads, without using future requests. Compare unchanged layout, simple static clustering, periodic graph partitioning and a bounded reinforcement/decay rule. Target pack grouping or worker affinity first; replication needs its own byte and lifecycle contract.

Charge graph updates, repacking, copied bytes, retained readers, verification and restart. Test unseen traces and sudden hot-set reversals. Success requires complete-consumer benefit after maintenance costs; improving a locality score alone is insufficient. A nature-inspired rule may lose to a simpler cache/partition policy, and that result should be retained.

## 7. Trade retained intermediates against recomputation

**Question:** Which shared results should survive when several tools compete for memory?

Use a task graph with measured preparation/recomputation costs and explicit immutable-result lifetimes. Compare retain-all where feasible, recency, cost/size-aware retention and a small offline optimal-search oracle. Explore graph-pebbling-style choices with fanout and repeated consumers, then replay one actual schema/analysis or asset pipeline.

Count transient producer/consumer buffers and active leases alongside cached bytes. Measure complete latency, repeated work, eviction, peak memory observations and cleanup/restart. The reference search must stay small; deriving an optimal tiny schedule does not establish an efficient general scheduler or an enforceable RSS budget.

## 8. Evaluate adaptation and transformation boundaries

**Question:** Can small policy searches and explicit transformation laws improve portability and performance together?

For a format adapter, define which identities and metadata must round-trip and which projection losses are intentional. Generate unknown fields, explicit/default variants and malformed inputs; compare direct-view and materialized-object consumers. Preserve the rejected Protobuf metadata case as a regression rather than normalizing it away.

For a policy tuner, select a small discrete space of batch size, grouping and retention thresholds. Compare fixed defaults, grid/random search and one adaptive candidate under equal evaluation budgets. Keep training and held-out traces separate; charge all preparation and retain failed candidates. Do not mix a new optimization level, representation or weaker oracle into a claimed isolated policy gain.

## Suggested first sequence

Start set reconciliation and the small patch algebra as independent correctness-focused prototypes. In parallel, build the common trace/replay boundary for scheduling and feedback experiments. Those traces can then support adaptive locality and memory/recomputation studies, followed by production workloads from assets, environments, editor services and shared human/agent workspaces.

No experiment here requires a production remote service or changes the accepted component contracts. Public schemas and protocols remain separate design decisions after the behavioral boundary is understood.
