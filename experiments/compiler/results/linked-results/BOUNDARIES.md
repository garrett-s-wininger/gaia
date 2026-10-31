# Complete-result compile-heavy correctness

One independently restored observation per engine/scenario. These single timings support correctness only. Unretained BLAKE3, original retention and completion reuse/resident checking all pass:

| Scenario | Compilers | Reused/new fragments | Validation/compiler trees |
| --- | ---: | --- | --- |
| Real high-fanout header | 26 | 5 / 26 | 1 / 26 |
| Changed global flags | 31 | 0 / 31 | 0 / 31 |
| Clean build | 31 | 0 / 31 | 0 / 31 |

All nine libraries and 279 object identities match independent CLI references and runtime probes. No candidate is reused when the request/conditions differ. New retention entries publish on successful misses, and the new path must use completion-record rebinding. Clean requests have no retained entries or fragments. The checker releases request allocations before acknowledgement. Native compiler/producer launches remain zero because the explicitly recorded seeds start resident compiler processes.

[Validation](boundary-validation.json) binds ignored `boundary-raw/results.json`; [summary](boundary-summary.json) retains work counts, memory, source hashes and cache accounting. The two matched runs plus these checks validate 387 libraries and 11,997 object checks.
