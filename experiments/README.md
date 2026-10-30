# Experiments

Runnable research, technical lab notes and retained measurements live here. For interpretation, start with the [human research guide](../research/README.md).

| Area | Code and reproduction | Evidence |
| --- | --- | --- |
| Native compiler tools | [compiler](compiler/README.md) | [Compiler run index](../research/compiler/experiments.json) |
| Python formats/loading | [python/dependency_bundles](python/dependency_bundles/README.md) | [Python run index](../research/python/experiments.json) |
| Python resolution | [python/dependency_solving](python/dependency_solving/README.md) | [Python run index](../research/python/experiments.json) |

Each experiment owns its source, reproduction README, detailed `FINDINGS.md`, retained reports under `results/` and ignored local `_work/`. Reports, acquisition manifests, provenance and validation summaries belong in Git. Full raw observations, profiler captures, replay plans, downloads and built tools stay ignored. The [evidence manifest](../research/evidence.json) records excluded original artifacts by path, size and SHA-256. They have not been published separately and are absent from a clean checkout.

## Reproduce elsewhere

Follow the [reproduction guide](reproducing.md) for toolchain configuration, input-generation order and fresh output locations. Commands recorded in published results describe the original environment; do not replay their absolute paths. Generate predecessor datasets and build native adapters on the machine being measured. No compatibility aliases or retained local binaries are required.
