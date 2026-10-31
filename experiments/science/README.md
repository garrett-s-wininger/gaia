# Transformations and shared computation

These experiments test the [scientific research directions](../../research/theory/README.md) against correctness oracles and conventional controls. Start with the [human overview](../../research/science/README.md) and [coverage map](../../research/science/coverage.md).

| Track | Reproduction | Evidence index |
| --- | --- | --- |
| Patches, changing observations, graph resources and native geometry | [Graphs](graphs/README.md) | [Runs](../../research/science/graphs/experiments.json) |
| Reconciliation, delivery, placement, search, environments and adapters | [Data](data/README.md) | [Runs](../../research/science/data/experiments.json) |
| Shared input generations, real LLVM analyses and speculative compilation | [Compiler](compiler/README.md) | [Runs](../../research/science/compiler/experiments.json) |
| Assets, modules, workspaces, editor, tests and GPU execution | [Workflows](workflows/README.md) | [Runs](../../research/science/workflows/experiments.json) |
| Process-visible accelerator APIs | [Devices](devices/README.md) | [Diagnostic](devices/results/capability/REPORT.md) |

Reports and compact evidence are reviewable source. Raw observations, source archives, third-party SDKs, binaries, packs, caches and temporary compiler outputs remain ignored. Follow each track's acquisition/reproduction instructions with fresh caller-selected work/output paths. Existing local absolute paths are historical provenance, not execution instructions.

Cooperating benchmarks take an advisory lock per case. That does not exclude preparation or unrelated system load. Model work, actual native CPU measurements, logical I/O delays and actual device execution are labelled separately. Cross-track numbers do not combine into a platform-wide speedup.
