# Sharing compiler work without sharing mutable compiler state

The [pass experiment](../../../experiments/science/compiler/results/passes-frozen/REPORT.md) and [shared-input experiment](../../../experiments/science/compiler/results/shared-inputs/REPORT.md) test complementary boundaries: private COW LLVM work after one frontend, and sealed input bytes shared by independent compiler workers. Read the [findings](findings.md), [prospects](prospects.md), [run index](experiments.json) and [reproduction instructions](../../../experiments/science/compiler/README.md).

The first pass-overlap/speculation policies do not establish a robust new performance win. Shared mappings reduce sampled worker PSS while leaving compiler state private. Neither result defines a portable AST, endorses fork inside a multithreaded service, or establishes an enforceable whole-process memory bound.
