# Compiler research

We have working prototypes and measurements for programmatic compilation, scheduling, local object reuse and incremental input preparation. They run on pinned Clang/LLVM/LLD with native Odin orchestration and narrow C++ adapters.

- [Findings](findings.md): what helped, what did not, and the practical limits.
- [Prospects](prospects.md): the next useful experiments and how to judge them.
- [Implementation and reproduction](../../experiments/compiler/README.md): commands and adapter details.
- [Run index](experiments.json): machine-readable evidence locations.
- [Lab journal](../../experiments/compiler/FINDINGS.md): detailed measurements and chronological reasoning.

The [compiler component](../../components/compiler/README.md) is the home for future product design. These experiments do not establish a production service or portable protocol.

Full raw observations and profiler captures are excluded from Git. Their original identities are recorded in the [evidence manifest](../evidence.json); raw files are local-only, with no published download location. Reports and validation summaries remain versioned.
