# Replaceable compiler, language-tool and runtime internals

Status: exploratory synthesis, 31 October 2026. The user is willing to consider replacing implementations and internal components of compilers, runtimes, linters and language tooling when the holistic benefit is substantial. This expands the research space beyond wrappers around existing commands. It does not select a replacement or change Gaia's implementation language.

The strongest question is which component can expose or preserve useful work for several consumers. A faster isolated executable is also valuable, but a component that shares project interpretation, semantic results or execution evidence could improve discovery, editing, validation and tool development together. The companion [source-discovery study](source-discovery.md) supplies the user-facing workload.

## T1 Use a language service as the reusable frontend

Roslyn exposes syntax, symbols, semantic analysis, diagnostics and emission through compiler APIs; its workspace model provides immutable solution/project/document snapshots. These are concrete examples of compiler knowledge serving editor and analysis tools. [Compiler API model](https://learn.microsoft.com/en-us/dotnet/csharp/roslyn-sdk/compiler-api-model), [workspace model](https://learn.microsoft.com/en-us/dotnet/csharp/roslyn-sdk/work-with-workspace).

**Gaia hypothesis:** a retained per-language provider consumes admitted source/configuration changes and serves navigation, selected diagnostics and compilation from eligible shared state. Choose the sharing boundary around what that implementation can safely retain. Export small immutable projections for consumers that need to outlive the frontend context.

Gaia's [Clang follow-through](../compiler/followthrough/findings.md) already shows why this needs a strong control: shared parsing reduced sampled CPU, while independent warm workers delivered similar latency. Its AST consumers were sequential because mutable/lazy Clang state was not safe to share concurrently. A product question needs a real linter or navigation consumer, cancellation, an unsaved edit and bounded retention.

Compare the provider's mature combined API before modifying its internals. A combined service should also avoid making a long diagnostic request block completion or navigation. Per-language sharing can be useful even when different languages remain in separate processes.

## T2 Replace coarse invalidation with stable semantic projections

rustc's query system distinguishes changed inputs from changed query results; its incremental design also describes projection queries that prevent a changed large result from invalidating every consumer. rust-analyzer separates function-body data from more stable item/module structure and makes semantic context dependent on the crate configuration. [rustc incremental queries](https://rustc-dev-guide.rust-lang.org/queries/incremental-compilation.html), [projection queries](https://rustc-dev-guide.rust-lang.org/queries/incremental-compilation-in-detail.html), [rust-analyzer architecture](https://rust-analyzer.github.io/book/contributing/architecture.html).

**Gaia hypothesis:** navigation, lint and compilation depend on the narrow projection they actually consume. Changing a function body may alter body diagnostics and code generation while preserving an exported-name summary. Comment edits may preserve some semantic results while changing documentation and every following source location. These are distinct projections with distinct validity conditions.

Retrofitting this into a compiler is deeper work than adding a cache. Swift's request-evaluator document describes a gradual migration toward tracked requests while acknowledging remaining mutable AST state. It is a useful model for evaluating how much internal restructuring is required. [Swift request evaluator](https://github.com/swiftlang/swift/blob/main/docs/RequestEvaluator.md).

Start with one measured expensive projection. Count dependency tracking, equality checks, serialization and retention. Hidden environment or plugin state can invalidate the premise. Gaia's [unsafe AST fingerprint findings](../compiler/findings.md#source-changes-and-object-changes-are-different-boundaries) remain relevant: unchanged exported names do not prove unchanged machine code. A fact's validity cannot be promoted to a stronger artifact identity.

## T3 Replace a collection of lint tools with shared analysis where coverage matches

Oxc's documented linter flow parses source, builds semantic information and supplies a shared lint context to rules. Biome documents a project scanner, recoverable concrete syntax and a daemon serving CLI/editor requests. Ruff's native server exposes diagnostics, fixes and formatting, while its documentation directs navigation/completion to a companion language server. [Oxc linter architecture](https://oxc.rs/docs/learn/architecture/linter), [Biome architecture](https://biomejs.dev/internals/architecture/), [Ruff editor integration](https://docs.astral.sh/ruff/editors/).

**Gaia hypothesis:** replace repeated project scanning, parsing, scope construction and transport across a chosen family of rules with one implementation that exposes reusable results. This could also make third-party rules easier to write against declared facts. A syntax-preserving edit representation can connect lint fixes to formatting and source discovery.

The replacement unit must include actual rules, suppressions, configuration precedence, plugins and fix behavior. A faster tool that omits required checks performs different work. Some style checks need only syntax; type-sensitive rules may need the language checker; whole-program checks may benefit from the [relational analysis route](source-discovery.md#d6-turn-the-index-into-a-substrate-for-executable-analyses).

Compare against existing combined commands and resident language servers. Do not assume all of the cited projects share one semantic model, or that one server already handles every capability. The research target is the missing duplicated work after their own optimizations are enabled.

## T4 Choose code generation for the expected life of the result

Wasmtime exposes a compilation-speed/code-quality tradeoff through Winch and Cranelift. Rust's `rustc_codegen_cranelift` is an actual alternative backend integration. These are examples of replaceable code generation at particular language/IR boundaries, not interchangeable backends for every compiler. [Wasmtime fast compilation](https://docs.wasmtime.dev/examples-fast-compilation.html), [fast execution](https://docs.wasmtime.dev/examples-fast-execution.html), [rustc Cranelift backend](https://github.com/rust-lang/rustc_codegen_cranelift).

**Gaia hypothesis:** an artifact used for a few quick tests may favor cheaper code generation; stable dependencies or frequently executed tests may repay optimization. Under a simplified serial model, a more optimizing backend wins when:

```text
extra compilation time < expected executions before invalidation
                         * execution time saved per run
```

This is a decision model, not a measured crossover. Include linking, loading, preparation and instrumentation in the actual comparison. Background optimization consumes resources and can interfere with requested work; prediction error and invalidation can erase its value. The broader research on baseline compilers examines this tradeoff directly. [Titzer, Whose baseline compiler is it anyway?, 2023](https://arxiv.org/abs/2305.13241).

Do not assume automatic tier migration: Wasmtime's platform documentation explicitly says modules do not automatically transition from Winch to Cranelift. Gaia would need a separate policy and, for live replacement, a correct state-transfer mechanism. Choosing a backend for the next execution is a simpler question. [Wasmtime compiler support](https://docs.wasmtime.dev/stability-platform-support.html#compiler-support).

Validate target support, ABI, exceptions/unwinding, debug information, sanitizers, intrinsics and the intended optimization semantics. Different backends need not emit identical bytes. Define behavioral and tooling compatibility separately, while retaining exact-byte checks when testing reuse under one pinned backend. Faster compilation that makes the test run or debugging session much slower may lose overall.

## T5 Treat linking, loading and executable lifetime as separate replacement points

mold is an alternative Unix linker. LLVM ORC supplies JIT materialization and resource-tracking interfaces, including removable code. They address different boundaries: producing an executable versus making code available within an execution session. [mold project](https://github.com/rui314/mold), [ORC design](https://llvm.org/docs/ORCv2.html).

**Gaia hypothesis:** first compare existing linkers on a workload where linking matters. For repeated bounded test kernels, separately examine whether retained loaded dependencies or demand materialization can avoid repeated executable preparation. A versioned code handle could connect execution back to the exact source and compiler context that produced it.

JIT resource removal does not prove that application threads or function pointers have stopped using the code. Globals, TLS, constructors, exception metadata, native extensions and external resources complicate both hot replacement and test reset. Replacing code is not equivalent to migrating live object layouts. This connects to [ownership and completion](connections.md#11-a-buffer-handoff-is-an-ownership-and-completion-contract), with execution quiescence as an additional requirement.

Compare with a fast ordinary linker and fresh test process before introducing a persistent executor. Preserve debugger and failure behavior. The existing Gaia result that direct object buffers alone provided little benefit is a reason to measure this boundary first, not evidence against all linker/runtime changes.

## T6 Share prepared metadata before sharing mutable runtime objects

Gaia already has relevant evidence: [Python dependency loading](../python/dependency-formats.md) benefits in some cases from prepared compact metadata, while [Java compiler prospects](../compiler/jvm/prospects.md) distinguish immutable platform data from mutable task-bound symbols. The [interpreter-state experiments](../python/interpreter-state.md) show both useful preparation and a complete TypeScript command where the stock compile cache beat a custom snapshot.

**Gaia hypothesis:** source discovery, type loading and runtime module discovery can use prepared views of the same pinned dependency inputs. Share names, declarations, source maps or module catalogues where meanings match. Bind those records into fresh mutable compiler/runtime contexts when required.

An index for source navigation and a runtime loader do not necessarily agree on resolution: type stubs, conditional exports, class loaders, search-path order and dynamic imports can select different entities. Preserve the mapping and context rather than treating a symbol catalogue as an executable module table. Shared byte storage also does not establish shared GC ownership.

Compare producer cost, cold admission, first useful lookup, full tool readiness and later requests. Keep stock caches enabled. Prepared metadata is promising when many consumers reuse a large stable dependency set; it can lose when only a small fraction is touched or decoding a second format adds work.

## T7 Consider runtime replacement for specialization and observability together

Truffle derives optimized execution from interpreters designed for partial evaluation, with explicit specialization and invalidation. Its instrumentation research also makes debugging, profiling and analysis events part of the runtime framework. This connects language implementation reuse with developer-tool reuse. [Truffle partial evaluation](https://www.graalvm.org/dev/graalvm-as-a-platform/language-implementation-framework/PartialEvaluation/), [Van De Vanter et al., instrumentation research, 2018](https://arxiv.org/abs/1803.10201).

**Gaia hypothesis:** a replaceable runtime for a bounded tool or language subset could expose execution evidence and source identity directly while specializing stable rules, project configuration or repeated workloads. A linter/query interpreter is a more contained candidate than an arbitrary application ecosystem. The same machinery might reduce the work of implementing profilers and debugging support.

A generic interpreter does not acquire these properties merely by changing its launcher. Runtime semantics, native extensions, FFI, introspection, threading and packaging may dominate migration cost. Warm-up and compiled-code retention may make a short-lived tool worse. Compare the complete existing runtime with its caches and prepared-worker options before adopting a new VM.

Record two separate potential benefits: faster complete user tasks, and less work to implement high-quality language tools. A runtime can improve one while worsening the other. Neither benefit is established for Gaia by the cited framework.

## T8 Make memory management a replaceable implementation concern

MMTk separates reusable memory-management machinery from VM-specific bindings. Its binding interface includes object-model, scanning, collection, reference and slot abstractions. This supplies an actual research path for collector/runtime integration rather than treating GC as an inseparable black box. [MMTk](https://www.mmtk.io/), [VM binding interface](https://docs.mmtk.io/api/mmtk/vm/trait.VMBinding.html).

**Gaia hypothesis:** compiler and index workloads have recognizable lifetimes—short request temporaries, immutable source generations, retained dependency facts and warm executable code. Use that information to evaluate request arenas, separate retained stores, different collectors or targeted runtime integration. Correctly isolating a lifetime may remove tracing or retention work across several tools.

Bulk reclamation is valid only when no live references escape the region. A collector swap requires correct root scanning, barriers, safepoints, object movement and native-reference behavior; a VM binding is substantial implementation work. Start with lifetime accounting and existing allocator/collector settings before changing a runtime.

The [Java queue results](../java/followthrough.md) already show that heap-used is a poor proxy for resident memory and that the fastest collector configuration need not use the least memory. Measure long sessions, physical sharing, pauses and foreground response under a fixed resource budget. An empty reported heap does not prove that retained processes are cheap.

## Boundaries to keep explicit while permitting deep replacements

| Boundary | What could change | What must remain reviewable |
| --- | --- | --- |
| Project discovery and input access | Scanners, package metadata readers, filesystem adapters | Visible namespace, configuration precedence and observed inputs |
| Syntax and semantic service | Parser, checker, query engine, selected IRs | Language/version coverage, incomplete-source behavior and fact validity |
| Diagnostics and transformations | Lint implementation, rule engine, formatter integration | Required checks, suppressions, fix semantics and source mappings |
| Code generation and linking | Backend, optimization policy, linker | Target/ABI behavior, debug support, artifact identity and execution results |
| Execution | Loader, interpreter, JIT, prepared worker | Language semantics, native integrations, reset and failure behavior |
| Storage and memory | Fact layout, allocator, collector, retention policy | Ownership, reclamation, physical cost and bounded foreground interference |

These interfaces permit deep per-language integration without requiring a universal AST or one mutable heap. APIs and schema adapters can be versioned at a narrow boundary. Forking a tool is a possible research route, but its upstream compatibility and ongoing maintenance cost belong in the adoption decision.

## A comparison that can reveal a holistic benefit

Use one realistic sequence: open a project, find an implementation, inspect references, edit it, obtain diagnostics, apply a fix, run a relevant test, inspect a failure and switch branches. Include source/configuration errors and cancellation. Run under the same memory budget and with the same requested capabilities.

Compare three arrangements:

1. **Competent existing tools:** their supported resident modes, combined commands and caches enabled.
2. **Shared inputs and coordination:** retain those tool implementations but remove repeated admission and redundant requests where their interfaces allow it.
3. **Selected internal replacement:** change one identified parser, analysis service, backend or runtime boundary while keeping the other improvements enabled.

This separates the value of the replacement from gains available through ordinary integration. Record first readiness, current diagnostic/navigation latency, complete test feedback, aggregate CPU, retained physical memory and obsolete work. Measure discovery task success as well as tool throughput. Preparation, recovery and shutdown are part of the session.

For a semantic replacement, use differential results and language conformance cases at the affected boundary; diagnostic differences need explanation, not automatic acceptance or rejection based on message text. For a new linter, map required rules explicitly. For a runtime/backend, verify actual programs and tooling behavior. Do not declare whole-language equivalence from a small successful fixture.

## Priority after expanding the scope

| Priority | Research target | Why it is informative now |
| --- | --- | --- |
| First | Source discovery plus one genuine diagnostic consumer sharing language facts | Direct user benefit and a concrete replacement for the prior detached-name surrogate |
| First | Stable dependency metadata used by both discovery and a language tool | Connects existing admission/index evidence to another real consumer |
| Next | Semantic projection reuse across realistic edits | Tests whether internal compiler changes remove work that input/result caches cannot |
| Next, when profiling supports it | Backend/linker choice for complete edit-test cycles | Actual replaceable implementations and a measurable lifetime tradeoff |
| Deeper research | Runtime specialization, instrumentation and memory-management integration | Potentially broad benefits, with larger compatibility and maintenance costs |

The most compelling initial slice is **a local source-discovery experience backed by a retained language service, with one real linter/checker or compiler consumer of the same eligible facts**. It exercises the user's two additions together and makes the benefit assessable before committing to broader runtime replacement.
