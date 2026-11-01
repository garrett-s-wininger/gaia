# Third experiment: target actual changed-source compilation

The [compact analysis experiments](retained-facts.md) did not establish a compiler speedup. This continuation profiles actual source-to-object work and measures a complete compile, link and executed regression workload on two algorithm edits to Zstandard 1.5.7.

**Compilation can be accelerated in this case, but the tested custom policy does not beat the strongest stock development choice.** Replacing optimized machine-code selection/allocation with LLVM's existing fast alternatives reduces compilation time by 17–20% against `-O2`. All fourteen paired compile comparisons win, and the two policies emit identical optimized LLVM IR in the diagnostic check. However, eight-suite execution becomes about 51% slower and the object grows about 2.4×. Stock `-O0` gives the shortest measured edit-to-test time for both one and eight suites; stock `-Og` also has better complete-operation medians than the custom policy.

The [complete report](../../experiments/backend_policy/results/backend/REPORT.md) includes the stock controls, both executed-demand scenarios, preparation, object sizes, paired comparisons, profile limitations and 105,840 successful round trips across 70 linked compilations. The compiler flags are experimental mechanisms already supplied by LLVM, not a newly invented compiler algorithm. No production settings changed.

## What the profile changes

The stock compiler spends approximately half its time optimizing LLVM IR and nearly half generating machine code, with only a few percent in the frontend on this TU. Cost is distributed across many specialized functions. The machine-code intervention roughly halves that stage in separate profiles. This is a much larger target than the isolated liveness relations studied earlier.

The previous compiler study's emitted-constant edit forced an object-cache miss. This experiment additionally requires an edit to change compressed output on its exercised inputs. Halving a search budget and increasing a lazy-search depth satisfy that condition. All policies must still match the **current edit's** compressed bytes and reconstruct the original input exactly.

It remains a bounded experiment on one upstream translation unit and a constructed API workload. Stock `-O0` wins partly because the measured artifacts execute for relatively little time. The project dependencies stay optimized and unchanged, so this models a mixed-policy incremental build, not an entirely unoptimized library or a production edit distribution.

## Research priority after this result

The [architectural research directions](architectural-next.md) set the next scope around changed computation, reuse units and ownership across tools. Further optimization-setting selection is outside that scope; this completed experiment remains evidence for its measured tradeoff.

The evidence does not justify building a replacement backend around this particular fast policy. Existing development settings already exploit a better tradeoff for the tested demand. A useful Gaia integration would need to select and retain artifacts according to their actual expected use, with correct build contexts and explicit runtime/debug requirements, rather than relabel a lower optimization level as a new acceleration technique.

If retaining optimized execution is essential, finer-grained optimization/code reuse remains a distinct untested hypothesis. It would have to avoid repeated work on unchanged functions while tracking inlining, referenced globals, target options and other dependencies. The profile supplies a reason to examine that boundary; it supplies no safe reuse key or speedup measurement for it. This is a deeper compiler change than the completed policy experiment.

For broader development-loop experiments, a real project's competent existing development settings belong in the control. Test setup/execution and source discovery offer distinct architectural boundaries to investigate. The present results provide no reason to pursue GPU/NPU offload for this compiler workload.

The [backend implementation](../../experiments/backend_policy/README.md) studies compiler policy separately from the [shared workspace](../integration/README.md); their source lifetimes, controls and clocks differ.
