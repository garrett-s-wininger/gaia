# Repository guide

The layout separates intended product behavior, research interpretation and reproducible evidence.

```text
README.md                         start here
components/                       product boundaries and designs
  source-control/                 agreed MVP, object model, first milestone
  dependencies/                   ecosystem/input-access boundary
  compiler/                       tool invocation and execution boundary
  editor/                         planned; open design questions
  artifact-host/                  transfer research design; public protocol open
docs/                             platform-wide direction and repository guidance
research/                         findings and prospects for human readers
  compiler/                       compiler conclusions, next experiments, run index
    jvm/                          managed Java compiler findings and run index
  python/                         Python loading/resolution and Python/Node state reuse
  artifacts/                      transfer conclusions, next questions, run index
  storage/                        modeled I/O sensitivity; actual device behavior separate
  java/                           JVM framework startup findings and run index
  ruby/                           Ruby loading findings and run index
  dotnet/                         .NET preparation findings and run index
experiments/                      runnable code, lab notes and evidence
  compiler/
    cpp_graph/                    multi-target C++ integration fixture
    semantic_invalidation/        AST/IR object-reuse comparisons
  artifacts/
  storage/
  python/dependency_bundles/
  python/dependency_solving/
  python/interpreter_snapshots/
  java/startup/
    jvmti/                        bounded instrumentation and framework refinement
  java/compiler/
    topology/                     one JVM versus multiple JVMs
    variants/                     GC/JIT, Leyden and Native Image
  ruby_startup/
  dotnet_startup/
tools/                            repository maintenance checks
```

## Where new work belongs

A component's `README.md` should state its purpose, current maturity, boundaries and the designs to read. Put accepted behavior, open proposals and milestones beside it, and distinguish those states. Start a new component with a scoped guide; avoid implying an agreed MVP through a placeholder directory.

Research findings should answer what was tried, what happened, why it matters and where the result stops applying. Keep prospects separate: the next question, the comparison needed and what would make it worth pursuing. Technical task IDs and machine-readable run indexes can support those pages without becoming their main narrative.

Experiments own implementation, reproduction commands, reports, raw data and validation. Detailed chronological `FINDINGS.md` files are lab journals. Human summaries link to the relevant evidence instead of copying a growing sequence of “latest” updates.

## Preserve evidence when organizing

Commit reports, acquisition manifests, provenance and validation summaries. Full observations, profiler captures and trace replay plans are ignored. The [evidence manifest](../research/evidence.json) identifies the excluded original artifacts by size and SHA-256; they are local-only until separately published. Retained measurement metadata describes the original environment, not a portable execution plan. Follow the [reproduction guide](../experiments/reproducing.md) to rebuild inputs and adapters; new outputs default to ignored `_work/runs/` directories. Do not depend on retained binaries, original checkout paths or an existing work tree.

Source-control contracts live under `components/source-control/`. Python experiment plans live under `research/python/designs/`. Keep documentation current rather than retaining superseded copies; preserve measurements and reproduction evidence under `experiments/`.

Run `python3 tools/check_repository.py` to check versioned Markdown links, run-index paths, raw-data ignore rules and the hashes of available evidence. Run focused implementation tests when moving code. Directory moves alone do not require rerunning performance matrices; new source/toolchain behavior does.
