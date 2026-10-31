# Sharing native compiler work

This follow-up tests one frontend feeding IR reuse, code generation and a small detached analysis. It also probes which invocation inputs must be declared before reuse is safe.

- [Findings](findings.md) explain the measured gains and limits.
- [Prospects](prospects.md) identify the missing integration boundaries.
- [Run index](experiments.json) connects reports, summaries and raw identities.
- [Implementation and reproduction](../../../experiments/compiler/followthrough/README.md) describe the experimental host and controls.

These are bounded Clang 22 experiments. They do not select a stable AST format, public service protocol or production graph scheduler. The broader [native compiler findings](../findings.md) retain the earlier lifecycle, input-generation and Ninja comparisons.
