# Compiler tools

Working experiments now drive Clang and LLD through a native Odin host. They cover immutable inputs, bounded compiler workers, dispatch priority, native object handoff, object caching and dependency-query validation. These are research prototypes tied to a pinned Linux/LLVM configuration.

Start with the [findings](../../research/compiler/findings.md) and [prospects](../../research/compiler/prospects.md). [Implementation and reproduction](../../experiments/compiler/README.md) belong with the experiment code.

## The boundary to develop

A tool request needs explicit inputs, toolchain/configuration identity, lifetime and resource limits. A result can contain artifacts, diagnostics and observed input conditions. Observations may support reuse, including failed lookups that can change when a header appears.

Useful implementation policies include bounded workers, scheduling hints and local result reuse. Their performance and safety depend on workload, resource budgets and input contracts. A compiler crash can still terminate the current threaded prototype; a crash-isolated persistent service remains work to do.

No compiler-product MVP or portable wire protocol has been agreed. The current evidence should guide those designs. Keep this component separate from source-control landing/review policy and from an eventual artifact-host implementation.
