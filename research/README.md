# Research

Start with [what we learned](findings.md) and [what to try next](prospects.md). The topic guides explain the evidence without requiring the experiment chronology or task IDs.

| Topic | Findings | Next questions | Code and reproduction |
| --- | --- | --- | --- |
| [Native compiler execution and input reuse](compiler/README.md) | [Read](compiler/findings.md) | [Read](compiler/prospects.md) | [Compiler experiments](../experiments/compiler/README.md) |
| [Managed JVM compilers](compiler/jvm/README.md) | [Read](compiler/jvm/findings.md) | [Read](compiler/jvm/prospects.md) | [Java compiler experiment](../experiments/java/compiler/README.md) |
| [Artifact transfer and local access](artifacts/README.md) | [Read](artifacts/findings.md) | [Read](artifacts/prospects.md) | [Artifact experiments](../experiments/artifacts/README.md) |
| [Python loading/resolution and Python/Node state reuse](python/README.md) | [Read](python/findings.md) | [Read](python/prospects.md) | [Python experiments](../experiments/python/README.md) |
| [JVM framework startup](java/README.md) | [Read](java/findings.md) | [Read](java/prospects.md) | [Groovy/Picocli experiment](../experiments/java/startup/README.md) |
| [Ruby tool startup](ruby/README.md) | [Read](ruby/findings.md) | [Read](ruby/prospects.md) | [RuboCop experiment](../experiments/ruby_startup/README.md) |
| [.NET tool startup](dotnet/README.md) | [Read](dotnet/findings.md) | [Read](dotnet/prospects.md) | [Roslyn experiment](../experiments/dotnet_startup/README.md) |

[Component designs](../components/README.md) describe intended product behavior. These pages describe measured behavior and its limits. Experimental formats, worker processes and caches do not establish production services or public standards.

Each topic has a machine-readable `experiments.json` linking its reports, validation and provenance. Full raw observations and profiler captures remain ignored local data; the [evidence manifest](evidence.json) records their sizes and hashes. A clean checkout includes the reports and instructions to reproduce them, rather than retained tools or original machine paths.
