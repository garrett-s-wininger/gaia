# One frontend for screening and fallback

The host now checks current pre-optimization IR and sends that same module to the backend on a miss. It avoids the previous prototype's second frontend. Equal exact IR permits object reuse only inside the fixed tool/SDK/options context measured here.

Three randomized blocks use private Zstandard 1.5.7 sources and one baseline-only object candidate per TU. Ccache is independently primed and restored to its baseline seed before every request; changed-result history hits are excluded. Each output is compared with an independent CLI object. Measurements are warm local Linux operations on one shared developer machine, with an advisory lock between measured research lanes; unrelated activity/preparation is not excluded.

| Translation unit | Edit | Native full compile, ms | Current IR, ms | Seeded ccache, ms |
| --- | --- | ---: | ---: | ---: |
| common/zstd_common.c | unchanged | 46.85 | 38.05 | 8.94 |
| common/zstd_common.c | comment | 47.24 | 36.01 | 56.98 |
| common/zstd_common.c | unused-macro | 44.34 | 35.00 | 58.09 |
| common/zstd_common.c | unused-type | 47.41 | 37.89 | 145.29 |
| common/zstd_common.c | semantic | 41.64 | 42.92 | 155.07 |
| compress/zstd_lazy.c | unchanged | 3666.32 | 77.92 | 9.34 |
| compress/zstd_lazy.c | comment | 3570.03 | 78.42 | 66.35 |
| compress/zstd_lazy.c | unused-macro | 3446.96 | 74.06 | 76.53 |
| compress/zstd_lazy.c | unused-type | 3547.09 | 75.62 | 3710.98 |
| compress/zstd_lazy.c | semantic | 3516.41 | 3458.45 | 3694.05 |

The heavy unused-typedef edit preserves emitted IR and objects while changing preprocessed input. IR reuse wins all three pairs against both full native compilation and seeded ccache. On a real emitted semantic change the backend still dominates; the host continues current IR without another parse. The small timing differences between the two full-compilation paths are not an established general gain. Exact unchanged inputs remain much cheaper through ccache's direct lookup, and ccache also wins the heavy comment comparison. A practical design should preserve a source/content fast path before deeper screening.

For the heavy semantic miss, stage medians are about 69 ms frontend, 7 ms IR printing/hash and 3.35 seconds backend. The heavy unused-type hit takes about 67 ms frontend, 6 ms screening and less than 1 ms object publication. Stage medians are independently aggregated and do not sum exactly to complete endpoint medians.

Validation covers 90 matched object requests, 24 additional shared-analysis compilation operations, two baseline seeds and seven code-generation/diagnostic boundary probes. Packing, target attributes, inline assembly and debug-line edits miss safely; a current source warning is emitted on an IR hit. Separate host regressions cover backend failure/recovery and a changed include's current depfile on a hit. Source/binary hashes are unchanged before/after the matrix.

The parsed-source analysis in this primary run compares separate sequential parses with shared serial/parallel execution. Use the [separate-worker parallel control](../analysis-parallel/REPORT.md) for the stronger wall-time comparison. This is a Clang-local compiler API experiment, not a portable AST/CST interchange specification. [Implementation, supported inputs and reproduction](../../README.md) document side-product and metadata limits.
