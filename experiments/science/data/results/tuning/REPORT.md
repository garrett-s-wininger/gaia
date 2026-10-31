# Small bounded searches reach the same median policy

The model explores 12 discrete choices: chunk grouping widths 1/4/8/16 and cache budgets 32/64/128 chunks, all within the same 8 MiB upper allowance. Actual trace-derived requests feed a deterministic LRU model. Training uses the first Django consumer; normal held-out requests come from another fresh consumer, and reversed order plus different service coefficients is a synthetic phase-change stress.

Grid, random and mutation/selection search each receive six evaluations. The fixed 8-chunk/128-chunk default gets none. Mutation/selection keeps the best current candidate and perturbs one dimension; this is a bounded evolutionary-search surrogate, not a population simulation or proof of biological optimization.

| Strategy | Median search CPU/wall observation | Modeled training evaluations | Normal held-out model | Reversed/changed-profile model |
| --- | ---: | ---: | ---: | ---: |
| Fixed default | 0 ms | 0 s | 10.93 s | 20.10 s |
| Grid, six evaluations | 8.44 ms | 65.80 s | 2.84 s | 3.25 s |
| Random, six evaluations | 9.38 ms | 76.26 s | 2.84 s | 3.25 s |
| Mutation/selection, six evaluations | 5.41 ms | 45.41 s | 2.84 s | 3.25 s |

There are 20 searches across five seeds/blocks. All evaluation histories, including duplicates/nonwinning candidates, remain in raw evidence. Search execution time is actual Python elapsed time. The service costs are hypothetical if evaluating candidates required actual modeled reads; they are not elapsed network or disk measurements. Trace collection is external preparation. Nothing permits adding these synthetic costs to measured CPU time as one observed speedup.

The searches find better modeled choices than this fixed default but show no median held-out advantage for the evolutionary candidate over grid/random. The tiny space and repeated application trace limit generalization; unseen production workloads and model calibration remain necessary. Report every training/evaluation cost before selecting an adaptive policy.

[Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), [reproduce](../../README.md).
