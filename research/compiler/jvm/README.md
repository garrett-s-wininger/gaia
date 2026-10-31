# Managed JVM compiler research

This track measures complete Java compilation through CLI and programmatic endpoints. It separates process lifetime, compiler execution, input delivery and memory. Groovy framework initialization has its own [startup research](../../java/README.md).

- [Findings](findings.md): useful results, negative results and practical limits.
- [Prospects](prospects.md): the next questions and the controls they need.
- [Initial invocation and delivery experiment](../../../experiments/java/compiler/README.md): jlink, compiler caches and complete-target queues.
- [Worker topology](../../../experiments/java/compiler/topology/README.md): one JVM versus many, with a separate memory trace.
- [Execution variants](../../../experiments/java/compiler/variants/README.md): GC, tiering, Leyden compiled-method caches and Native Image.
- [Run index](experiments.json): reports, validation and provenance for each study.

The experiments use pinned source targets and independent CLI output checks. Their timing windows and compiler versions differ; use controls within each report. Native-image SDK adaptation, cache construction and retained workers have separate preparation and compatibility costs. No production service or universal JVM policy is selected.
