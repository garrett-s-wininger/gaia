# Sharing current workspace knowledge and using CPU vectors

The [additional-project study](generalization/README.md) tests frozen reuse rules and bounded frontend/backend overlap on xxHash, spdlog, re2c and curl. The [workspace refinement](refinements/README.md) measures earlier publication, cached identities and precise configuration/result reuse on the original fixture.

These experiments combine earlier mechanisms in actual operations rather than adding another policy model. Start with the [findings](findings.md), [next questions](prospects.md), [run index](experiments.json), and [reproduction map](../../experiments/integration/README.md).

The workspace experiment connects admitted source generations, real Clang observations, a project declaration index and production Ninja outputs. Its controls include concurrently running independently cached consumers and Ninja + ccache. The SIMD experiment evaluates exact dependency-set unions with optimized loops, explicit vector widths and sparse lists. Native kernel gains remain separate from complete workflow gains.

A [created-header cache diagnostic](../../experiments/integration/workspace/results/negative-cache/REPORT.md) explains why the first control was rejected and how the corrected fixture preserves output equivalence. Fixed-context compiler adapters, explicit source admission and generated-query tests do not establish a production service, hard memory quota or public protocol.
