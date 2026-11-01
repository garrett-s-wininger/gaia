# Historical and implementation reading routes

Sources were consulted on 31 October 2026. Dates below refer to the original work or the explicitly identified version, not a search engine's crawl date. Paper copies, author material and official project documentation support the mechanisms; the proposed Gaia applications are in [the connections](connections.md).

## Historical research by question

| Work | Useful question | Read |
| --- | --- | --- |
| Coase, 1937, Economica | At what point does internal coordination cost more than the transactions it removes? | [The Nature of the Firm](https://onlinelibrary.wiley.com/doi/10.1111/j.1468-0335.1937.tb00002.x) |
| Cousot and Cousot, POPL 1977 | Which cheap approximation is sound for the decision being made? | [Author summary and paper](https://www.di.ens.fr/~cousot/COUSOTpapers/POPL77.shtml) |
| Lampson, 1983 | Which interface and implementation choices preserve performance and flexibility? | [Hints for Computer System Design](https://www.cs.tufts.edu/~nr/cs257/archive/butler-lampson/Hints%20for%20computer%20system%20design.html) |
| Cook, Carpenter and Catmull, SIGGRAPH 1987 | Can a common working representation preserve locality across diverse inputs? | [The Reyes Image Rendering Architecture](https://www.cs.cmu.edu/afs/cs/academic/class/15869-f11/www/readings/cook87_reyes.pdf) |
| Engler, Kaashoek and O'Toole, SOSP 1995 | Which resource policies can move closer to the application while protection remains shared? | [Exokernel](https://web.stanford.edu/class/archive/cs/cs240/cs240.1236/old/sp2014/readings/exokernel-sosp95.pdf) |
| Frigo, Leiserson, Prokop and Ramachandran, 1999 work expanded in ACM TALG 2012 | Can algorithm structure improve locality across several memory levels? | [Cache-Oblivious Algorithms, 2012 version](https://cs.uwaterloo.ca/~imunro/cs840/frigo.pdf) |
| Foster, Greenwald, Moore, Pierce and Schmitt, POPL 2005 | What information must survive when a shared view omits concrete details? | [Combinators for Bi-Directional Tree Transformations](https://www.cis.upenn.edu/~bcpierce/papers/newlenses-popl.pdf) |
| Green, Karvounarakis and Tannen, 2007 | Can derivations be represented algebraically and maintained alongside results? | [Authors' PrOPr presentation on provenance semirings](https://www.cis.upenn.edu/~plclub/propr/greg-slides.pdf) |
| Ostrom, 2009 | What can be coordinated through multiple centers instead of a single policy hierarchy? | [Author interview with Williamson](https://www.nobelprize.org/prizes/economic-sciences/2009/ostrom/164465-ostrom-williamson-interview-transcript/), [lecture landing page](https://www.nobelprize.org/prizes/economic-sciences/2009/ostrom/lecture/?lbw=1) |
| Williams, Waterman and Patterson, CACM 2009; Williams's later chapter | Is the relevant stage limited by computation or data movement? | [Original publication record](https://escholarship.org/uc/item/78h8v7mr), [author's Roofline chapter](https://escholarship.org/content/qt0qs3s709/qt0qs3s709_noSplash_b958fff358a4aa26695b4dfed9b5a29c.pdf) |
| Ghodsi et al., NSDI 2011 | How should heterogeneous resource demands share capacity? | [Dominant Resource Fairness](https://www.usenix.org/legacy/event/nsdi11/tech/full_papers/Ghodsi.pdf) |
| Ahmad, Kennedy, Koch and Nikolic, PVLDB 2012 | Can maintaining delta queries remove repeated query work? | [DBToaster](https://vldb.org/pvldb/vol5/p968_yanifahmad_vldb2012.pdf) |
| Ragan-Kelley et al., SIGGRAPH 2012 and PLDI 2013 | Which execution choices can vary independently of the algorithm? | [Decoupling Algorithms from Schedules](https://people.csail.mit.edu/jrk/halide12/), [Halide language and compiler paper](https://people.csail.mit.edu/jrk/halide-pldi13.pdf) |
| Hammer, Phang, Hicks and Foster, PLDI 2014 | How should changing demand interact with incremental recomputation? | [Adapton](https://matthewhammer.org/adapton/adapton-pldi2014.pdf) |
| Davis, Rajamanickam and Sid-Lakhdar, 2016 | What structural analysis survives changes to numerical values? | [Sparse direct methods survey, section 4](https://people.engr.tamu.edu/davis/publications_files/survey_tech_report.pdf) |
| Mokhov, Mitchell and Peyton Jones, ICFP 2018 | Which choices govern execution order, and which govern rebuilding? | [Build Systems à la Carte](https://simon.peytonjones.org/assets/pdfs/build-systems-original.pdf) |
| Willsey et al., POPL 2021 | Can a bounded family of equivalent workflows be searched without committing early to one form? | [egg paper preprint](https://arxiv.org/abs/2004.03082) |
| Budiu, McSherry, Ryzhyk and Tannen, 2022 preprint | Can a stream algebra derive incremental forms of rich queries? | [DBSP](https://arxiv.org/abs/2203.16684) |

This is a selected reading route across ACM and related communities, not a complete historical survey. In particular, SIGGRAPH's locality and representation ideas and SIGPLAN's semantic decompositions are being compared as mechanisms; similar mechanisms do not establish a historical line of influence.

## Open source mechanisms to inspect next

The entry points below were identified through project documentation and author descriptions. They are useful starting points for a future code-level study, not pinned implementations that have been built or tested here. Any experiment should record the exact revision it uses.

| Project or subsystem | Entry point | Specific comparison for Gaia |
| --- | --- | --- |
| [Salsa](https://salsa-rs.github.io/salsa/overview.html) | Inputs, tracked deterministic functions and query database | Demand and revision handling versus a shared eager fact store |
| [Adapton](https://www.cs.umd.edu/projects/PL/adapton/) | Original PLDI artifact and demanded computation graph | Observer withdrawal and reuse across changing demand |
| [Halide](https://halide-lang.org/) | `compute_at`, tiled schedules and algorithm definitions | How fusion, recomputation and materialization are separated from meaning |
| [OpenSubdiv](https://opensubdiv.org/docs/far_overview.html) | `TopologyRefiner`, `PrimvarRefiner`, `StencilTable` | Structural identity and reuse across changed values |
| [egg](https://egraphs-good.github.io/egg/egg/struct.Runner.html) | `Runner` limits, rewrite scheduling and domain analyses | Whether planner cost and state growth can be bounded |
| [DuckDB](https://duckdb.org/docs/2.0/internals/vector) | Vectors and data chunks between operators | Batch processing versus one object per fact or whole-table materialization |
| [Apache Arrow](https://arrow.apache.org/docs/format/CDataInterface.html) | Schema/array structures and release callbacks | Borrowing across runtimes within a process; separate IPC is needed across processes |
| [MLIR](https://mlir.llvm.org/docs/Bufferization/) | `BufferizableOpInterface`, One-Shot Bufferize and ownership-based deallocation | How logical values constrain allocation reuse and copies |
| [SuiteSparse GraphBLAS](https://github.com/DrTimothyAldenDavis/SuiteSparse/blob/dev/GraphBLAS/README.md) | Sparse operators, masks and semiring selection | An established native control for repeated graph kernels |
| [Zoltan](https://www.sandia.gov/ccr/software/zoltan/) | Hypergraph partitioning and data-neutral callbacks | Shared-input communication cost versus pairwise layout heuristics |
| [SPDK](https://spdk.io/doc/concurrency.html) | `spdk_thread_poll` and `spdk_thread_send_msg` | Ownership, batching and locality without a globally shared mutable index |
| [Box2D](https://box2d.org/documentation/group__tree.html) | Dynamic tree and broad/narrow collision phases | Conservative candidate generation followed by a stronger check |
| [PBRT](https://www.pbr-book.org/4ed/Wavefront_Rendering_on_GPUs) | `WavefrontPathIntegrator` and work queues | Operation grouping, retained device data and synchronization costs |
| [Linux RCU](https://docs.kernel.org/RCU/whatisRCU.html) | Removal, publication and grace-period reclamation | Correct lifetime separation for old generations |
| [Linux dma-buf](https://docs.kernel.org/driver-api/dma-buf.html) | Export/import, attachments, `dma_fence`, `dma_resv` | Ownership and readiness across asynchronous consumers |
| [Linux NAPI](https://www.kernel.org/doc/html/latest/networking/napi.html) | Receive budget, poll completion and interrupt masking | Bounded service and wakeup amortization |
| [io_uring](https://kernel.dk/io_uring.pdf) | Submission/completion queue model in the original design account | Bulk admission and completion handling; current API details need separate checking |

SPDK's [SSD internals explanation](https://spdk.io/doc/ssd_internals.html) supplies the storage-lifetime analogy. It explicitly uses a simplified device model. Zoltan's [author tutorial](https://cs.sandia.gov/Zoltan/papers/Dagstuhl09.pdf) supplies the communication model behind its implementation entry.

## Source discovery and language implementation routes

The [discovery](source-discovery.md) and [tooling internals](tooling-internals.md) extensions cite their sources next to each mechanism. Particularly useful routes through that literature are:

| Route | Sources | Question connecting them |
| --- | --- | --- |
| Immediate search to contextual navigation | [Zoekt design](https://github.com/sourcegraph/zoekt/blob/main/doc/design.md), [Tree-sitter](https://tree-sitter.github.io/tree-sitter/), [Stack graphs, 2022](https://arxiv.org/abs/2211.01224) | What can be prepared per content/file, and what must resolve in the current context? |
| Semantic facts as shared outputs | [Glean](https://glean.software/docs/introduction/), [SCIP schema](https://github.com/scip-code/scip/blob/main/scip.proto), [clangd indexing](https://clangd.llvm.org/design/indexing) | How do retained facts, live edits, coverage and producer precision fit together? |
| Navigation as an investigation task | [Lawrance et al., IEEE TSE 2013](https://web.engr.oregonstate.edu/~burnett/Reprints/TSE-IFT-2013-asprinted.pdf) | Which cues and routes help a developer find useful evidence? |
| Facts to executable analyses | [Soufflé, CC 2016](https://souffle-lang.github.io/cc-paper), [Roslyn APIs](https://learn.microsoft.com/en-us/dotnet/csharp/roslyn-sdk/compiler-api-model), [Oxc linter](https://oxc.rs/docs/learn/architecture/linter) | Which analyses can share extraction and semantic work? |
| Narrow change propagation | [rustc projection queries](https://rustc-dev-guide.rust-lang.org/queries/incremental-compilation-in-detail.html), [rust-analyzer](https://rust-analyzer.github.io/book/contributing/architecture.html), [Swift evaluator](https://github.com/swiftlang/swift/blob/main/docs/RequestEvaluator.md) | What must change inside a language implementation to preserve unaffected results? |
| Code quality versus iteration time | [Titzer, 2023](https://arxiv.org/abs/2305.13241), [Wasmtime compilation](https://docs.wasmtime.dev/examples-fast-compilation.html), [rustc Cranelift](https://github.com/rust-lang/rustc_codegen_cranelift), [LLVM ORC](https://llvm.org/docs/ORCv2.html) | How much compilation and loading does an artifact's useful lifetime justify? |
| Runtime implementation and tool support | [Truffle instrumentation research, 2018](https://arxiv.org/abs/1803.10201), [partial evaluation](https://www.graalvm.org/dev/graalvm-as-a-platform/language-implementation-framework/PartialEvaluation/), [MMTk bindings](https://docs.mmtk.io/api/mmtk/vm/trait.VMBinding.html) | Can execution, observability and memory management improve together? |

These are documentation and publication studies, not compatibility audits. Moving project documentation needs a pinned revision and implementation inspection before any experiment. The SCIP repository redirected from `sourcegraph/scip` to `scip-code/scip` when consulted. Biome's architecture page describes its scanner, syntax and daemon, but marks its formatter/linter internals as work in progress; the extension does not infer a complete semantic-sharing implementation from those unfinished sections. Wasmtime documentation explicitly rules out automatic Winch-to-Cranelift tier transitions; a Gaia tiering policy remains a hypothesis.

## Source access and scope

The Reyes URL formerly hosted under `graphics.pixar.com` redirects to a general technology page; the university-hosted paper above supplies the original text. OpenSubdiv's current documentation is at `opensubdiv.org`.

Ostrom's interview and lecture information were available as indexed primary-source extracts; direct requests to those endpoints and the lecture PDF returned access errors. Only the interview's discussion of polycentric coordination is used here. No detailed institutional design principle or performance claim is attributed to the unread lecture. The original GraphBLAS paper timed out on direct open; the indexed paper excerpt and project README support the limited semiring/mask description.

The bibliography deliberately excludes claimed speedup transfers. Published improvements belong to their original algorithms, machines, baselines and workloads. The [Gaia questions](questions.md) require their own evidence.
