# Research

Start with [what we learned](findings.md) and [what to try next](prospects.md). The topic guides explain the evidence without requiring the experiment chronology or task IDs.

The [broader sharing overview](workflows/coverage.md) maps the compiler, data, testing, repository and schema prototypes to their results and remaining limits.

The [shared theory track](theory/README.md) connects graph, set, patch, networking and adaptive/nature-inspired models to [proposed experiment sets](theory/experiments.md). The [science experiments](science/README.md) now test those proposals with bounded models, real consumers, compiler analyses and device execution.

The [cross-field connections](connections/README.md) combine literature with seven measured continuations. Read the [findings](connections/findings.md) for retained native facts, namespace invalidation, compiler policy, runtime isolation and source/test evidence; the [prospects](connections/prospects.md) keep the remaining hypotheses separate from measured gains.

| Topic | Findings | Next questions | Code and reproduction |
| --- | --- | --- | --- |
| [Shared workspace and CPU integration](integration/README.md) | [Read](integration/findings.md) | [Read](integration/prospects.md) | [Integration experiments](../experiments/integration/README.md) |
| [Native facts, ownership and source discovery](connections/README.md) | [Read](connections/findings.md) | [Read](connections/prospects.md) | [Connections experiments](../experiments/connections/README.md) |
| [Transformations, geometry and heterogeneous compute](science/README.md) | [Coverage and limits](science/coverage.md) | [Priorities](science/prospects.md) | [Science experiments](../experiments/science/README.md) |
| [Native compiler execution and input reuse](compiler/README.md) | [Read](compiler/findings.md) | [Read](compiler/prospects.md) | [Compiler experiments](../experiments/compiler/README.md) |
| [Managed JVM compilers](compiler/jvm/README.md) | [Read](compiler/jvm/findings.md) | [Read](compiler/jvm/prospects.md) | [Java compiler experiment](../experiments/java/compiler/README.md) |
| [Artifact transfer and local access](artifacts/README.md) | [Read](artifacts/findings.md) | [Read](artifacts/prospects.md) | [Artifact experiments](../experiments/artifacts/README.md) |
| [Storage-service sensitivity](storage/README.md) | [Read](storage/findings.md) | [Read](storage/prospects.md) | [Storage experiments](../experiments/storage/README.md) |
| [Python loading/resolution and Python/Node state reuse](python/README.md) | [Read](python/findings.md) | [Read](python/prospects.md) | [Python experiments](../experiments/python/README.md) |
| [JVM framework startup](java/README.md) | [Read](java/findings.md) | [Read](java/prospects.md) | [Groovy/Picocli experiment](../experiments/java/startup/README.md) |
| [Ruby tool startup](ruby/README.md) | [Read](ruby/findings.md) | [Read](ruby/prospects.md) | [RuboCop experiment](../experiments/ruby_startup/README.md) |
| [.NET tool startup](dotnet/README.md) | [Read](dotnet/findings.md) | [Read](dotnet/prospects.md) | [Roslyn experiment](../experiments/dotnet_startup/README.md) |
| [Sharing work across consumers](workflows/README.md) | [Report](../experiments/workflows/results/combined-control/REPORT.md) | [Questions](workflows/README.md) | [Workflow experiments](../experiments/workflows/README.md) |
| [Prepared test workflows](testing/README.md) | [Read](testing/findings.md) | [Read](testing/prospects.md) | [Testing experiments](../experiments/testing/managed/README.md) |

[Component designs](../components/README.md) describe intended product behavior. These pages describe measured behavior and its limits. Experimental formats, worker processes and caches do not establish production services or public standards.

The compiler continuation examines [IR reuse, shared parsing and a production graph](compiler/followthrough/README.md). The managed continuation examines [longer queues, runtime discovery and native optimization](java/followthrough.md). The artifact continuation examines [shared data and cache lifetimes](artifacts/followthrough.md).

Each empirical topic has a machine-readable `experiments.json` linking its reports, validation and provenance. Full raw observations and profiler captures remain ignored local data; the [evidence manifest](evidence.json) records their sizes and hashes. A clean checkout includes the reports and instructions to reproduce them, rather than retained tools or original machine paths.
