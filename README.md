# Gaia

Gaia explores a faster, simpler development environment: source control, dependency access, compiler execution, an editor and artifact hosting. Native code uses Odin. The starting target is a Linux developer laptop, with a local experience that needs no separately provisioned infrastructure.

We are testing whether explicit inputs, reusable tool processes and direct data access can replace repeated filesystem discovery and process startup. Some experiments have produced useful gains; others have shown where that approach stops helping. The designs and measurements have different maturity levels.

## Start here

- [What we have learned](research/findings.md): the useful results, disappointments and limits in plain language.
- [What looks worth trying next](research/prospects.md): prioritized experiments and the questions they would answer.
- [Platform direction](docs/platform.md): how the pieces fit together and the boundaries we want to preserve.
- [Component map](components/README.md): source control, dependencies, compiler tools, editor and artifact host.
- [Repository guide](docs/repository-layout.md): where designs, research, code and evidence belong.

## Components

| Component | Current state |
| --- | --- |
| [Source control](components/source-control/README.md) | Agreed MVP behavior and first local-engine milestone; implementation has not started. |
| [Dependencies](components/dependencies/README.md) | Python loading and resolution experiments; broader interfaces remain open. |
| [Compiler tools](components/compiler/README.md) | Working research prototypes for invocation, scheduling, caching and input preparation. |
| [Editor](components/editor/README.md) | Scope and integration questions; no implementation or agreed MVP yet. |
| [Artifact host](components/artifact-host/README.md) | Scope and integration questions; no service or remote protocol yet. |

[Experiments](experiments/README.md) contain runnable research and retained evidence. They are not production implementations or standardized protocols. Use the [reproduction guide](experiments/reproducing.md) to generate inputs and results on your machine.
