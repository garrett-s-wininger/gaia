# Native references and namespace observations

The fifth experiment follows the [source-delta study](delta-analysis.md) into its producer bottleneck. Module additions/removals previously required reparsing every file, because unchanged imports can bind differently when a formerly absent module appears. We exposed the native parser's references, indexed their candidate names, and tested rebinding those retained references against a stronger scoped native reparsing control.

The [report](../../experiments/import_rebinding/results/django/REPORT.md) records a useful result: **scoped native parsing reduces the complete tested trace by 41.61%** against full rescans, with reductions in every block. The four local membership changes take 74.28% less time. The original 16-event trace improves by 38.10%, before adding the two broader shadowing probes.

Retaining all parsed references and rebinding them is correct but does **not** establish an additional overall latency improvement over scoped native parsing. Their paired median difference is approximately zero, with individual blocks on both sides. The retained-reference path also keeps 6,520 extra reference records. Both indexed variants make initial response slower, so the gain depends on subsequent changes and reuse.

## The connection made concrete

This is a small instance of incremental relational maintenance: join changed namespace names with the source references that observe them, then update the resulting bindings. The relevant observation is not limited to the module an import currently resolves to. Its **absent exact candidate** can matter just as much as the present fallback parent.

For example, `from django.utils import later` initially resolves to `django.utils` under the pinned static resolver. Adding `later.py` changes the unchanged import's binding. Indexing only the old resolved edge misses this event. Recording both candidates lets the producer find the affected importer directly.

The [native patch](../../experiments/import_rebinding/native.patch) exposes Grimp's existing parser output before membership-dependent resolution. It retains the original native treatment of relative imports, syntax, locations and lazy flags. The Python binder implements the pinned resolver's bounded exact-name/immediate-parent rule. This is not a replacement for Python execution, type checking or arbitrary language semantics.

The two indexed controls share the observation index. One discards full references and invokes the native parser only for affected unchanged files. The other keeps those references and avoids parsing them. This isolates the value of full reference retention from the larger gain due to precise invalidation.

## Evidence and boundary

All 378 measured responses pass fresh unmodified Grimp graph and full Import Linter checks. Four focused tests cover another 360 randomized source-update batches, namespace packages, file/package replacement, stale-index removal, lazy/relative imports and failed publication. Responses use the prior editor contract: three dependency-navigation sets and one shortest current explanation per forbidden-rule violation, rather than the full CLI report.

When one missing module appears, full rescanning parses 908 files; scoped native parses two; rebinding parses only the new file. When a name used by 62 existing files is shadowed by a new module, scoped native parses 63 files while rebinding parses one. The latter case is a deliberate stress fixture over real Django source, not a captured edit or a valid application change.

All arms still rediscover the module namespace, costing around 6 ms per membership change. Source writes, discovery, parsing, index changes and result production remain inside request clocks. Initial state construction is included in trace totals. Oracles run between requests and can affect memory/cache behavior; small differences between the indexed variants need an uninterrupted service benchmark before being treated as a reliable advantage.

The demonstrated next baseline is therefore **native facts plus explicit namespace observations and scoped invalidation**. A universal graph or complete retained AST is unnecessary for this result. The boundary belongs to the semantic producer: it knows which names and absences can change a binding. Gaia could preserve that knowledge across source discovery and diagnostic consumers instead of reconstructing it from files on every namespace change.

The implementation is in [experiments/import_rebinding](../../experiments/import_rebinding/README.md). Native import resolution and scoped invalidation are the tested boundaries; production integration remains open.
