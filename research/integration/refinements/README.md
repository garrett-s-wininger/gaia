# Earlier useful results and more precise reuse

The continuation implements the three missing boundaries from the first integration: frontend fact publication, retained immutable identities and conservative configuration/result-history reuse. Read the [complete replay](../../../experiments/integration/refinements/results/combined/REPORT.md), [scan study](../../../experiments/integration/refinements/results/scan/REPORT.md), [hardened handoff check](../../../experiments/integration/refinements/results/handoff/REPORT.md), and [reproduction guide](../../../experiments/integration/refinements/README.md).

| Matched operation | Original shared path | Refined path | Ninja + ccache/refined index |
| --- | ---: | ---: | ---: |
| Numeric configuration macro change | 14.36 s | 272 ms | 2.41 s |
| Return to earlier optional-header state | 295 ms | 130 ms | 182 ms |
| Source edit, complete build/query | 292 ms | 279 ms | 506 ms |
| Source edit, editor facts received | 292 ms | 126 ms | 197 ms |

Values are medians of three fresh matched trace blocks, not before/after samples from different research runs. Configuration changes reuse 32 of 33 targets and compile the target that actually reads the changed numeric macro. Returning to the earlier state restores its object and depfile without a frontend, then links. No target, ABI, optimization or language options are silently discarded.

Summed timed operations across each twelve-operation trace have medians of **20.28 seconds original, 4.96 seconds refined and 8.67 seconds Ninja/index**. Refined trace sums win all three pairs against both controls. The sum excludes preparation, full reference work and between-operation validation; it is not a complete continuous session.

The result has limits. The project-wide header-edit query still takes 2.73 seconds versus the standalone index's 1.32 seconds: later frontends wait behind earlier serial backends. Median current persistent-worker PSS rises from 189 to 208 MiB as lexical footprints and history are retained. Ninja's persistent index alone samples at 129 MiB; transient compiler/linker peaks and controller memory are excluded. The 128 MiB history payload allowance is not a total-memory quota.

The separate retained-scan study uses the same LLVM SHA-256 helper in both hosts. Retaining immutable identities reduces the median from **5.68 to 1.28 ms**, or **8.35 to 1.69 ms** when unchanged-generation admission is included. All 280 scan responses preserve exact identities and facts; later source changes invalidate correctly. This query interface differs from the full replay's explicit current-command bindings, so its time cannot replace the full no-op measurement.

All 108 complete replay operations match fresh physical object, depfile, executable and declaration-index references. Configuration projection is a restricted, conservative fast path over numeric definitions, read identifiers, expanded aliases and potential pasted names, under a fixed SDK/environment contract. It is not a general compiler-effect proof or a production service.

Failure-path hardening followed the full matrix. Current code passes 16 refinement and four compatibility methods. A further seven actual production-TU edit pairs preserve object/fact identity and match stock Clang; hardened frontend receipts remain around 114 ms before roughly 140 ms compilation completion. Those single-TU checks do not establish full-matrix timing equivalence. Reports retain historical pins and a source reconstruction patch.
