# Experiments

This directory contains runnable research, technical lab notes and measured evidence. Start with the [research guide](../research/README.md) for conclusions and the [reproduction guide](reproducing.md) for setup and experiment order.

| Area | Code and reproduction | Evidence index |
| --- | --- | --- |
| Shared workspace, SIMD and dispatched hashing | [integration](integration/README.md) | [Integration runs](../research/integration/experiments.json) |
| Native facts, ownership and source discovery | [connections](connections/README.md) | [Connection runs](../research/connections/experiments.json) |
| Transformations and shared computation | [science](science/README.md) | [Coverage](../research/science/coverage.md) |
| Native compiler tools | [compiler](compiler/README.md) | [Compiler runs](../research/compiler/experiments.json) |
| C++ dependency graph | [compiler/cpp_graph](compiler/cpp_graph/README.md) | [Compiler runs](../research/compiler/experiments.json) |
| Managed JVM compilers | [java/compiler](java/compiler/README.md) | [JVM compiler runs](../research/compiler/jvm/experiments.json) |
| Artifact transfer and access | [artifacts](artifacts/README.md) | [Artifact runs](../research/artifacts/experiments.json) |
| Storage-service sensitivity | [storage](storage/README.md) | [Storage runs](../research/storage/experiments.json) |
| Python dependency loading | [python/dependency_bundles](python/dependency_bundles/README.md) | [Python runs](../research/python/experiments.json) |
| Python resolution | [python/dependency_solving](python/dependency_solving/README.md) | [Python runs](../research/python/experiments.json) |
| Python/Node interpreter state | [python/interpreter_snapshots](python/interpreter_snapshots/README.md) | [Python runs](../research/python/experiments.json) |
| JVM framework startup | [java/startup](java/startup/README.md) | [JVM startup runs](../research/java/experiments.json) |
| Ruby tool startup | [ruby_startup](ruby_startup/README.md) | [Ruby runs](../research/ruby/experiments.json) |
| .NET tool startup | [dotnet_startup](dotnet_startup/README.md) | [.NET runs](../research/dotnet/experiments.json) |
| Repository queries, schema sharing and checkpoints | [workflows](workflows/README.md) | [Workflow runs](../research/workflows/experiments.json) |
| Prepared test environments and discovery | [testing/managed](testing/managed/README.md) | [Testing runs](../research/testing/experiments.json) |

The [Java overview](java/README.md) distinguishes framework startup from managed compilation and their different preparation contracts.

The compiler continuations include [semantic object reuse](compiler/semantic_invalidation/README.md), [JVM worker topology](java/compiler/topology/README.md), [GC/JIT and native execution](java/compiler/variants/README.md), and [JVMTI framework profiling](java/startup/jvmti/README.md). Their timing and compatibility boundaries remain separate.

New continuations cover [single-frontend compilation and source generations](compiler/followthrough/README.md), [JVM lifetime/runtime discovery/profile controls](java/followthrough/README.md), and [artifact admission, cache growth and cross-runtime catalogues](artifacts/followthrough/README.md).

Reports, acquisition manifests, provenance and compact validation summaries belong in Git. Downloads, built tools, caches, full observations and profiler captures stay ignored. The [evidence manifest](../research/evidence.json) identifies retained raw data by path, size and hash; those files have no separately published download location.

Each experiment owns its reproduction README and reports under `results/`. Detailed `FINDINGS.md` files are lab notes; current interpretations live under `research/`. Generate fresh inputs and adapters on the machine being measured. Commands in retained observations describe their original environment and should not be replayed with the recorded absolute paths.
