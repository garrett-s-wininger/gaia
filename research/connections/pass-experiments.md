# First experiment: change the formulation of a real analysis

The first bounded experiment is complete. On branch-heavy Zstandard and zlib LLVM IR, a conventional block worklist beats both synchronous Boolean sweeps and sparse per-value traversal at the prepared-kernel boundary. Once extraction and representation construction are included, those costs dominate much of the operation. This result favors investigating how useful relations are produced and retained before attempting device offload for this pass.

This follows Gaia's guiding principle: a holistic view can expose choices hidden behind established tool boundaries. The experiment changes a pass's mathematical organization while preserving its exact required result. It does not assume that a more regular mathematical form must be faster.

## Complementary scope

The [implementation](../../experiments/pass_algebra/README.md) measures analysis formulations separately from the [workspace and SIMD integration](../integration/README.md). An advisory lock excludes cooperating timed cases, rather than unrelated activity or preparation.

The integration work examines sharing and accelerating existing relations; this experiment asks which relation and propagation schedule a compiler analysis should use. A later consumer can receive the resulting facts through an explicit boundary.

## What ran

Three native Odin implementations compute the same block-by-SSA-value live-in relation:

1. A block worklist using packed value masks.
2. Synchronous sparse Boolean multiplication with generate/kill masks.
3. A transposed generator relation with sparse backward propagation per value.

All use the same output layout and compiler settings. The [mathematical contract](../../experiments/pass_algebra/README.md#required-result-and-mathematical-transformation) includes incoming-edge PHI uses, local definitions, unreachable blocks and the least fixed point. The C++ adapter uses LLVM to extract facts; this is not a comparison of Python graph code with native kernels.

The corpus contains 121 functions, 5,978 blocks and 35,185 SSA values across three unchanged upstream translation units, compiled freshly at `-O1`. Zstandard's common file reduces to six single-block functions with no CFG edges; it is a small overhead control, not evidence for parallel graph execution. The branch-heavy cases are `zstd_lazy.c` and zlib's `deflate.c`.

## Current-source results

Values are milliseconds per module pass, medians of seven shuffled blocks with ten repetitions per timing batch. They describe warm CPU execution on one machine. Repetition amortizes timing noise; an actual unchanged request could reuse its result rather than rerun this pass.

| Input and boundary | Block worklist | Boolean sweeps | Per-value sparse |
| --- | ---: | ---: | ---: |
| Zstandard lazy, prepared kernel | 0.300 | 1.987 | 0.884 |
| Zstandard lazy, resident IR to result | 11.521 | 12.561 | 12.639 |
| zlib deflate, prepared kernel | 0.0196 | 0.1397 | 0.0351 |
| zlib deflate, resident IR to result | 0.927 | 1.036 | 0.967 |

Both alternatives lose all seven paired kernel comparisons on each branch-heavy input. The Zstandard complete-pass comparisons also favor the worklist in all seven blocks. The smaller zlib complete-pass comparisons are mixed: sweeps win three blocks and per-value traversal wins two. Their median differences are not a robust general whole-pass advantage.

The complete-pass clock begins with an already parsed module and includes fact extraction, selected-layout construction, scratch allocation, solving, full-output consumption and request cleanup. IR parse/verification and source-to-IR compilation are separately recorded. This is an analysis boundary, not a complete build or user-task timing. [Report](../../experiments/pass_algebra/results/no-names/REPORT.md), [summary](../../experiments/pass_algebra/results/no-names/summary.json), [provenance](../../experiments/pass_algebra/results/no-names/provenance.json).

The per-value representation reduces retained element payload plus scratch: roughly 0.89 MB versus the worklist's 1.07 MB on Zstandard, and 87 KB versus 103 KB on zlib. It still loses kernel latency. These counts exclude allocator/container overhead, LLVM memory and the other comparison instances; they are not process-memory measurements.

The Boolean form supplies independent row work within each sweep, but pays repeated convergence work on this CPU. The individual real functions are small: the maximum is 191 blocks in the Zstandard case and 758 SSA values in the zlib case. A device experiment would need a natural batch and a complete movement/synchronization comparison; these results do not establish a useful GPU or NPU workload.

## An extraction mistake that the wider clock exposed

The [initial exploratory run](../../experiments/pass_algebra/results/initial/REPORT.md) constructed human-readable LLVM operand names during every extraction, even though the analysis output uses integer identities. It produced roughly 409 ms and 44 ms worklist complete-pass medians on the branch-heavy inputs, overwhelming the kernels.

The current adapter constructs those names only for the hand-checked diagnostic dump. The required relation, function shapes and output digests are identical across the two runs. The [small source change](../../experiments/pass_algebra/results/initial/remove-unused-names.patch) records the correction, and both observation sets retain source/binary identities. The initial timings belong to the earlier adapter and should not be used to rank the final implementation.

This is a correction to the experimental adapter, not a production Gaia speedup. It illustrates why a kernel-only result is insufficient: the surrounding interface may do expensive presentation or reconstruction work that the operation never required. The final full-pass cost remains much larger than the prepared solver cost, so merely accelerating propagation misses a substantial part of this prototype's work.

## Correctness and limits

Every output bit from all three implementations was checked against an independent ordered-set fixed-point solver. Four executed test methods cover 4,096 exhaustive tiny graph/fact combinations, 175 deterministic random cases and six hand-checked LLVM functions. They exercise cyclic and disconnected graphs, mask word boundaries, PHIs, unreachable blocks, empty value universes, `invoke` edges and buffer guards. [Validation](../../experiments/pass_algebra/results/no-names/validation.json).

The extraction adapter is shared by the competing formulations, so the set oracle alone cannot validate extraction semantics. The hand-checked LLVM cases address that separate boundary. No stock LLVM liveness pass, code generator, GPU or NPU is benchmarked. The analysis is syntactic SSA value liveness, not memory aliasing or register allocation. No optimizer transformation or emitted program was changed.

These are a few translation units on one machine, with warm pages and advisory measurement exclusion. This first study makes no confidence claim about an entire language ecosystem and has no enforced memory budget or incremental edits. The [second experiment](retained-facts.md) adds controlled IR edits and a second consumer.

## The next question made concrete

The [retained-facts follow-up](retained-facts.md) now tests this boundary against a stronger control: LLVM's existing use lists with the same result caching and invalidation. Compact graph construction does not recover its cost in that measured trace.

For this workload, keep the worklist as the native control. Investigate producing the required CFG/use/definition relations directly at a useful language-tool boundary and retaining them for an actual second consumer. Compare that with rebuilding this adapter's relations, including the cost of invalidation and changed value identities. This would test whether holistic ownership of the representation matters more than another propagation kernel.

The wider experimental method is now established: **declare the exact pass result, derive alternative formulations, choose layouts/schedules that expose different execution patterns, then charge production, movement, solving and consumption**. A later pass with larger regular batches may justify a device backend; the current evidence supplies no reason to force this one onto an accelerator.
