# Compiler tools

This component concerns explicit tool requests: admitted inputs, toolchain/configuration identity, execution budgets and returned artifacts, diagnostics and observed dependencies. Working native and managed-language experiments inform the boundary; no compiler-product MVP or portable protocol has been agreed.

## Research to read

| Area | Findings and implementation |
| --- | --- |
| Native invocation and reuse | [Compiler findings](../../research/compiler/findings.md), [Clang/LLVM/LLD experiments](../../experiments/compiler/README.md) |
| Input identity and lifetime | [Immutable input contract](immutable-input-research.md), including sealed segments and authoritative logical generations |
| Object invalidation | [Semantic reuse](../../experiments/compiler/semantic_invalidation/README.md): AST candidate fingerprints and exact IR checks under fixed compiler context |
| JVM execution and workers | [Managed compiler findings](../../research/compiler/jvm/findings.md), [JVM experiments](../../experiments/java/compiler/README.md) |

The native host uses Odin with narrow C++ compiler adapters. JVM studies cover programmatic invocation, private whole-target workers, GC/JIT policy, prepared caches and Native Image. Experimental compiler-specific identities do not establish a cross-language cache format. Target SDKs, initial admission, filesystem compatibility and retained memory remain explicit costs.

## The boundary to develop

A result can include artifacts, diagnostics and input observations. Those observations may support selective reuse, including failed lookups that can change when a header appears. An API-owned immutable workspace and a mutable-directory adapter require different update and stability contracts.

Worker limits, scheduling hints and local result reuse are policies whose value depends on workload and resource budgets. Cancellation, crash isolation, processor/plugin behavior and long-lived memory bounds remain open. A native compiler failure can still terminate its current threaded prototype.

The [prospects](../../research/compiler/prospects.md) and [JVM next questions](../../research/compiler/jvm/prospects.md) identify the remaining measurements. Keep execution separate from source-control review/landing policy, CI orchestration and artifact-host retention policy.
