# Source discovery as a consumer and producer of shared knowledge

Status: exploratory synthesis, 31 October 2026. Source indexing and discovery are now explicit research priorities for the user experience. The companion [tooling internals study](tooling-internals.md) includes replacing language-tool implementations where that improves the complete workflow. These pages identify mechanisms and comparisons; they contain no new benchmarks or implementation selections.

The central opportunity is to connect **finding code, understanding it, changing it and validating the change** through the same source generations and reusable language facts. An index can serve a person searching an unfamiliar repository, an agent collecting evidence, a linter and a compiler. Each consumer still needs its own completeness and correctness contract.

## Start with the questions a developer needs answered

| Question | Useful evidence | What a matching result does not establish |
| --- | --- | --- |
| Where is this name, string, configuration key or error message? | Paths and exact text matches | That two occurrences refer to the same entity |
| Which declaration does this use refer to? | Language-specific binding under the selected project configuration | That all configurations or dynamic targets were analyzed |
| Where is this behavior implemented? | Text, structural matches, symbols, docs and ranked conceptual candidates | That conceptual similarity proves behavior |
| What calls this, and what might this change affect? | Qualified reference/dependency relations and their coverage | A complete impact set from an incomplete index |
| How is this actually used? | Call sites, examples, tests and recorded execution evidence | That recorded executions exhaust possible uses |
| Why did this tool resolve or rebuild that? | Input observations, failed lookups, configuration and derivations | That an explanation from an old generation is current |
| What should I read or run next? | The above evidence, current task and estimated cost | That a ranked suggestion is a required or sufficient check |

The success criterion is time to a correct, useful next action. Search latency is one component. An instant wrong location, a stale reference or a huge undifferentiated result set can make the task slower.

## D1 Make basic discovery available before semantic indexing finishes

Zoekt's design uses positional trigrams to narrow full-text searches, including extracting useful strings from regular expressions. It supplies a concrete indexed-search mechanism to compare with scanning. [Zoekt design](https://github.com/sourcegraph/zoekt/blob/main/doc/design.md).

**Gaia hypothesis:** retain a cheap path/text index over admitted content and search changed or unindexed content directly. Store reusable text-derived shards separately from the generation's path and visibility mapping. A branch switch can reuse unchanged content while changing which documents are visible. Verify candidates with the requested matching semantics; short or poorly selective patterns need a fallback that preserves completeness.

Gaia already found that [one combined ripgrep operation beat both parallel queries and the experimental fused scanner](../workflows/README.md). Keep combined ripgrep as a serious control. Charge initial indexing, update writes, branch churn, disk footprint and memory; a small repository or occasional query may favor scanning. Search exclusions, generated files, case/encoding behavior and dependency visibility must agree across controls.

This path should answer useful questions on the first visit, even when the project cannot build. It is also a fallback for languages without a semantic provider.

## D2 Reuse structural analysis while preserving incomplete source

Tree-sitter incrementally updates concrete syntax trees and is designed to provide useful results around syntax errors. It is an example of a responsive syntax layer. It does not by itself supply a language's complete type and binding rules. [Tree-sitter introduction](https://tree-sitter.github.io/tree-sitter/).

**Gaia hypothesis:** share structural facts needed by outlines, structural search, chunk selection, simple diagnostics and edit previews. Maintain the mapping back to the original source, including comments and malformed regions. A structural query such as “calls with this argument shape” can narrow candidates before demanding semantic resolution.

An existing language service may already provide the necessary incremental syntax. Adding a second parser can duplicate work or introduce disagreeing syntax interpretations. Compare that service's existing capabilities with a separate structural provider. Compiler-backed transformations must validate the final edit with the relevant language semantics; a recovered tree is useful evidence about an unfinished edit, not a successful compilation.

## D3 Separate reusable file structure from contextual name resolution

Stack graphs encode name binding through paths and permit file-local graph construction and reusable partial paths. Resolution combines those pieces in the repository context. The research targets indexing without invoking each package's build. [Creager and van Antwerpen, Stack graphs, 2022](https://arxiv.org/abs/2211.01224), [graph model and examples](https://github.github.com/stack-graph-docs/).

**Gaia hypothesis:** an unchanged dependency or source file can retain its local binding structure across branches, while a changed import/export environment changes the answers assembled from it. This resembles retaining a structural plan and supplying new context, extending [connection 4](connections.md#4-separate-structural-plans-from-changing-values).

This is especially interesting for useful navigation before full compilation is available. It is not evidence that every language's bindings are derivable from file syntax alone. Macros, generated code, conditional compilation, overloads and runtime behavior require provider-specific treatment. Test the modeled subset against the language's authoritative tooling. Distinguish unresolved, ambiguous and unsupported results from an empty set of references.

## D4 Let expensive language analysis publish facts for several consumers

Glean stores immutable, schema-defined facts, derives views and exposes code queries. Its documentation explicitly permits language-specific schemas and typically stores selected facts rather than full ASTs. SCIP provides an interchange schema for documents, symbol occurrences and relationships; the producer determines the precision of those facts. [Glean introduction](https://glean.software/docs/introduction/), [SCIP schema](https://github.com/scip-code/scip/blob/main/scip.proto).

**Gaia hypothesis:** when a compiler or language server already resolves a source generation, publish the demanded projections for navigation, reference search, API migration and selected lint rules. An independently maintained semantic index would then have less analysis to repeat. Stable SDKs and dependencies are particularly attractive for prepared indexes distributed with their content identities.

A record format does not establish freshness, complete coverage or correct invalidation. SCIP import could be a compatibility path while a live provider supplies its own update contract. Facts extracted under different targets or feature flags must not be silently merged into one authoritative program. A shared schema can normalize locations and relationships while retaining the language-specific information needed to interpret them.

Gaia's [shared-frontend experiment](../compiler/followthrough/findings.md) detached declaration records while code generation continued, but the consumer only hashed names. A real navigation or lint consumer would test whether useful exported facts justify extraction, storage and lifetime costs. Do not equate the existing surrogate with a completed semantic index.

## D5 Treat edits as coherent overlays with semantic invalidation

clangd combines dynamic, background and optional static indexes. Its dynamic index reflects active files while background indexing supplies broader coverage. This is a useful precedent for immediate edited-file feedback over retained repository knowledge. [The clangd index](https://clangd.llvm.org/design/indexing).

**Gaia hypothesis:** use an immutable base plus explicit unsaved changes, removals and configuration changes. Each request observes one coherent input generation; output records retain their producing context. Show partial coverage while recomputation proceeds, and publish current semantic results only after their dependency conditions are satisfied.

Replacing the edited file's records is insufficient. If an edit changes an exported name or import resolution, references in unchanged files may become stale. Negative lookups matter: adding a formerly absent module can change binding without changing an importer. Invalidate or withhold affected derived answers until refreshed. A displayed historical result can remain useful if clearly identified, but must not become the target of an unvalidated rename.

Retain per-context dependency information so unrelated edits remain selective. A generation labels the snapshot queried; it need not force recomputation of every fact after every keystroke. Match the validity boundary to the projection. Source locations can change even when a symbol's type is unchanged.

## D6 Turn the index into a substrate for executable analyses

Soufflé compiles Datalog analysis specifications into specialized C++ analyzers, applying staged compilation and specialized relational structures. This connects program facts to efficient derived analyses. It does not imply that an arbitrary Soufflé program automatically maintains results incrementally across Gaia edits. [Soufflé architecture paper, CC 2016](https://souffle-lang.github.io/cc-paper).

**Gaia hypothesis:** a bounded family of checks can operate over retained facts: forbidden module dependencies, API usage migrations, declaration/reference constraints or dependency explanations. Source navigation and these checks could reuse both extracted facts and derived relations. Stable rule sets may justify compiled query plans; interactive ad hoc queries may favor interpretation.

Choose rules whose semantics the extracted facts actually support. Path-sensitive behavior, reflection and arbitrary linter plugins may require a different analysis. Deletions, negation and recursion need explicit incremental semantics; the earlier [delta-query connection](connections.md#2-changes-can-have-their-own-compiled-programs) provides a research link, not a ready integration. Compare complete extraction-plus-analysis with the native linter's retained mode, not just relational query time against a fresh CLI.

The additional opportunity is tool-development speed: a new check might be a small query over existing facts. Measure implementation effort and diagnostic fidelity separately from execution performance.

## D7 Join source evidence to tests, execution and explanations

**Gaia proposal:** connect declared source entities to generated artifacts, test observations, failure recordings, benchmark spans and historical changes. This combines [provenance](connections.md#3-retain-why-a-result-exists) with [failure memory and replay](development-loop.md). It would support questions such as “show the implementation, tests that exercised it, and the failure that motivated this guard.”

Build these edges from explicit mappings when available: compiler source maps, build identities, test instrumentation and recorded revision links. An FFI boundary, generated binding or overloaded symbol needs an explicit bridge. Matching names or nearby embeddings can suggest a connection but cannot establish it. Dynamic coverage answers what was observed in particular executions; a static possible-call relation answers a different question.

This can improve discovery without collecting every possible fact. Retain demanded relations and bounded historical evidence. Benchmark useful cross-tool questions against an ordinary editor plus text/symbol search and test reports. Include the cost of producing and updating the mappings, particularly where no tool currently emits them.

## D8 Rank routes to evidence, then preserve enough context to act

Information-foraging research studied how programmers follow cues through source while debugging, including an empirical study of ten professional developers. It offers a connection between navigation topology, useful cues and search behavior; it does not establish a particular Gaia interface or agent policy. [Lawrance et al., IEEE TSE 2013](https://web.engr.oregonstate.edu/~burnett/Reprints/TSE-IFT-2013-asprinted.pdf).

**Gaia hypothesis:** rank results using multiple routes—exact terms, symbols, structural relationships, docs, prior examples and optional embeddings—and explain the strongest route. A result that says “implements this interface; exercised by these two tests” may reduce exploration more than another ranked snippet. Let the user expand callers, tests or history from that result without repeating project discovery.

For an agent, return a bounded collection of source excerpts and evidence links with generation, scope, unresolved relationships and truncation status. Retrieval budgets should limit presentation without silently turning a truncated answer into “all references.” Code-edit application must revalidate against the current source.

The [NPU relevance proposal](development-loop.md#a1-an-npu-could-maintain-local-relevance-across-a-project) fits here only if a model improves task success beyond lexical and symbol baselines. Measure the model on unfamiliar tasks and edited source, count indexing and reranking cost, and preserve exact evidence behind its suggestions. GPU/NPU execution is a later backend comparison for this same retrieval workload.

## A concrete interaction that joins the ideas

Consider an unsaved rename of an exported function while the user asks where a failing test reaches it:

1. Text and structural search can immediately inspect the new buffer and retained unchanged content.
2. The language provider marks affected bindings stale, including importers whose bytes did not change.
3. A current semantic result identifies the renamed declaration and qualified call sites. Old coverage remains labeled with its original source/build identity.
4. The interface offers the relevant test and prior failure evidence, with their relationship to the current code made explicit.
5. A requested build or diagnostic reuses eligible facts and validates its own remaining input conditions. New results publish only for the appropriate context.

The proposed saving is repeated discovery and analysis across those steps. This interaction also tests whether retained state improves the experience when the code is temporarily incomplete.

## Small shared contracts worth investigating

These are research requirements, not a proposed universal AST or finalized protocol.

| Shared concept | Information needed |
| --- | --- |
| Source identity | Content identity, logical document and generation membership; explicit unsaved and generated content |
| Source range | Unambiguous coordinate/encoding convention and conversion to editor coordinates |
| Semantic context | Provider/schema version, language mode, target, feature flags, dependency resolution and relevant configuration |
| Fact validity | Observed inputs, including relevant absence/visibility conditions; relation to the current context |
| Coverage | Analyzed scope, unsupported cases, pending work, ambiguity and truncation |
| Result origin | Text match, structural analysis, qualified semantic fact, execution observation or relevance suggestion |
| Lifetime | Publication, cancellation, reader ownership and reclamation of obsolete state |

Symbol identity must be qualified by the provider and context where necessary. A content digest alone does not identify what a name means, and a process-local AST pointer cannot serve as a durable cross-tool identity.

## First comparisons

| Research slice | Strong control | Outcomes and reason to stop |
| --- | --- | --- |
| Text/path index with live changes | Combined ripgrep over the same visible source | First useful answer, update cost and total session resources; stop if construction never amortizes |
| Navigation plus one real diagnostic consumer | The language service's existing combined/incremental mode | Complete answer/diagnostic latency, duplicate analysis avoided and retained memory; stop if native sharing already captures the benefit |
| Semantic base plus unsaved overlay | Fresh authoritative analysis of each relevant state | Deletes, imports, macros/configuration, generated files and branch switching; any stale authoritative answer rejects the design |
| Source/test/failure discovery | Existing editor, symbol search and test reports | Correct task completion, steps to relevant evidence and preparation cost; stop if the joins do not improve actual investigation |
| Optional learned relevance | Lexical/symbol retrieval and a CPU model | Held-out task success, evidence quality, energy and response latency; stop if device/model overhead exceeds benefit |

Use a session containing first open, unfamiliar-code exploration, typing, rename, configuration change, dependency update and branch switch. Include searches during a build and under a fixed memory budget. Keep time to the first useful partial answer separate from time to a complete answer, and measure how long stale or incomplete information is presented.

For human tasks, control familiarity and task order; for agent tasks, hold model, prompts and tool budgets constant. Backend microbenchmarks alone cannot establish improved development productivity. The highest-value first question is whether **one real semantic producer can improve navigation and a second tool together** beyond the mature combined baseline.
