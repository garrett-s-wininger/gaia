# Where shared native work should go next

The current IR pipeline is ready to connect to the stronger admitted-input and observed-condition checker. Keep the exact-content fast path, continue the same current module on misses, and preserve ordinary diagnostics, dependency outputs and debug identity. Investigate useful edit mixes before pursuing finer-grained function reuse; whole-module equality is the only object-reuse boundary measured here.

Use a real analysis consumer next. The detached-name surrogate establishes a lifecycle and CPU-sharing mechanism, while the separate parallel control shows why removing a parse need not improve latency when another worker can overlap it. Measure analysis facts, their construction/retention costs and actual consumer requirements before selecting a portable representation. Version-specific compiler ASTs should remain implementation details unless a stronger interchange contract is designed.

The production C++ trace needs dynamic observed dependencies and negative include conditions before it can become a generic scheduler. Refreshing positive depfiles alone does not cover optional-header appearance or include shadowing. Connect the existing stronger logical-condition checker rather than treating a baseline dependency map as complete authority validation. Keep generated-input execution, compiler configuration and linker inputs explicit.

Extend metadata and environment identity deliberately: source locations, time-sensitive builtins, generated files, profile inputs, plugins and target SDK namespaces can affect outputs. Retain the current counterexamples and source/binary freeze checks. The prototype's JSON requests and serial single-generation lifetime are experimental conveniences, not a selected Gaia protocol.
