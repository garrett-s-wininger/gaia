# Mechanisms to connect across fields

Each numbered connection separates a sourced mechanism from a Gaia hypothesis. “Question” identifies the evidence that could justify further exploration; none of these questions has been answered by this literature pass. The [overview](README.md) maps them to the existing portfolio.

## 1 Demand is an input

**Mechanism.** Adapton distinguishes observers from incremental computations and repairs results when demanded. Salsa provides a practical example of deterministic queries over explicitly supplied inputs. The useful distinction is between a result becoming potentially stale and someone actually requiring its replacement. [Adapton, PLDI 2014](https://matthewhammer.org/adapton/adapton-pldi2014.pdf), [Salsa overview](https://salsa-rs.github.io/salsa/overview.html).

**Gaia hypothesis.** An open editor diagnostic, a requested build target and an active test selection could register separate demands on shared facts. An edit invalidates observations; only the demanded closure is recomputed. Closing a file could remove a demand without canceling preparation still needed by the build. This reaches inside the computation, beyond the current obsolete-request queue experiment.

**Boundary and question.** Durable requested operations cannot disappear because an editor closes. Hidden environmental reads must become inputs, and laziness can move latency onto the next interaction. Does demand tracking save total CPU while preserving the latency of the next requested result against existing incremental language-server behavior?

## 2 Changes can have their own compiled programs

**Mechanism.** DBToaster derives and materializes delta queries, including higher-order deltas. DBSP treats incremental computations through an algebra of streams. These are ways to compute a result change directly instead of rerunning the original query on all affected data. [DBToaster, PVLDB 2012](https://vldb.org/pvldb/vol5/p968_yanifahmad_vldb2012.pdf), [DBSP, 2022 preprint](https://arxiv.org/abs/2203.16684).

**Gaia hypothesis.** Represent facts such as `imports(module, name)`, `defines(module, symbol)` and `test_uses(test, symbol)` as relations. Maintain demanded joins after admitted edits. For a bilinear join over signed multisets, the illustrative identity is:

```text
delta(R join S) = deltaR join S + R join deltaS + deltaR join deltaS
```

Here `R` and `S` are the old relations; the last term matters when both change in one update. This is a discrete algebraic identity, not numerical differentiation or an approximate gradient.

**Boundary and question.** Set deduplication, negation, recursion and ordering need their own semantics. A tiny input delta may produce a huge output delta. Does maintaining selected derived facts beat both full recomputation and Gaia's existing affected-subgraph traversal after charging indexes and update bursts?

## 3 Retain why a result exists

**Mechanism.** Provenance semirings annotate derived tuples with algebraic expressions describing their input derivations: alternatives combine differently from jointly required inputs. The original positive relational setting does not automatically cover absence or arbitrary negation. [Green, Karvounarakis and Tannen, 2007 author presentation](https://www.cis.upenn.edu/~plclub/propr/greg-slides.pdf).

**Gaia hypothesis.** The same derivation record might support invalidation, explanation in the editor and selective retention. If a derived relation has two independent witnesses, losing one witness need not remove the result. That is more informative than a flat “these files were read” set. It connects database lineage with scientific provenance and build observations.

**Boundary and question.** A compiler's execution trace is not automatically a proof that one alternative input suffices. Negative lookups, precedence and configuration must remain explicit predicates. Full symbolic provenance can grow rapidly. Can compact witnesses reduce unnecessary fact recomputation on a real dependency query without increasing update time or memory beyond the saved work?

## 4 Separate structural plans from changing values

**Mechanism.** Sparse direct solvers distinguish symbolic analysis from numerical factorization; reusable structure depends on the matrix pattern and solver conditions. OpenSubdiv separates topology refinement from interpolation of changing vertex data. [Davis, Rajamanickam and Sid-Lakhdar, sparse direct methods, section 4](https://people.engr.tamu.edu/davis/publications_files/survey_tech_report.pdf), [OpenSubdiv Far overview](https://opensubdiv.org/docs/far_overview.html).

**Gaia hypothesis.** Retain execution order, buffer sizing plans, reverse indexes and consumer binding plans under a separate structural identity. A source edit that preserves observed dependency topology may invalidate compiler results while leaving these plans reusable. Schema shape versus record values and package topology versus admitted bytes are related separations.

**Boundary and question.** Structural identity must include anything affecting the plan: generated edges, target configuration, ABI, layout or operator choice. Equal topology never proves equal outputs. Can a captured edit history identify a substantial class of value changes for which validating and reusing a plan is cheaper than rebuilding it? Reject the idea if structural analysis is already negligible.

## 5 Separate meaning from execution policy

**Mechanism.** Halide separates an image computation from choices about order, locality, parallelism and storage. Build Systems à la Carte separates scheduling from deciding whether a task needs rebuilding. These are related decompositions at different scales. [Halide, PLDI 2013](https://people.csail.mit.edu/jrk/halide-pldi13.pdf), [Build Systems à la Carte, ICFP 2018](https://simon.peytonjones.org/assets/pdfs/build-systems-original.pdf).

**Gaia hypothesis.** Give a small set of transformations explicit input/output and effect contracts, then compare eager versus lazy execution, batching, locality and retention without rewriting transformation semantics. Retain specialized compiler and ecosystem adapters. The substrate may need a shared vocabulary for decisions more than a shared implementation of every operation.

**Boundary and question.** Halide's transformations rely on restrictions that arbitrary tools do not satisfy. Stateful compiler passes, nondeterminism and external effects constrain legal schedules. Can two materially different schedules run the same bounded workflow with identical artifacts, diagnostics and failure behavior, while exposing their costs separately?

## 6 Optimize a small algebra of valid workflows

**Mechanism.** Equality saturation represents equivalent expressions in an e-graph and chooses among them using a cost model. The `egg` library supplies rebuilding and domain analyses to support this process. [egg, POPL 2021 paper preprint](https://arxiv.org/abs/2004.03082).

**Gaia hypothesis.** Start with a narrow workflow algebra: verified read, projection, pure mapping, materialization and concatenation under specified ordering. Explore whether conversion can be delayed, filters pushed earlier, or a repeated pure transformation shared. Connect compiler rewriting to database planning and artifact pipelines.

**Boundary and question.** Rewrite validity includes failures, ordering, metadata and effects. An additive expression-tree cost can miss shared DAG work, parallelism and peak memory. Search can cost more than execution. Does a small, time-bounded planner find improvements beyond hand-written fusion and a conventional dynamic-programming planner on previously unseen workflows? Whole-program semantic equivalence is outside this proposal.

## 7 Use cheap conservative filters before exact validation

**Mechanism.** Abstract interpretation derives sound approximations of program properties. Collision systems use a broad phase to find possible interactions, followed by detailed checks. Box2D makes these phases and their persistent structures explicit. [Cousot and Cousot, POPL 1977](https://www.di.ens.fr/~cousot/COUSOTpapers/POPL77.shtml), [Box2D simulation loop](https://box2d.org/documentation/md_simulation.html).

**Gaia hypothesis.** Search for reusable results through progressively more selective indexes before invoking the expensive exact guard. A coarse signature can select candidates or rank checks; accepting reuse remains the responsibility of the exact contract. This offers a constructive role for the AST fingerprints that Gaia found insufficient as object-cache proofs.

**Boundary and question.** A filter used to skip invalidation needs a soundness argument. A heuristic used only to miss a cache opportunity may safely cause recomputation. Those are different error costs. Does the cascade reduce complete validation cost after accounting for missed reuse and index maintenance, while preserving the packing, assembly, debug and side-output regressions?

## 8 A shared view may need a private complement

**Mechanism.** A lens maps a concrete structure to a view and uses the original concrete structure when putting an edited view back. This addresses information discarded by projection. [Foster et al., POPL 2005](https://www.cis.upenn.edu/~bcpierce/papers/newlenses-popl.pdf).

**Gaia hypothesis.** Multiple consumers can share typed facts while a producer retains source ordering, comments, explicit/default distinctions and unknown extensions needed for exact output. This connects the existing adapter roundtrip result to a formal account of why a useful common view need not contain every ecosystem detail.

**Boundary and question.** Lens laws do not automatically guarantee byte-identical serialization; exact bytes require a stronger concrete contract. View updates may be ambiguous or unsupported. Does sharing the common view plus an opaque complement reduce parsing and allocation compared with mature native APIs, while unchanged roundtrips and declared edits preserve the required information?

## 9 Unify a bounded working representation

**Mechanism.** Reyes converts diverse geometric inputs into micropolygons and exploits locality through the rendering pipeline. Vectorized database execution processes batches between operators. Both suggest common intermediate units with a controlled working set. [Reyes, SIGGRAPH 1987](https://www.cs.cmu.edu/afs/cs/academic/class/15869-f11/www/readings/cook87_reyes.pdf), [DuckDB execution format](https://duckdb.org/docs/2.0/internals/vector).

**Gaia hypothesis.** Share batches of source observations, diagnostics or dependency facts, allowing consumers to process only the columns they need. Stream these batches rather than first constructing one complete language-neutral object graph. A common working representation could be useful even if persistent representations remain ecosystem-specific.

**Boundary and question.** Rendering's numerical approximation is not permission to approximate compiler outputs. Batching adds delay; tiny requests can lose. Does a batch interface improve two real simultaneous consumers over a mature combined API after producer conversion and consumer materialization are included?

## 10 Value lifetime and storage lifetime are different

**Mechanism.** MLIR bufferization decides when tensor values can reuse storage without destroying still-needed data. RCU separates removal of a reference from reclamation after prior readers have finished. [MLIR bufferization](https://mlir.llvm.org/docs/Bufferization/), [Linux RCU overview](https://docs.kernel.org/RCU/whatisRCU.html).

**Gaia hypothesis.** Treat immutable logical values, physical allocations and reader lifetimes separately. Scratch memory may be reused after its last reader even though result identities remain in a catalogue. Publishing a new source generation need not wait for all readers of the old generation, provided retirement remains correct.

**Boundary and question.** Static compiler liveness is stronger information than a service usually has. A stalled process or device can pin old allocations; a cooperative epoch is not a revocation mechanism for arbitrary mappings. Can generation-level lifetime accounting beat per-object reference updates while keeping peak retained memory bounded under slow readers and rapid edits?

## 11 A buffer handoff is an ownership and completion contract

**Mechanism.** Arrow's C data interface exposes data and release callbacks for sharing within one process. Linux dma-buf separates a shared allocation from fences that signal completion of asynchronous device work. [Arrow C data interface](https://arrow.apache.org/docs/format/CDataInterface.html), [dma-buf and synchronization](https://docs.kernel.org/driver-api/dma-buf.html).

**Gaia hypothesis.** A useful view contract could carry logical identity, schema, bounds, access mode, memory domain, a lifetime token and readiness. That connects cross-language sharing to CPU/GPU/media pipelines. Some of these fields can be implicit for a synchronous local consumer; their semantics still need to exist.

**Boundary and question.** Arrow C pointers are not a cross-process wire format. dma-buf compatibility depends on devices, drivers and layout. “Zero copy” can still incur mapping, cache maintenance and waits. Which real consumer pairs can borrow the same representation with lower total cost than a copy, including release, readiness and fallback?

## 12 Amortize event handling with bounded service

**Mechanism.** io_uring uses shared submission and completion queues. NAPI processes network receive work with a budget and can continue polling when work remains. These mechanisms reduce repeated event-handling overhead while controlling how much work one service turn performs. [Axboe, Efficient IO with io_uring](https://kernel.dk/io_uring.pdf), [Linux NAPI](https://www.kernel.org/doc/html/latest/networking/napi.html).

**Gaia hypothesis.** Admit a bounded batch of known input requests or tool completions, process a bounded amount, then reconsider interactive work. Batch size and service budget need not be the same parameter. This extends the existing successful fixed batching with an explicit connection to driver scheduling.

**Boundary and question.** Busy polling consumes CPU and energy; completion order is not dependency order; compiler tasks may lack safe interruption points. Does batching reduce wakeups and service overhead during bursts without hurting isolated-request latency or starving editor work? An ordinary event loop and fixed batches are the first controls.

## 13 Move small requests to owned state

**Mechanism.** SPDK commonly assigns mutable state to one thread and sends it requests, reducing shared-state contention and preserving locality. It also describes selective replication of frequently read data. [SPDK message passing and concurrency](https://spdk.io/doc/concurrency.html).

**Gaia hypothesis.** Partition mutable admission indexes, worker state or cache queues by ownership, while sharing immutable payloads. This joins actor-style concurrency to hardware cache locality. The transferable idea is ownership of a shard; using SPDK's storage stack is not required.

**Boundary and question.** One owner can become a serial bottleneck. Cross-shard dependencies add hops, and a message per tiny lookup may cost more than a read lock. Does batching requests to stable owners improve useful throughput and tail latency compared with a lock-protected catalogue and immutable replicated indexes at laptop-scale concurrency?

## 14 Allocate resource vectors instead of worker slots

**Mechanism.** Dominant Resource Fairness allocates multiple resource types using each user's largest normalized resource share. Its fairness properties hold under the paper's resource and demand model. [Ghodsi et al., NSDI 2011](https://www.usenix.org/legacy/event/nsdi11/tech/full_papers/Ghodsi.pdf).

**Gaia hypothesis.** A Java compile, native analysis, dependency transfer and editor request consume different combinations of CPU, memory and I/O. Admission could account for those vectors, with an explicit interactive reservation, instead of pretending all jobs consume one interchangeable worker slot.

**Boundary and question.** Resident memory is a stock; CPU and bandwidth are rates measured over intervals. Bursty, nonpreemptible tasks and shared pages complicate attribution. Classical DRF guarantees do not automatically survive these changes. Can a simple vector-aware policy avoid memory-pressure stalls and protect current feedback better than fixed workers plus a memory gate, at acceptable accounting cost?

## 15 Model shared inputs as hyperedges

**Mechanism.** A hyperedge can connect all computations that use one datum. Zoltan uses hypergraph partitioning to model communication more directly than pairwise or purely geometric proximity in relevant scientific workloads. [Zoltan tutorial](https://cs.sandia.gov/Zoltan/papers/Dagstuhl09.pdf).

**Gaia hypothesis.** Treat tasks as vertices and an SDK segment, parsed module or artifact chunk as a hyperedge spanning its consumers. Under a simple replication model, a datum of size `b` used in `k` partitions contributes approximately `b * (k - 1)` extra bytes after the first copy. This avoids expanding every consumer group into an arbitrary clique.

**Boundary and question.** That objective models replicas, not all real transport: cache reuse, multicast, compression and temporal demand change costs. Partitioning and migration themselves cost work. Does a weighted hypergraph improve held-out transfer or admission volume over static clustering and existing co-access layouts after accounting for construction and repartitioning?

## 16 Share sparse kernels without erasing edge meaning

**Mechanism.** GraphBLAS expresses graph operations using sparse matrices over chosen semirings. Boolean operations can express reachability; masks restrict which entries are updated. [SuiteSparse GraphBLAS](https://github.com/DrTimothyAldenDavis/SuiteSparse/blob/dev/GraphBLAS/README.md), [Davis's algorithm paper](https://people.engr.tamu.edu/davis/GraphBLAS_files/toms_graphblas.pdf).

**Gaia hypothesis.** Dependency propagation, selected repository relations and provenance queries may share optimized sparse kernels even when their surrounding semantics differ. This is a narrower and more defensible unification than converting every graph into the same interpretation. It also supplies an external CPU control for Gaia's native CSR and GPU traversal studies.

**Boundary and question.** Small frontiers often favor direct adjacency walks. Converting representations or rebuilding a matrix may dominate. Negative observations, cyclic fixed points and deletion semantics remain above the kernel. Do repeated queries on a retained sparse representation beat the current native implementation at any realistic density and update rate?

## 17 Optimize movement at each memory level

**Mechanism.** Cache-oblivious algorithms analyze movement in an idealized memory hierarchy without embedding cache sizes in the algorithm. Roofline relates achievable compute performance to operational intensity and bandwidth. [Frigo et al., ACM Transactions on Algorithms 2012, extending the 1999 work](https://cs.uwaterloo.ca/~imunro/cs840/frigo.pdf), [Williams, The Roofline Model](https://escholarship.org/content/qt0qs3s709/qt0qs3s709_noSplash_b958fff358a4aa26695b4dfed9b5a29c.pdf).

**Gaia hypothesis.** Shared source pages can reduce physical memory while consumers still repeatedly miss in CPU caches. Recursive traversal, compact columns and blocked graph processing might remove traffic that a shared-memory interface leaves untouched. Conversely, recomputing a cheap projection can beat loading a large cached result.

**Boundary and question.** The ideal-cache assumptions do not describe every associativity, TLB or coherence effect. A compiler is not a uniform floating-point kernel, so a FLOP-based roofline is not a complete compiler model. Can profiles identify a memory-bound stage where a layout change reduces measured traffic and complete workflow time beyond existing compact/CSR controls?

## 18 Group persistent data by lifetime as well as access

**Mechanism.** SSD flash translation layers relocate live data when reclaiming erase blocks. SPDK's explanatory model shows why a region with no surviving data is cheap to reclaim. [SPDK SSD internals](https://spdk.io/doc/ssd_internals.html).

**Gaia hypothesis.** A pack containing long-lived toolchain bytes and short-lived generated outputs mixes lifetimes. Separating them could allow whole-segment deletion instead of repeatedly copying survivors. This connects storage garbage collection to compiler arenas and dependency-aware retention. Access locality and death-time locality are different objectives.

**Boundary and question.** A logical pack is not a physical erase block; filesystem allocation, copy-on-write and opaque device firmware can change the outcome. Co-access separation can also increase reads. Do lifetime groups reduce application-level rewrite volume and reclamation pauses without worsening real consumer access? Physical write-amplification claims require actual device telemetry.

## 19 Treat integration as a marginal cost decision

**Mechanism.** Coase explains organizational boundaries through the costs of transactions and internal coordination. Lampson's system-design guidance supplies a technical counterpart: interfaces and implementation choices affect the cost and flexibility of the whole system. [Coase, The Nature of the Firm, 1937](https://onlinelibrary.wiley.com/doi/10.1111/j.1468-0335.1937.tb00002.x), [Lampson, Hints for Computer System Design, 1983](https://www.cs.tufts.edu/~nr/cs257/archive/butler-lampson/Hints%20for%20computer%20system%20design.html).

**Gaia hypothesis, by analogy.** Share another preparation step when avoided discovery, parsing and handoff costs exceed added coordination, retention, adaptation and interference. This suggests measuring the marginal benefit of each additional consumer. It provides a reason to test selective integration rather than assume benefits grow with the size of the shared service.

**Boundary and question.** Firms and software processes are different objects; the economic argument supplies a cost-accounting question, not a runtime law. Does the second or third consumer improve complete session cost, or merely transfer work to a central service while increasing its serial path and lifetime burden?

## 20 Share accounting while leaving policy near consumers

**Mechanism.** Ostrom's account of polycentric systems describes coordination across multiple centers. Exokernel research separates protection from resource-management policy. These are distinct kinds of evidence with a useful architectural resemblance. [Ostrom's 2009 author interview](https://www.nobelprize.org/prizes/economic-sciences/2009/ostrom/164465-ostrom-williamson-interview-transcript/), [Exokernel, SOSP 1995](https://web.stanford.edu/class/archive/cs/cs240/cs240.1236/old/sp2014/readings/exokernel-sosp95.pdf).

**Gaia hypothesis, by analogy.** A common service could enforce budgets, identity and publication rules while compiler, editor and artifact consumers choose their own prefetch and retention policies. Shared accounting makes external costs visible: retaining a warm compiler may displace another consumer's useful pages.

**Boundary and question.** Social institutions do not prove scheduler properties. Local policies can produce contention or strategic overclaiming, even if every client appears efficient in isolation. Can simple per-consumer policies under a global budget outperform one universal policy on mixed workloads while preserving interactive reservations? This does not propose replacing Linux or the accepted source-control authority model.

## 21 Preparation has an option value and an expiry risk

**Connection.** The project already charges image and index construction. Investment reasoning adds a related question: how long will the prepared state remain usable, and what else could occupy its memory? The following is a Gaia decision model, not a claim derived from a finance paper.

Let `B` be preparation cost, `s` the saving per valid future use, `N` the number of uses before invalidation or eviction, and `H` the total retention and maintenance cost, all expressed in one declared cost unit. Preparation is beneficial in this simplified model when:

```text
E[N] * s > B + E[H]
```

**Gaia hypothesis.** Delay expensive preparation until observed demand makes useful reuse plausible. Distinguish a reusable structural plan from a version-sensitive result. The expected lifetime links this question to structural reuse, demand and resource accounting.

**Boundary and question.** Expected CPU savings can coexist with worse first-use latency; bytes and milliseconds cannot be added without an explicit valuation. Predictions need held-out traces. Does a simple reuse threshold beat always-prepare and never-prepare on total session cost, including invalidated preparations and displaced work?

## 22 Offload a resident pipeline

**Mechanism.** PBRT's GPU path uses queues of related work and specialized kernels, sometimes fusing stages to reduce traffic. Queue state and asynchronous execution also constrain synchronization. [PBRT wavefront architecture](https://www.pbr-book.org/4ed/Wavefront_Rendering_on_GPUs/Mapping_Path_Tracing_to_the_GPU), [implementation foundations](https://www.pbr-book.org/4ed/Wavefront_Rendering_on_GPUs/Implementation_Foundations).

**Gaia hypothesis.** If several demanded graph or data operations can share a device-resident representation, test the entire sequence with a final required readback. Structural plans and explicit buffer completion could make such residency usable. The exploitable link is between demand, data lifetime and operation grouping.

**Boundary and question.** GPU kernels are worthwhile only at a suitable scale and intensity; the same wavefront organization can hurt CPUs. PBRT's backend is not evidence that its implementation runs on Gaia's AMD/D3D12 path. Does any genuine multi-operation workload cross over against an optimized CPU pipeline after initialization, updates, allocation, synchronization and readback? The existing one-frontier GPU loss remains valid.
