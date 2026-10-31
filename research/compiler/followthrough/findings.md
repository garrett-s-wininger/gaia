# What sharing frontend work establishes

## Current IR can continue directly on a miss

The [single-frontend study](../../../experiments/compiler/followthrough/results/ir/REPORT.md) removes the previous prototype's repeated frontend. A heavy unused-typedef edit takes 75.62 ms through current IR versus 3,710.98 ms for seeded ccache, with all three paired wins. A real semantic edit still takes about 3.46 seconds because optimization/code generation remains necessary; the current module reaches that backend without reparsing.

This is not a replacement for ordinary content lookup. An unchanged heavy input takes 9.34 ms through ccache's direct path versus 77.92 ms through IR screening; ccache also wins the heavy comment comparison. The useful design is an inexpensive exact-input fast path followed by deeper screening where the frontend has meaningful information.

All 90 matched objects equal independent CLI outputs. Current frontend warnings and dependency files still run on object hits. Backend errors fail the request, workers recover from the tested assembly error, and entries with backend diagnostics are not retained. Optimization remarks and arbitrary compiler side products remain outside the prototype's contract.

## Shared parsing saves work without necessarily beating parallel workers

The [strong parallel control](../../../experiments/compiler/followthrough/results/analysis-parallel/REPORT.md) compares one shared frontend with two separate initialized workers. For the small TU, independent parallel parsing/compilation takes 51.95 ms versus shared serial's 51.13 ms. Sampled aggregate worker CPU falls from about 100 to 50 ms at 10 ms counter granularity. Shared parallel execution takes 54.76 ms, so another thread does not establish a latency improvement for this small analysis.

The heavy TU remains backend dominated at roughly four seconds. The surrogate analysis hashes detached declaration names; it is not a production linter or evidence that arbitrary AST passes can run concurrently. The implementation shares the AST sequentially with consumers, then allows independent immutable records to outlive that access while the backend runs. Clang's mutable/lazy AST state is not accessed concurrently.

## Source bytes do not describe every invocation

The [identity probes](../../../experiments/compiler/followthrough/results/reproducibility/REPORT.md) expose absolute path/debug identity, environment-selected headers, date/time configuration and ordered archive inputs. Explicit path maps restore equality in the tested pair; sorting ordered archive members restores the reference archive. Equal output under two selected locales does not prove general locale independence.

The source-provider tests also demonstrate a metadata limitation: normalized in-memory mtimes change expanded `__TIMESTAMP__`. Supported logical-graph commands reject date/time builtins through `-Werror=date-time`; a general contract needs explicit metadata/environment semantics instead of silently replacing physical files with byte arrays.

## A larger production graph works within a fixed dependency trace

The [Ninja production-graph prototype](../../../experiments/compiler/followthrough/results/graph/REPORT.md) builds 33 upstream C++ translation units from admitted source bytes. Against one-worker Ninja plus baseline-seeded ccache, source edits take 448.51 versus 597.23 ms and generated-input edits take 439.36 versus 564.53 ms, with three of three paired wins in each case. Header and configuration comparisons vary more; the configuration median's small advantage is not a reliable general build win. Initial full builds are sequential preparation observations, not randomized cold-build evidence.

Every measured operation preserves all object/executable identities against the CLI. A small editor interaction inspects and compiles the same admitted unsaved generation and rejects stale compile/update requests. The source-root filesystem fails closed on omitted project headers; the final adapter imports actual baseline project dependencies.

This runner's scheduling uses a fixed baseline dependency map and known generator rules. It does not refresh dependencies or record negative include queries, so it is not a sound generic scheduler for newly introduced includes or optional-header appearance. The stronger logical-condition checker has not yet been integrated into this production graph. Source generations, physical SDK access, generated-file execution and completion publication remain distinct boundaries.
