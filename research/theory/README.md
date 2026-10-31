# Mathematical models and ideas from other sciences

Status: supporting literature and experiment designs. The [bounded implementation round](../science/README.md) now supplies measured results and models; this page retains the reasoning behind those tests. It supplies models and experiment designs across the existing compiler, artifact, runtime, testing, editor and source-control work. The [experiment sets](experiments.md) define how to test the proposals on the available Linux laptop.

There are two useful roles for theory: laws that describe valid transformations, and policies that choose where to spend resources. A correctness law can constrain an implementation. An adaptive policy needs empirical comparisons, including its own learning, coordination and retention costs. Inspiration from nature supplies candidate mechanisms; any benefit to software remains a hypothesis.

## Models to connect across the research portfolio

| Area | Useful concepts | Proposed Gaia application |
| --- | --- | --- |
| Set theory and reconciliation | Membership, intersections, differences, compact set summaries | Identify missing content and changed observations without exchanging or rebuilding complete inventories. |
| Patch algebra | Context, composition, partial inversion, commutation | Reorder/split stacks, reconcile private work and classify independent operations while validating resulting snapshots. |
| Graph algorithms and incremental computation | Reachability, dependency frontiers, strongly connected components, fixed points | Update affected repository facts and build observations; distinguish cyclic analysis from acyclic task execution. |
| Parallel algorithms and graph pebbling | Total work, critical path, retained intermediates versus recomputation | Preserve parallel consumers while sharing preparation; choose which costly results fit in a memory budget. |
| Networking and queueing | Bandwidth-delay product, flow control, fairness, head-of-line blocking | Select request windows, batches and priorities across data delivery and tool work. |
| Order and lattice theory | Partial orders, monotonic information, joins | Combine observations with explicit convergence rules; preserve coordination for decisions whose semantics require it. |
| Information theory | Representation size, redundancy, query selectivity | Compare full inventories, exact differences, sketches and direct views including construction and access costs. |
| Feedback control | Setpoints, delayed observations, damping, hysteresis | Adapt concurrency, prefetch and retained workers without oscillation or unbounded growth. |
| Nature-inspired adaptation | Local reinforcement, decay, exploration, modular organization | Explore locality-aware work placement, cache admission and bounded prefetch policies. |
| Experimental design and optimization | Controlled interventions, held-out workloads, bounded search | Tune interacting parameters without hiding search cost or choosing only favorable traces. |

These concepts apply to several distinct structures. A dependency graph, a transfer network, a snapshot-retention graph and an operation history have different edge semantics. Their interfaces can share identities and observations without pretending those graphs are interchangeable.

## Sets and patches give concrete starting points

For exact content sets `A` and `B`, missing content is `B ∖ A`; two-way inventory disagreement is their symmetric difference. Compare complete sorted inventories and Merkle traversal with a set-reconciliation sketch. Invertible Bloom lookup tables provide one probabilistic candidate; decoded candidates still need exact verification, and failures must fall back to a complete method. The [original IBLT paper](https://arxiv.org/abs/1101.2245) describes the data structure, not a demonstrated Gaia transfer advantage.

A patch can be modeled as a transformation between defined contexts. Reordering can require transformed patches: applying `p` then `q` may correspond to `q'` then `p'`, rather than blindly swapping the original operations. [Darcs patch theory](https://darcs.net/Theory) and [Homotopical Patch Theory](https://www.cs.cmu.edu/~rwh/papers/htpt/paper.pdf) provide relevant foundations.

The experiment should specify a small operation algebra and check its laws against complete-state oracles. Preserve dependencies, conflicts, absence, file types and metadata. Disjoint text edits do not establish independent program behavior, and an inverse applied to a different current state is not automatically a safe undo.

Patch research does not change the accepted source-control storage model: retained source remains directly readable through snapshots. Algebraic transitions can guide integration/reordering without introducing mandatory replay of historical diffs or changing the landing/review contracts.

## Graph and network models explain different costs

For a fixed task DAG with total work `W`, span `S` and `P` identical processors, the idealized work/span lower bound is `max(W/P, S)`. Its assumptions exclude the resource contention and communication costs that a real tool service must also measure. Changing the algorithm or representation changes the graph and its work; this is not a physical floor for the problem. [Work/span reference](https://users.ece.cmu.edu/~jhoe/course/ece643/latest/L05.pdf)

Incremental analysis can contain cycles and fixed-point computation. [Differential Dataflow](https://www.microsoft.com/en-us/research/publication/differential-dataflow/) is relevant prior work for maintaining results as inputs change. Any Gaia prototype still needs deletion, negative observations and stale-generation correctness checks, plus a full recomputation oracle.

Networking offers corresponding tools for data movement. Bandwidth-delay product helps reason about bytes in flight; Little's law relates average population, arrival rate and time within the same stable system boundary. Neither selects an optimal request window or predicts tail latency by itself. [RFC 7323](https://www.rfc-editor.org/info/rfc7323/), [Little's original paper](https://pubsonline.informs.org/doi/abs/10.1287/opre.9.3.383)

Flow fairness and active queue management suggest ways to protect interactive work from bulk work. [FQ-CoDel](https://www.rfc-editor.org/info/rfc8290/) is a networking baseline for these ideas. Mapping them to tool scheduling requires explicit task cancellation and admission semantics: a compiler job cannot simply be discarded like a packet, and acknowledged source operations must retain their durability requirements.

## Nature supplies mechanisms to test

**Adaptive transport.** Slime-mould research motivates locally reinforcing used connections and weakening unused ones. Our proposed analogue is an evolving co-access graph for artifact layout, replication or worker affinity. Compare it with ordinary clustering, static placement and cost-aware caching, using unseen traces and changing hot sets. Digital links have different costs from spatial biological networks. [Tero et al., adaptive network design](https://pubmed.ncbi.nlm.nih.gov/20093467/)

**Foraging and local coordination.** Ant-inspired methods use indirect shared signals to guide exploration. A bounded proposal is a decaying score for a worker's recent useful access to an input group, informing task placement. Compare FIFO, locality-aware queues and ordinary work stealing before a more elaborate search. Preserve fairness, dependencies and admission bounds. [Dorigo et al., Ant System](https://iridia.ulb.ac.be/~mdorigo/Published_papers/All_Dorigo_papers/DorManCol1996tsmcb.pdf)

**Homeostasis.** Treat memory, queue delay and bandwidth as observed signals, with a controller adjusting prefetch/concurrency slowly enough to account for delayed feedback. Compare fixed policies and simple damped controllers. Measure overshoot, settling time and starvation as well as throughput. This is a proposed feedback-control application; a logical cache limit or sampled stop remains different from an enforced process limit.

**Selective retention and modularity.** Explore keeping frequently useful preparation while discarding cold state, with fresh mutable bindings. Also test boundaries that contain change propagation. These ideas connect to existing caching, garbage collection and modular software design; a biological analogy alone establishes no new algorithm or speedup.

**Evolution and adaptation.** Search over a small space of packing, batching and admission policies with a fixed evaluation budget. Compare grid/random search and simple online selection. Charge every training run, retain unsuccessful candidates and evaluate on held-out workloads. Expensive compiler-image construction makes unbounded tuning particularly inappropriate.

## Correctness boundaries remain explicit

Lattice-based replicated data types provide formal convergence conditions for suitable state. They do not make every application decision coordination-free. [Shapiro et al., CRDTs](https://perso.lip6.fr/Marc.Shapiro/papers/CRDTs_SSS-2011.pdf)

Observed facts, conflicts, approvals, withdrawals and authoritative landing decisions need their own semantics. Heuristic confidence cannot substitute for source identity, current-generation validation or the accepted review/landing policy. Exact-output contracts must retain explicit/default/source metadata, as the [Protobuf rejection](../../experiments/workflows/results/protoc-guarded/REPORT.md) demonstrates.

Start with simple models and strengthen them when measured prediction error justifies it. A proposed mechanism earns further work when it improves a complete operation under equivalent correctness and resource conditions.
