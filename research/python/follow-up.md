# Python research follow-up queue

Current disposition: preserve measured formats/loading and resolution work as two Python-specific tracks. Framework-specific micro-optimizations are paused. Compiler work has its own [findings](../compiler/findings.md) and [prospects](../compiler/prospects.md); PY-FMT-04 has a first [measured state-reuse experiment](interpreter-state.md); the other Python tasks remain queued until selected.

| ID | Follow-up | Prerequisite / scope | Evidence needed to finish |
| --- | --- | --- | --- |
| PY-FMT-01 | Representative industry-tool startup | Choose one real tool using many Python modules; pin its full inputs and fixed operation. | Matched native/directory/indexed controls, actual output validation, full lifecycle, producer cost and compatibility materialization. |
| PY-FMT-02 | Portable admission/format contract | Decide immutable-store/trust boundary and supported ecosystem behavior before freezing a schema. | Independent reader, versioned test vectors, malformed inputs, per-open integrity policy and invalidation behavior. |
| PY-FMT-03 | Broader Python compatibility | Pick concrete missing cases: native wheels, namespace packages, metadata/entry points, editable dependencies. | Explicit supported/rejected behavior and no silent fallback; separate performance/compatibility cost. |
| PY-FMT-04 | Interpreter state reuse | Fork-template, synthetic Node, real TypeScript module and full project CLI controls measured; next real-tool preparation boundary, lifetime/invalidation and memory budget. | Cold creation and repeated request costs, error recovery, finalizers, mutable global isolation and correct source/debug behavior. Not another container tweak. |
| PY-RES-01 | Larger published candidate universe | Acquire a pinned local inventory without conflating network discovery with solving. | Artifact-identity agreement against documented reference policy; explicit incomplete/unsat outcomes; multiple graph shapes. |
| PY-RES-02 | Lazy eligibility summaries | Separate target/tag/Requires-Python summaries from full dependency metadata. | Reduced preparations/bytes with unchanged selections on the same universe, including cold session and memory cost. |
| PY-RES-03 | Dense/conflict-heavy solver bookkeeping | Extend rollback, information-list and incompatibility-scan measurements. | Differential/oracle tests where feasible, search counters, full disposal/memory and no universal polynomial claim. |
| PY-RES-04 | Remote metadata and artifact delivery | Specify source identity, trust, target/policy and byte verification first. | Local-equivalent selections, bulk queries, bounded caching/invalidation and artifact hash validation. No protocol chosen by current JSON fixtures. |

When reopening a task, record its ID, concrete workload, baseline, correctness checks, timed boundary and stop condition before optimizing. Add its report/raw locations to [experiments.json](experiments.json), then update the relevant review page. Preserve negative results and original observations; annotate superseded timing scopes instead of silently rewriting them.

A new timing run is required for new toolchains or material environment changes. Existing absolute times cannot be combined across runs. Storage-cold claims require cache control. Human review should assess the effect size and sample distribution, not only a best time or syscall count.
