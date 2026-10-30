# Zstandard compiler phases

Separate instrumented runs; artifact identities match the completed timed controls. Durations are summed job/event wall spans across eight workers, including descheduling. These are not CPU samples or independent additive stages: backend contains optimizer/code-generation subphases.

| Configuration | Sum job spans ms | Frontend ms | Backend ms | Optimizer ms | CodeGenPasses ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| release | 22082.05 | 2763.05 | 19098.08 | 11667.29 | 7372.93 |
| debug | 30756.80 | 3195.59 | 27029.88 | 14237.17 | 12728.47 |

The raw traces include every job and finer nested phases. Profiling overhead is excluded from all latency tables. The library configuration, optimization/debug flags and compiler lifecycle are unchanged. No compilation result is reused.
