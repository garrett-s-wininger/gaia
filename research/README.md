# Research

Start with [what we learned](findings.md) and [what is worth trying next](prospects.md). These pages explain the results and their implications without requiring the experiment chronology or task IDs.

| Topic | Findings | Prospects | Code and evidence |
| --- | --- | --- | --- |
| Compiler execution and input reuse | [Read](compiler/findings.md) | [Read](compiler/prospects.md) | [Experiments](../experiments/compiler/README.md) |
| Python dependency loading and resolution | [Read](python/findings.md) | [Read](python/prospects.md) | [Loading](../experiments/python/dependency_bundles/README.md), [resolution](../experiments/python/dependency_solving/README.md) |

[Component designs](../components/README.md) describe intended product behavior. Research describes what was actually tried, what happened and which questions remain. The distinction matters: source control has an agreed design but no implementation; editor and artifact-host work have not reached that stage.

Detailed reports, raw observations and validation logs stay with each experiment. The [compiler run index](compiler/experiments.json) and [Python run index](python/experiments.json) provide machine-readable evidence locations. Historical notes remain available for deeper investigation; current conclusions live here.

Full raw observations and profiler captures are excluded from Git. Their original identities are recorded in the [evidence manifest](evidence.json); raw files are local-only, with no published download location. Reports and validation summaries remain versioned.
