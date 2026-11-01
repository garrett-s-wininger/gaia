# Accelerators and physical models for the whole development loop

Status: research hypotheses, 31 October 2026. This extends the [connection map](README.md) from execution and data reuse to understanding code, choosing work, testing, reproducing failures and delivering useful feedback. No new hardware execution or kernel configuration changes accompany this study.

The optimization target is **time to a useful, trustworthy answer about a change**. A faster kernel can help, but so can avoiding an irrelevant test, making a failure reproducible, retrieving the right context, or keeping background work from blocking an editor. The proposals below distinguish established mechanisms from their possible application to Gaia; “novel” here means an additional angle for this project, not a priority claim over prior research.

## Accelerator opportunities

The [source-discovery study](source-discovery.md) expands the retrieval and navigation workload below. The [tooling-internals study](tooling-internals.md) also considers changing compilers, linters and runtimes so these workflows can share more useful state.

### A1 An NPU could maintain local relevance across a project

Keep a small embedding or ranking model available to score changed functions, symbols, documentation, previous failures and test descriptions. Update only changed records. Human and agent requests could then retrieve likely relevant material from the same revision-aware index. A second use is grouping similar compiler diagnostics or failure reports before presenting them.

The proposed saving includes CPU interference and unnecessary context gathering, not just inference latency. The CPU still tokenizes inputs and manages indexes unless those stages have a supported offload path. Compare lexical/symbol search, a CPU model and an NPU model on the same retrieval tasks, charging model compilation, first inference, updates, idle residency and retrieval quality.

NPU runtimes distinguish model preparation from later execution; OpenVINO explicitly documents those timing boundaries and model caching. That makes a retained model a plausible mechanism, but does not establish a Gaia retrieval win or compatibility with the captured AMD machine. [OpenVINO NPU documentation](https://docs.openvino.ai/2026/openvino-workflow/running-inference/inference-devices-and-modes/npu-device.html).

### A2 Use a learned model to rank speculative work

Predict which test will fail first, which dependency is likely to be needed, or which prepared state will be reused before eviction. Feed the model facts Gaia already owns: edit kind, observed dependency changes, prior timings and recent demand. This could make the NPU an adviser to the scheduler while the CPU executes the authoritative operations.

This is a proposed application of small-model inference. A wrong prediction may waste a bounded amount of work; it must not validate a cache hit, suppress a required check or publish a stale result. Begin with cheap rules and a CPU model. NPU offload is justified only if inference is substantial enough to amortize dispatch and does not consume more shared power or bandwidth than it saves.

Measure time to the first actionable failure and cost of wasted speculation on unseen edit traces. Randomize some ordering to avoid learning only from tests the policy already prefers. This adds a concrete prediction target to the earlier [preparation model](connections.md#21-preparation-has-an-option-value-and-an-expiry-risk).

### A3 Some NPUs can run regular dataflow kernels without a neural model

AMD's IRON/MLIR-AIE toolchain exposes workers, tiled computation, buffers and data movement; its examples include element-wise dataflow patterns. That opens a more unusual possibility: streaming feature extraction, repeated fixed-shape reductions, vector similarity or a restricted numerical analysis over retained arrays. [IRON programming interface](https://xilinx.github.io/mlir-aie/dev/api/iron/), [programming examples](https://github.com/Xilinx/mlir-aie/blob/main/programming_examples/README.md).

The hypothesis is to compile a stable regular operation once and reuse it across many source or trace batches. This is device-specific programming, not evidence that an NPU can execute an arbitrary compiler pass. Dynamic allocation, pointer-heavy traversal, branching, precision, overflow and limited local memory can defeat the mapping. For exact results, verify operation semantics against an exact CPU oracle, including boundary values.

A useful first question is whether any actual Gaia stage has the required shape and enough repeated work. If SIMD CPU code already finishes before NPU submission would, stop. The cited toolchain's existence does not establish an accessible NPU on this host.

### A4 Use a GPU to explore concurrent protocol states

GPUexplore demonstrates GPU execution of explicit state-space exploration; its 2023 version reports deadlock checking for concurrent models with data. A concrete Gaia target is the protocol around input generations, leases, cancellation, publication and reclamation. [GPUexplore 3.0, SPIN 2023](https://awijs.win.tue.nl/articles/gpuexplore3.pdf).

For example, enumerate interleavings of two readers, one publisher, cancellation and a device completion. Look for freeing an allocation while a reader still owns it, or publishing a result after its generation became obsolete. This accelerates design validation and debugging, even if it never makes a compiler invocation faster.

The model must correspond to the implementation, and explored bounds must be stated. This is not automatic verification of arbitrary native programs. Compare against a CPU model checker with reductions enabled. Porting a CUDA research tool to Gaia's demonstrated AMD/D3D12 path is separate work; small state spaces may remain CPU tasks.

### A5 Keep coverage and trace queries in a regular representation

A test-by-feature coverage matrix supports batched intersections, counts and similarity queries. A large trace supports filtering, grouping and joins across many debugging questions. These are better-shaped accelerator candidates than a tiny irregular dependency frontier. GPU tabular systems such as cuDF supply a concrete implementation reference. [cuDF documentation](https://docs.nvidia.com/cudf/latest/).

Proposed uses include ranking tests after an edit, grouping duplicate failures, identifying common slow paths and comparing performance traces across revisions. Retain the representation across queries, and include ingestion and result transfer in the comparison with CPU bitsets, sparse kernels and DuckDB.

Observed coverage is incomplete evidence of future behavior. Use it to prioritize; it is not by itself a sound rule for excluding tests. cuDF's CUDA implementation is not available merely because another GPU backend works. A small laptop trace may be cheaper to scan on the CPU.

### A6 Batch differential tests for suitably regular components

For a shader, image kernel, numerical routine or small fixed-state interpreter, run many inputs or candidate versions in parallel and compare against a reference. This could speed regression discovery for components already amenable to device execution. It combines the prior [resident pipeline idea](connections.md#22-offload-a-resident-pipeline) with testing rather than production throughput.

Arbitrary application tests do not become GPU kernels automatically. System calls, dynamic object graphs and divergent paths often prevent the mapping. Compilation, transfers and a meaningful oracle remain part of the cost. Numerical tolerance must be specified where bit identity is not the contract. Compare equal testing budgets and unique reproduced failures, not just executions per second.

## Linux mechanisms that could shorten the loop

### K1 Schedule around pressure and current user demand

PSI measures CPU, memory and I/O stall time. cgroup v2 provides resource controls; `sched_ext` permits experimental BPF-defined CPU scheduling on appropriately configured kernels. [PSI](https://docs.kernel.org/accounting/psi.html), [cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html), [sched_ext](https://www.kernel.org/doc/html/latest/scheduler/sched-ext.html).

Gaia could distinguish a test blocking the current edit from background indexing and speculative builds. When pressure rises, stop admitting expendable work before it delays requested feedback. Use the ordinary scheduler, cgroups and application queues first. Consider `sched_ext` only if traces show a remaining CPU scheduling problem that these cannot address.

Weights do not guarantee deadlines, and `memory.high` is a throttling/reclaim boundary rather than a hard memory cap. Device contention and laptop thermal limits need separate accounting. Compare p95 current-result latency, completed background work and total stall time under the same resource limits. More CPU utilization is not necessarily better development performance.

### K2 Learn where legacy tools repeatedly cross expensive boundaries

BCC provides BPF-based tracing tools and examples. BPF tracing can export selected events through ring buffers, whose kernel design explicitly allows reservation failure when full. [BCC](https://github.com/iovisor/bcc/blob/master/README.md), [BPF ring buffers](https://docs.kernel.org/bpf/ringbuf.html).

Use opt-in, scoped tracing to find repeated opens, process launches, faults, waits and worker restarts. Correlate them with a declared tool request and source generation. The result could identify where a persistent worker, bulk input admission or retained index would remove real work, without first rewriting the tool.

Trace loss, permissions, namespace/path interpretation and unobserved semantic inputs matter. Such observations are optimization evidence, not automatically a complete dependency declaration. Missing lookups and environmental inputs must still be represented for sound reuse. Compare the tracing overhead against `perf`, tool-native profiles and short targeted captures; do not put full tracing on every operation by default.

### K3 Make prepared tests cheap to branch and discard

`userfaultfd` permits userspace handling of selected faults and supports write-protection mechanisms; OverlayFS provides a lower tree and writable upper tree. These can inform demand-loaded prepared state and private filesystem changes for repeated tests. [userfaultfd](https://docs.kernel.org/admin-guide/mm/userfaultfd.html), [OverlayFS](https://docs.kernel.org/filesystems/overlayfs.html).

The proposed workflow is to prepare an expensive fixture, run each test with declared private state, and discard its changes. First compare ordinary copy-on-write fork, existing test batching and filesystem sharing. Use custom fault handling only when measured memory loading or dirty-page handling justifies it.

A memory snapshot does not reset sockets, database servers, timers, other processes or device state. OverlayFS does not supply complete isolation, and a multithreaded runtime cannot be assumed safe to fork. Establish an explicit reset contract. Measure setup, private writes, cleanup and dirty-memory growth; an impressive reset primitive is insufficient if fixture preparation was already amortized by the test runner.

### K4 Preserve a failure so it can be examined repeatedly

rr records supported Linux executions for deterministic replay and reverse debugging. Gaia could bind a failure recording to its source generation, toolchain, environment and test inputs, then reuse that recording for diagnosis instead of repeatedly trying to reproduce the failure. [rr project](https://rr-project.org/).

The performance opportunity is reduced human or agent investigation time. Combine recording with a minimized reproducer, while keeping them distinct: replay examines the recorded execution; a changed program needs a new execution. Recording overhead, supported CPUs/syscalls, parallel execution and external device interactions limit coverage. Validate the actual runtime boundary before adopting it for a test class.

### K5 Verify immutable artifacts on demand

fs-verity makes supported files read-only and verifies accessed data through a Merkle tree. Its file digest can be retrieved without rereading the complete payload. This is directly relevant to large immutable SDK or dependency packs whose consumers touch a small subset. [fs-verity](https://docs.kernel.org/filesystems/fsverity.html).

The hypothesis is to preserve verified direct access while avoiding repeated eager whole-pack hashing. Charge tree construction, initial content admission, metadata storage and later fault-time verification. Authenticate the expected digest separately; the fs-verity digest is not interchangeable with an existing plain file hash. Compare against Gaia's verified chunk design and an ordinary immutable file cache. Filesystem support and host policy are prerequisites.

### K6 Retain useful working sets instead of entire warm processes

DAMON samples memory access patterns and can support access-aware operations. Combine this physical information with Gaia's semantic knowledge of regenerable indexes, source mappings and expensive prepared state. [DAMON design](https://docs.kernel.org/mm/damon/design.html).

The proposed policy asks two different questions: is this memory being used, and how expensive would it be to reconstruct? A cold, cheap index and a cold, costly runtime image need not receive the same treatment. Start with monitoring and logical object eviction; any reclamation action must match the allocation's semantics. Never discard arbitrary live anonymous state as though it were a regenerable cache.

Sampling can miss short bursts. More monitoring or premature eviction can cause refaults. Compare with the normal kernel reclaim policy and simple application LRU under actual memory pressure. The meaningful result is lower useful latency or fewer memory stalls, including monitoring overhead.

## Nature and physical systems as sources of mechanisms

### P1 Adaptive mesh refinement suggests adaptive analysis resolution

Berger and Oliger's adaptive mesh refinement allocates finer computation where estimated numerical error requires it. The transfer to development is an analogy about allocating resolution, not an assertion that program dependencies behave like spatial fields. [Original 1984 paper abstract](https://www.sciencedirect.com/science/article/pii/0021999184900731/pdf?md5=5e2a7448acc5f3f93e61aa5172e04178&pid=1-s2.0-0021999184900731-main.pdf).

Maintain coarse module summaries broadly, then refine functions, call sites or path-sensitive facts near a requested diagnostic, failing test or uncertain boundary. A broad edit may invalidate summaries before any expensive detailed analysis runs. Coarse summaries used for correctness must conservatively include possible effects; unresolved cases trigger refinement. Macros, reflection and global state can destroy locality.

Compare with a conventional demand-driven analyzer. Count summary maintenance and repeated refinement. This is especially interesting for whole-program tools where full precision is expensive but the user is investigating one change. It does not justify approximating a final compiler artifact.

### P2 Immune memory suggests a project-specific regression memory

Adaptive immunity combines recognition, expansion, contraction and memory. A software analogy is to retain compact representatives of prior failure classes, increase exploration around a newly observed failure, then reduce redundant effort while keeping a small regression witness. This is conceptual inspiration; it is not a new biological algorithm for testing. [Review of adaptive immune principles](https://pmc.ncbi.nlm.nih.gov/articles/PMC11177542/).

Pair that idea with diverse test generators rather than many copies of one strategy. EnFuzz supplies an actual software mechanism for sharing seeds across diverse fuzzers. [EnFuzz, USENIX Security 2019](https://www.usenix.org/conference/usenixsecurity19/presentation/chen-yuanliang).

Gaia's reusable unit could include a minimized input, failure signature, relevant source facts and toolchain context. Similarity can suggest what to try first, but only reproduction identifies the same failure. Compare against an ordinary minimized regression corpus plus an established ensemble; measure distinct reproduced regressions and time to detection. Retain exploration so a memory of old failures does not monopolize the test budget.

### P3 Reaction networks suggest conservation laws for resource lifetimes

Petri nets have been applied to represent and analyze metabolic pathways. Their use here would be a formal resource model inspired by the same production/consumption structure. The biological paper establishes the modeling connection; the following invariant is a Gaia proposal. [Reddy, Mavrovouniotis and Liebman, 1993 abstract](https://pubmed.ncbi.nlm.nih.gov/7584354/).

Represent resource reservations as tokens. Job admission consumes capacity; completion or cancellation returns it through a defined transition. For a fixed reservation pool, require:

```text
free tokens + reserved tokens + active tokens + retiring tokens = capacity
```

A transition must not count the same token in two states. GPU completion and the last reader release can be separate prerequisites for returning a buffer token. This makes cancellation leaks, double release and premature reclamation visible. It can also feed the GPU state-exploration proposal.

The invariant covers the modeled reservation pool, not all physical memory. Conservation alone proves neither progress nor freedom from deadlock. A practical benefit would be reducing unnecessarily conservative global waits while preserving explicit lifetime proofs; compare with the current lease state machine before adding a new formalism.

### P4 Biological adaptation suggests controlling response time under disturbance

Yi and colleagues connect robust adaptation in a bacterial chemotaxis model to integral feedback under stated assumptions. The relevant transfer is the mechanism of correcting sustained error, not the biological label. [Yi et al., PNAS 2000](https://pmc.ncbi.nlm.nih.gov/articles/PMC18287/).

A development service could target interactive response time while changing background admission slowly, using PSI and measured completion times. Use separate timescales for immediate cancellation and slower memory/prefetch policy. Saturation, delayed measurements and integral windup require ordinary control-engineering treatment.

Gaia's earlier [feedback policy lost to fixed batching](../science/prospects.md). This proposal is worth testing only under changing contention where fixed limits demonstrably fail. Compare with a static cap, hysteresis and a simple damped controller before any richer policy. Measure settling, overshoot, useful latency and starvation.

### P5 Choose experiments for information gained per unit cost

ENTROPIC treats fuzzing as learning about program behavior and uses information measures to guide seed energy. Delta debugging systematically reduces failure-inducing inputs. These supply more concrete foundations than a general appeal to entropy. [ENTROPIC authors' CACM account](https://mboehme.github.io/paper/CACM23-entropic.pdf), [Zeller and Hildebrandt, 2002](https://www.cs.columbia.edu/~junfeng/08fa-e6998/sched/readings/delta-debug-input.pdf).

For Gaia, choose the next test, configuration or reduced reproducer by the hypotheses it can distinguish relative to its execution cost. A short test that separates two plausible causes may accelerate development more than a large batch repeating familiar behavior. Shared prepared state could make these discriminating experiments cheap to run.

Information gain is a proposed ranking objective, not a correctness certificate. Flaky outcomes, invalid reductions and biased failure histories need explicit handling. Delta debugging generally gives a local minimality guarantee under its test model, not the globally smallest cause. Compare against existing test ordering and reduction tools using time to a reproducible explanation, not raw test throughput.

## Combinations with the highest value to investigate

| Proposed combination | Development benefit | First useful comparison |
| --- | --- | --- |
| Relevance index plus exact source generations | Find relevant code, docs and previous failures faster | Lexical/symbol search, CPU inference and optional NPU inference on held-out tasks |
| Prepared test branches plus failure memory and minimization | Turn a failure into a compact reproducible explanation | Existing batched tests and corpus minimizers, with equal isolation and compute budgets |
| PSI plus declared user demand | Keep the current edit responsive during builds and indexing | Fixed concurrency, cgroups and ordinary priority queues |
| Resource invariants plus state-space exploration | Find lifecycle bugs before integrating more concurrency | CPU model checking and current lease tests before GPU offload |
| Stable coverage/trace representation plus repeated GPU queries | Answer more debugging questions without rebuilding indexes | CPU bitsets, sparse kernels and DuckDB including ingestion |
| fs-verity plus immutable dependency packs | Avoid repeated eager verification of untouched content | Existing verified chunks and ordinary file caching |

The first checks should establish a useful software mechanism on the CPU where possible. The accelerator question then becomes whether a compatible device improves complete-operation latency, CPU availability or total energy under the same output contract. Count shared power, memory bandwidth and thermal contention; an idle accelerator does not imply free work.

The existing [hardware results](../../experiments/science/workflows/devices/results/REPORT.md) establish one AMD/D3D12 compute path and a negative sparse-traversal comparison. They do not establish NPU availability or compatibility with CUDA-based references. Kernel configuration, delegated controls, filesystem support and host/container visibility likewise need checking before implementation.

Source scope: the adaptive-mesh publisher abstract and metabolic-network abstract support only their described mechanisms; neither full paper was used to derive Gaia correctness claims. All application hypotheses above need independent validation.
