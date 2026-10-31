# Storage-service sensitivity

This track measures how artifact/consumer designs respond to explicitly modeled read/write request cost. The first proof reuses the real pinned Django dependency workload and compares packed positional reads with fully admitted sealed memory.

- [Findings](findings.md): latency wins, bandwidth losses and complete cost boundaries.
- [Prospects](prospects.md): real storage validation, demand granularity and native follow-up conditions.
- [Run index](experiments.json): reports, validation, provenance and raw identity.
- [Experiment/design/reproduction](../../experiments/storage/README.md).
- [Human report](../../experiments/storage/results/service-model/REPORT.md), [summary](../../experiments/storage/results/service-model/summary.json) and [validation](../../experiments/storage/results/service-model/validation.json).

This is application-storage-service evidence. It does not simulate global disk throttling, prove cold physical I/O or infer native compiler behavior from Python results.
