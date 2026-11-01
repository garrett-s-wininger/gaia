# Architectural experiments after the compiler-policy boundary

The [backend-policy study](backend-policy.md) establishes a compile/runtime tradeoff using existing settings. Further flag selection is outside this research direction. The next experiment should change the computation, the unit of reuse, or ownership across tools, and demonstrate a benefit beyond a competent existing implementation.

The following began as research proposals, not implementation commitments. The first now has a [measured continuation](delta-analysis.md): retained native source facts and consumer caching improve the tested Python tooling response; the extra maintained proof graph does not establish an overall win. The branched-execution proposal now also has a [real Django test-state experiment](branched-tests.md): native reuse remains competitive, with a separate warm-worker isolation limit. The discovery and deeper compiler proposals remain unmeasured here. They return to the original question: which options become available when the substrate owns source generations, tool lifetimes, observations and execution effects together? The primary sources were checked on 31 October 2026. Their published results are evidence for mechanisms in their own domains, not forecasts for Gaia.

## First choice: maintain analyses from changes

**Experimental outcome:** [Django navigation and a real forbidden-dependency rule](delta-analysis.md) validate 336 responses. Retained native processing reduces summed request time by 57.47% against the cached-library path; adding proof maintenance is 1.75% slower by paired median and does not establish an overall improvement. The follow-up [native-reference experiment](import-rebinding.md) addresses source resolution across module membership changes: an observation index plus scoped native parsing cuts its tested trace by 42% against full rescans; retaining complete references adds no established overall gain. The proposal below records the original question and acceptance boundary.

**Connection:** incremental database theory, digital signal processing and programming-language analysis.

DBSP models database changes as streams and derives incremental implementations of rich queries, including recursion and aggregation. Its mathematical construction is inspired by digital signal processing and uses a difference operation on suitable data domains. This supplies a precise alternative to merely marking an answer stale and rerunning its entire computation. [Budiu et al., PVLDB 2023](https://www.vldb.org/pvldb/vol16/p1601-budiu.pdf).

**Gaia hypothesis:** a source generation produces changes to semantic facts; navigation and a supported diagnostic update their derived results from those changes. An edit that changes an import should update the affected bindings and dependency-rule results without every consumer rebuilding its project graph. An edit that changes only locations should not automatically recompute unrelated semantic relations.

The mathematical target is the change in a query result, `Q(F + ΔF) − Q(F)`, where `F` is the admitted fact collection. Maintaining that change can cost less than recomputing `Q(F + ΔF)`. This does not imply that every small edit has a small effect: a widely used declaration or configuration change can legitimately affect most of the project.

**First experiment:** one language, an existing semantic producer, import/dependency navigation and one real dependency-policy diagnostic. Feed initial facts and subsequent additions/deletions into an incremental query engine. Exercise ordinary edits, import retargeting, removed exports, newly appearing modules and branch changes. Compare both answers against fresh authoritative recomputation after each edit.

The strong performance control is the language service/linter's existing combined or incremental mode with caches enabled. Charge initial production, discovering deltas, emitting/receiving facts, maintenance, first-demand delay and retained state. A native API already sharing equivalent work is a successful control, not something to omit.

**What makes this different from the failed compact-graph experiment:** that prototype constructed another graph and cached answers until a whole function was invalidated. This proposal changes how an invalidated answer is maintained. It must reduce executed analysis work after a real change, rather than accelerate a traversal that a good result cache can avoid anyway. Duplicating LLVM's maintained structures is not part of this proposal.

Continue only if the complete edit-to-correct-navigation-and-diagnostic operation improves. Stop if the producer rebuilds or reexports so much state that it consumes the saving, or if existing incremental services already do the same work more efficiently. Implementing a simplified parser or a weaker rule does not establish an equivalent linter improvement.

## Second choice: branch initialized execution state

**Experimental outcome:** [real django-todo requests](branched-tests.md) validate 350 timed operations. Forked runtime/fixture branches cut 28.72% against fully fresh runs, but only 2.35% against native database reuse with mixed block outcomes. Warm reuse cuts 20.21% against native database reuse under a narrower contract; a separate successful-mutation diagnostic exposes its heap leak. The proposal below records the original question.

**Connection:** database snapshot isolation, virtual-memory copy-on-write, effect tracking and fuzzing systems.

SnapFuzz combines late safe snapshot placement, controlled communication and an in-memory filesystem to remove repeated setup and cleanup in network fuzzing. Faasm combines software-fault isolation, shared memory and restoration from initialized snapshots in serverless execution. These are examples of changing an execution boundary across memory and external resources. Faasm itself still exposes a POSIX host interface; it is not evidence for a POSIX-free design. [Andronidis and Cadar, ISSTA 2022](https://srg.doc.ic.ac.uk/files/papers/snapfuzz-issta-22.pdf), [Shillaker and Pietzuch, USENIX ATC 2020](https://www.usenix.org/conference/atc20/presentation/shillaker).

**Gaia hypothesis:** runtime loading, stable application initialization and fixture preparation produce an initialized versioned state. Tests or tool requests branch from it, receive private writable state and explicitly bound external resources, then discard their branch. The substrate owns the relation between a snapshot, its source/configuration inputs and the effects a branch can perform.

This is more than retaining a warm process. A warm worker preserves mutations between requests unless it resets them. A reusable initialized state must reproduce the appropriate starting state and external-resource conditions. Copying memory alone does not restore shared file offsets, database connections, background threads or network peers.

**First experiment:** choose a real application whose initialization/setup dominates its existing test loop. Retain its test runner and compare fresh execution, a competent warm worker or forkserver, prepared fixture cloning/rollback, and a branched initialized state. Include a failing test, interrupted cleanup, source/configuration invalidation and external writes. Charge construction, restoration, resource rebinding, private dirty pages and teardown.

The research contribution would be a reusable boundary that composes memory with controlled effects and current source identity. Simply enabling `fork()` or demonstrating the existing SQLite backup speedup again would not answer that question. Gaia's [prepared-test study](../testing/findings.md) already supplies those simpler controls.

Continue only when isolated complete test operations improve without state leakage or excessive retention. If a mature forkserver or existing fixture API captures the whole gain, reuse that mechanism rather than inventing a competing runtime.

## Discovery route: preserve file structure across changing contexts

**Connection:** scope/stack graphs, formal name-resolution rules and content-addressed reuse.

Stack graphs construct file-local binding information without visibility into the rest of the program, then resolve names by combining those pieces. Their construction and resolution support reuse of previously seen file versions, and their syntactic extraction does not require running a package's build process. [Creager and van Antwerpen, Stack graphs](https://arxiv.org/abs/2211.01224).

**Gaia hypothesis:** source discovery becomes useful before a project builds, and unchanged dependency/file structure survives branch switches or workspace imports. Source bytes identify a reusable local fragment; current import/export/visibility context determines which answers can be assembled from it. This separates reuse of a file's structure from reuse of a particular binding answer.

**First experiment:** an unfamiliar real repository, a branch switch, an unsaved import edit and a changed dependency. Measure first correct navigation and subsequent update latency using file-local fragments and contextual resolution. Compare an existing stack-graph implementation, the language server's current incremental index, and lexical search for the queries it can answer. Validate the supported semantic subset with the authoritative language tool; preserve unsupported and ambiguous outcomes.

This does not promise complete compiler semantics from syntax for arbitrary macros, overloads, generated code or dynamic behavior. Nor is a second index automatically beneficial. It earns its place only if it supplies useful current answers earlier or avoids reconstruction that the existing provider actually performs. It could provide inputs to the first proposal, but the two mechanisms need separate cost accounting.

## A deeper compiler route, if returning to compilation

An architectural alternative is to compile/materialize executable units only when the requested test reaches them and to reuse unaffected units across source generations. LLVM ORC already provides lazy materialization and resource tracking, so it is a starting control. It does not by itself provide safe semantic invalidation across edits or reset arbitrary running-program state. [ORC design](https://llvm.org/docs/ORCv2.html).

The potential saving is omitted compilation and executable-wide work. The difficult contract includes dependencies introduced by inlining, globals, initialization, ABI/debug metadata and old code still executing. Emitting and linking machine code still require relocation/materialization work; using a JIT does not make those obligations disappear. This route is substantially deeper than compiler flags and should have its own bounded target, not be treated as the next tweak to the completed benchmark.

## Scope and selection

The [compiler integration](../integration/generalization/README.md) measures shared Clang observations, result reuse and backend scheduling. Delta-maintained source analysis, initialized test state and discovery without build-dependent preparation have separate consumers and validation requirements.

My first choice is delta-maintained navigation plus one real diagnostic: it directly connects the requested source-discovery experience with replaceable tool internals and a mathematical transformation of the work. Branched execution state is the next choice if the priority is a broader test/runtime boundary. Both need competent native controls from the outset.

GPU/NPU selection should follow a demonstrated computation with suitable batching, residency and semantics. A device backend for a useful maintained relation or retrieval model can be a later experiment; accelerating another isolated traversal would repeat a boundary already tested negatively. No numerical improvement is predicted for these proposals.
