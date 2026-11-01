# Retained source facts beat repeated assembly; incremental proofs need a better case

The fourth experiment moves beyond compiler settings into language-tool internals. It keeps Grimp's native Python import parser, changes the lifetime of its facts, and compares native cached queries with an alternative that maintains shortest dependency proofs after edits. Navigation and a real Import Linter rule consume the same current facts. The [measured report](../../experiments/delta_analysis/results/django/REPORT.md) and [implementation](../../experiments/delta_analysis/README.md) describe the exact controls and limitations.

## Result

On a designed 16-event Django trace, retaining native facts and updating the existing graph cuts the summed request time by a paired median **57.47%** against the cached-library path. Median trace spans are 467.343 ms for the library path and 199.637 ms for retained native. Edits that preserve module membership fall from 240.440 to 22.262 ms across eight requests.

Adding maintained shortest proofs yields a 203.136 ms trace median: a paired median **1.75% slower** than retained native, with block differences on both sides of zero. It is **11.81% slower** on the fixed-membership edit group. The transformation has a small stable benefit when changing the rule to a target already maintained for navigation, but that is insufficient to justify the additional graph and proof state for the trace as a whole.

This result separates two claims that would otherwise be easy to conflate. A tool service retaining parsed source facts and invalidating consumers precisely is useful here. Replacing its native query traversal with a separately maintained algebraic representation has not demonstrated an overall benefit.

## The connection tested

[Incremental database theory](https://www.vldb.org/pvldb/vol16/p1601-budiu.pdf) motivates computing changes in derived answers instead of reconstructing them after each edit. This implementation specializes that idea to a min-plus shortest-path relation. Finite distances determine dependency-navigation results and forbidden-rule violations; selected parent paths explain those violations.

Deletions reveal why provenance matters. A reference count alone could let a disconnected cycle keep supporting its own answer. The prototype invalidates the selected witness subtree before repairing paths from still-valid boundaries. Independent breadth-first search validates 3,000 randomized update batches, and real-source traces exercise cycle exit loss/recovery.

The computation is not inherently device-friendly merely because it has an algebraic description. One import retarget processes 741 root/node entries and 5,426 edge examinations across three maintained targets. Native traversal with result caching handles that edit faster. Sparse, irregular repairs plus small demand do not establish a GPU/NPU opportunity here; no device backend was measured.

## What is actually equivalent

The response gives three module-dependency navigation sets and one shortest current explanation per forbidden-rule violation. It does not provide symbol/type navigation or the full linter CLI report. The real `ForbiddenContract.check` runs with a small traversal adapter in both measured retained arms; the control uses the native singular shortest-chain operation, and the alternative uses its maintained proof. The unmodified linter independently checks the violation set and minimum explanation lengths after every request.

All 336 responses also match fresh native graph facts, current source locations and lazy-import flags. This validates the declared static-import response, not arbitrary Python semantics or a production concurrent language service. The architecture rule is a research probe, not a declared Django constraint.

## The stronger next hypothesis is in the producer

**Measured continuation:** the [native-reference and namespace-index experiment](import-rebinding.md) now tests this proposal. Scoped native reparsing reduces the complete trace by 41.61% against full rescans; keeping complete references for rebinding adds no established overall advantage over that indexed control. The following paragraphs record the hypothesis that motivated it.

Adding/removing modules consumes about 130 ms of the retained native trace's 155 ms after initialization. Both retained arms rescan the project because a previously absent module can change resolution of **unchanged source**. The pinned library's ordinary file cache actually retains a stale edge at that boundary; the experiment reproduces it and gives the library control a fresh cache namespace so its output stays correct.

The next useful experiment would separate **file-local import references** from **contextual bindings**. Retain syntactic references, including names that failed to resolve; let module membership changes invalidate only affected bindings. This combines the [contextual source-discovery proposal](architectural-next.md#discovery-route-preserve-file-structure-across-changing-contexts) with the successful retained producer. It would target a demonstrated full-rescan cost rather than spend more time optimizing a small graph kernel.

That is a new hypothesis, not a measured improvement. It requires replacing or extending the native resolver's interface, exact handling of relative imports and parent fallback, and a control with the same retained facts. Start with the absent-module counterexample and expand only where current-source semantics remain equivalent.

The [implementation](../../experiments/delta_analysis/README.md) studies native import facts and derived diagnostics separately from Clang observations and scheduling. The [backend-policy result](backend-policy.md) supplies a different comparison; this experiment does not tune compiler flags.
