# Questions worth pursuing first

These are possible follow-ups to the [connection map](README.md), not implementation commitments. Priority reflects the quality of the question, its connection to existing Gaia evidence and the availability of a competent control. No numerical speedup is predicted.

The [development-loop extension](development-loop.md) also considers code discovery, test prioritization, reproducible debugging, kernel resource controls and accelerator uses beyond compilation.

The expanded scope makes [source discovery](source-discovery.md) a primary user-facing workload and permits [internal tool replacements](tooling-internals.md). Questions 7 and 8 make those additions concrete; a shared language service serving discovery and one real diagnostic/compiler consumer is now the preferred first slice of question 1.

## 1 Can several consumers share demanded facts and their derivations

Combine demand-driven computation, relational deltas and provenance: connections [1](connections.md#1-demand-is-an-input), [2](connections.md#2-changes-can-have-their-own-compiled-programs) and [3](connections.md#3-retain-why-a-result-exists).

Use the existing [dynamic observation work](../science/graphs/README.md) and [production build graph](../compiler/followthrough/README.md) as starting evidence. The missing link is a real second consumer, such as editor dependency feedback or test selection, with independently changing demand.

The decisive comparison would hold the admitted source generations and output contracts constant across independent incremental consumers, a shared eager fact store and a shared demanded store. Trace positive inputs, missing lookups, shadowing, configuration changes and demand withdrawal. A full recomputation oracle should check each published demanded result. Include a filesystem adapter's discovery cost when that adapter is part of the operation.

The question is whether less work is executed over a session while current feedback remains fast. Report maintenance CPU, first-demand latency, memory and obsolete work separately. Stop if a mature combined API already captures the saving, or if tracking every fine-grained fact costs more than the eliminated work. A flat dependency set is the baseline before symbolic provenance.

## 2 Is there a valuable structural reuse layer

Combine sparse symbolic analysis and subdivision topology with schedule separation: connections [4](connections.md#4-separate-structural-plans-from-changing-values) and [5](connections.md#5-separate-meaning-from-execution-policy).

First inspect real edit histories for two distinct change classes: values within a stable observed graph, and changes to the graph or its interpretation. Candidate retained objects include reverse dependency indexes, query plans and consumer binding plans. Start by measuring their construction cost; an elegant separation has little performance value if that cost is tiny.

Compare full plan reconstruction with a retained plan whose structural guard includes relevant configuration and dynamic observations. Existing exact-input and IR caches remain enabled in both arms. Preserve an oracle for graph reconstruction and ordinary output checks for execution. A source edit can reuse the plan while requiring new compilation.

Continue only if savings survive guard construction, first readiness, configuration changes and plan invalidation. Stop on any missed structural change. OpenSubdiv and numerical solvers establish that this separation can be productive in their domains; they do not establish that build-plan construction is a Gaia bottleneck.

## 3 Can views cross ownership boundaries without expensive reconstruction

Combine bounded batches, complements, lifetime analysis and device completion: connections [8](connections.md#8-a-shared-view-may-need-a-private-complement) through [11](connections.md#11-a-buffer-handoff-is-an-ownership-and-completion-contract).

Choose one real producer and two readers of diagnostics, dependency facts or a resolved catalogue. Compare a native combined API, separate serialized results, shared borrowed views and copied compact batches. Define which metadata each reader requires and whether exact regeneration is part of the contract. Exercise delayed readers, generation replacement, cancellation and a failed consumer.

The useful result would be lower total conversion CPU or physical memory with equivalent complete-operation latency and correct release. Account for producer memory, mappings, temporary allocations and retired generations. Logical payload size and the sum of process RSS are insufficient measures of physical saving.

Stop if retaining a whole generation costs more than copying a small projection, or if the current native consumer interface already borrows the relevant data. Device interoperability is an optional later extension once a real device consumer exists; a CPU demonstration should not claim it has solved device fences.

## 4 Does a better communication model change placement

Combine hypergraphs, sparse kernels and lifetime-based storage: connections [15](connections.md#15-model-shared-inputs-as-hyperedges) through [18](connections.md#18-group-persistent-data-by-lifetime-as-well-as-access).

Gaia already found that [ordinary clustering beats the tested force layout](../science/data/findings.md). The new question is whether the objective was incomplete: one shared datum can have many consumers, while its lifetime can differ from nearby data.

Use train-only access and update traces, then evaluate unseen sessions with a shifting hot set. Compare the existing layout, static clustering, a byte-weighted hypergraph partition and lifetime groups. Separate read locality from reclamation; improve one without hiding damage to the other. Charge index construction, partitioning, migration, duplicated bytes and pack rewrite volume.

Start with application-level traffic and reclamation. Actual device claims need a separate device boundary and telemetry. Stop if partition construction takes longer than its useful lifetime or if simpler static groups achieve the same result. A sparse-library experiment is useful only if retained queries amortize representation conversion.

## 5 Can shared resources remain responsive under mixed demand

Combine budgeted event processing, owned mutable state, resource vectors and local policy: connections [12](connections.md#12-amortize-event-handling-with-bounded-service) through [14](connections.md#14-allocate-resource-vectors-instead-of-worker-slots), and [20](connections.md#20-share-accounting-while-leaving-policy-near-consumers).

Use a mixed session with editor requests, native compilation, a managed compiler and artifact access. Existing [queued cancellation](../science/workflows/findings.md) and [soft memory admission](../java/followthrough.md) provide starting controls. Compare fixed worker counts, a memory gate, and a simple vector-aware admission policy with the same declared interactive reservation.

Measure current-result latency, queue delay, completed bulk work, memory peaks, idle CPU and starvation. Attribute shared resources once. Keep interruptibility explicit; admission cannot make an already-running compiler preemptible. A replay can compare policies, but real overlapping processes are needed to establish interference and memory behavior.

Continue if responsiveness improves without unacceptable bulk regression or accounting overhead. Stop if a fixed cap and priority queue work equally well. The social-theory link is a question about where decisions belong, not evidence for any scheduling algorithm.

## 6 Is there a genuinely reusable device-resident pipeline

Combine structural reuse, buffer completion and wavefront grouping: connections [4](connections.md#4-separate-structural-plans-from-changing-values), [11](connections.md#11-a-buffer-handoff-is-an-ownership-and-completion-contract) and [22](connections.md#22-offload-a-resident-pipeline).

This follows the [actual D3D12 traversal result](../../experiments/science/workflows/devices/results/REPORT.md), where native CSR won. Identify multiple useful operations that naturally consume the same representation before final readback. Do not manufacture repetitions solely to amortize launch costs.

Compare the whole sequence against optimized CPU execution, including native sparse algorithms and an established library where appropriate. Charge capability initialization, initial upload, updates, temporary and retained memory, synchronization and final readback. Verify exact results where the operation requires exactness. Backend compatibility must be established independently of the cited renderer.

Stop if no natural workload provides enough work per transfer, or if the CPU pipeline wins at all realistic sizes. NPUs, codec engines, storage offload and other devices remain leads only when an actual operation, usable API and equivalent baseline can be named.

## 7 Can source discovery make shared semantic work valuable immediately

Join current text/structural search, contextual semantic facts and test/failure evidence. Compare a retained producer serving navigation and one real diagnostic consumer with the language service's existing combined mode. Include first open, unsaved incomplete edits, exported-name changes, newly appearing imports, configuration changes and branch switches. The [discovery study](source-discovery.md#first-comparisons) defines the detailed comparisons.

Measure time to a correct useful action, first partial answer, complete answer, stale-result exposure, update work and retained memory. Reference correctness needs a fresh authoritative control for the supported language/configuration scope. Stop if the exported facts do not support a real second consumer or mature native sharing already captures the benefit. Optional embedding relevance must improve held-out discovery tasks before device offload is relevant.

## 8 Which internal replacement improves the complete development session

Compare competent existing tools, shared-input integration using those tools, and one selected internal replacement. Candidate boundaries include semantic query invalidation, lint analysis, code generation, linking, runtime preparation and memory management. The [tooling study](tooling-internals.md#a-comparison-that-can-reveal-a-holistic-benefit) specifies a session that joins discovery, editing, diagnostics, testing and debugging.

Preserve the requested capability set, language semantics and relevant tooling behavior. Charge preparation, retained state, recovery and migration/maintenance effort. Report human/agent task success separately from CPU, latency and memory. Continue only if the replacement adds material value beyond integration alone; stop if omitted checks, worse generated-code execution or compatibility gaps explain the apparent saving.

## How to decide between these questions

Start with the first three through the discovery workload in question 7, using question 8 to distinguish the benefit of ordinary integration from internal replacement. They connect measured Gaia strengths to mechanisms that could remove repeated work across consumers. Placement and resource-policy questions require longer mixed traces. Device residency depends on finding a suitable workload first. Equality saturation should wait until repeated workflow choices are concrete enough to supply a small valid algebra and a measured cost model.

Keep useful latency, CPU, physical memory, storage/network traffic and preparation cost as separate outcomes. A single weighted score is optional and requires declared weights. Report cold readiness and subsequent session behavior separately. Reuse opportunities often compete for the same memory or remove the same work, so gains from separate experiments cannot be added.

The purpose of this pass is to identify productive links. A cheaper explanation of an existing negative result is also a worthwhile outcome; it need not produce a new subsystem.
