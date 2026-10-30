# mmap prefault experiment

Run: `20261028T214337.292713Z`.

Warm/reused filesystem cache, fresh process/mapping per trial. Identical immutable ZIP bytes within each corpus. All modes parse and validate the same index and verify CRC on every scan; full SHA-256 equivalence is checked after timing. Population is charged to open/index time. `populate` requests Linux MAP_POPULATE at mapping creation; `touch` reads one byte per page immediately after mapping. `none` faults on demand. Population is not a residency guarantee.

15 randomized trials per case; four scans per process, lexical order. Views avoid payload copies; bytes mode returns copied bytes. First use is each sample's index + first scan, then median. Fault counts are process-wide getrusage deltas, including Python allocations; they are not a count of archive pages. Fault counters bracket, but are outside, each timed interval.

| Corpus | Result | Prefault | Index ms | First scan ms | Reused scan ms | First use ms | Index minor faults | First scan minor faults | Major faults, index + scans |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tiny entries | bytes | none | 32.573 | 1.910 | 1.760 | 34.471 | 430 | 0 | 0 |
| tiny entries | bytes | populate | 32.639 | 1.707 | 1.626 | 34.322 | 433 | 0 | 0 |
| tiny entries | bytes | touch | 32.166 | 1.715 | 1.692 | 33.956 | 432 | 0 | 0 |
| tiny entries | view | none | 31.131 | 1.715 | 1.821 | 32.992 | 430 | 0 | 0 |
| tiny entries | view | populate | 32.792 | 1.696 | 1.725 | 34.829 | 433 | 0 | 0 |
| tiny entries | view | touch | 32.499 | 1.655 | 1.496 | 34.422 | 433 | 0 | 0 |
| 1 MiB entries | bytes | none | 6.780 | 32.129 | 27.370 | 38.876 | 80 | 1251 | 0 |
| 1 MiB entries | bytes | populate | 10.109 | 29.080 | 26.484 | 38.930 | 337 | 994 | 0 |
| 1 MiB entries | bytes | touch | 8.642 | 29.319 | 26.993 | 38.259 | 337 | 994 | 0 |
| 1 MiB entries | view | none | 5.367 | 24.518 | 23.176 | 30.593 | 80 | 257 | 0 |
| 1 MiB entries | view | populate | 10.600 | 23.778 | 23.028 | 34.591 | 337 | 0 | 0 |
| 1 MiB entries | view | touch | 8.195 | 23.408 | 23.222 | 31.954 | 337 | 0 | 0 |

## Corpora

- tiny entries: 2,104 entries, 429,600 payload bytes, 744,838 archive bytes; SHA-256 `2e6c927afac97a19d75a51022083274fa816175abd2c7cacf837fcbc0fcec6db`.
- 1 MiB entries: 64 entries, 67,108,864 payload bytes, 67,115,670 archive bytes; SHA-256 `caa6c7308dbcae6ffd033293bd17ab4b772b283b620324d9e003f0037078f1ae`.

## Limits

No cache dropping or cold-storage measurement. A warm page cache still requires page-table population for a fresh mapping. Minor faults may map multiple pages (fault-around), so explicit touching need not produce a fault per page. Header validation itself touches mapping pages. This synthetic full-scan experiment does not test sparse consumption, working sets exceeding RAM, concurrent consumers, sustained memory pressure, or native-language implementations. Eager whole-file population can load unused data in those cases. Setup is synchronous; no work overlaps useful execution. No language/compiler changes or end-to-end loader improvement are inferred from this access-only run.
