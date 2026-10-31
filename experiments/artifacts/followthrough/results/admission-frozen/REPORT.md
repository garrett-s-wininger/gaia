# Demand admission: choose the request and byte budget together

A shared chunk service lets fresh Django processes execute real framework code before all dependency reads finish. Small chunks reduce bytes admitted across repeated starts, while larger chunks reduce requests. Full admission wins the latency-heavy case here; fine demand admission has the lowest three-start bandwidth-limited session time. No one policy wins every clock.

## Frozen confirmation

This is one randomized matched block of four policies and three service profiles, with three fresh normal-exit consumers per session: 36 application processes. Source snapshots and SHA-256 identities are captured before execution and checked unchanged afterward. A preceding [three-block exploratory matrix](../admission/REPORT.md) is retained separately because a constructor resource-cleanup fix occurred during it. Its medians are not primary confirmation statistics.

The index is 672,773 bytes and the payload 28,590,237 bytes. Persistent installation is identical for all policies: two reads/29,263,010 bytes and three writes/29,263,283 bytes. Every fresh child additionally reads/verifies the index. Payload service operations below are in addition to that common traffic.

| Policy | Payload bytes fetched over three starts | Payload service reads | Retained chunk bytes |
| --- | ---: | ---: | ---: |
| Exact ranges, no retention | 18,190,326 | 1,425 | 0 |
| Demand 4 KiB | 7,626,752 | 1,862 | 7,626,752 |
| Demand 64 KiB | 20,660,381 | 316 | 20,660,381 |
| Full admission | 28,590,237 | 1 | 28,590,237 |

A 4 KiB chunk can cross multiple logical file reads, but it also splits larger reads into many source operations. The 64 KiB case fetches about 72% of the payload because used files are distributed through the bundle. The appropriate granularity depends on request cost, bandwidth, locality and reuse.

## Complete observed clocks

Installation, admission, service setup, child startup, actual framework operation and normal child exit are included. The table shows this single block's first-consumer total and complete three-consumer session, in seconds. It is not a confidence interval or a universal ranking.

| Service profile | Policy | First consumer | Three-consumer session |
| --- | --- | ---: | ---: |
| Nominal | Exact range | 0.816 | 2.254 |
| Nominal | Demand 4 KiB | 0.930 | 2.246 |
| Nominal | Demand 64 KiB | 1.088 | 2.459 |
| Nominal | Full | 0.746 | 2.198 |
| 1 ms per logical request | Exact range | 1.601 | 4.552 |
| 1 ms per logical request | Demand 4 KiB | 4.272 | 5.751 |
| 1 ms per logical request | Demand 64 KiB | 2.022 | 3.797 |
| 1 ms per logical request | Full | 0.933 | 2.380 |
| 16 MiB/s reads and writes | Exact range | 5.215 | 8.594 |
| 16 MiB/s reads and writes | Demand 4 KiB | 5.961 | 7.519 |
| 16 MiB/s reads and writes | Demand 64 KiB | 6.674 | 9.165 |
| 16 MiB/s reads and writes | Full | 6.754 | 8.351 |

The demand policies retain verified chunks across otherwise fresh interpreters. Producer SHA-256 chunk-manifest construction took 72 ms for both chunk sizes together; its hashes are derived from the pinned payload. This producer work is reported separately, not hidden in consumer admission. Manifest storage for both granularities is reported in raw observations. The index and each requested logical file retain their preceding integrity checks.

## What interleaving establishes

An audit records first Django code execution. For every range/demand session, that execution precedes the final first-consumer payload fetch. Full admission finishes fetching before framework execution. This proves real consumer work is interleaved with partial delivery. Reads remain synchronous: no independent transport/CPU overlap, multiplexed WAN transfer or progressive-stream scheduling advantage has been demonstrated.

All policies use the same Python Unix-socket dispatch and data-copy path, including full admission. It is a correctness-friendly provider adapter, not an optimized native transport. Its overhead and ordinary host variation are visible even with nominal modeled cost; these results must not be compared directly with earlier direct-mapping startup numbers. The measurements use warm host pages and injected application-service read/write latency/bandwidth. They neither throttle a physical disk nor measure a real network.

## Correctness and follow-up

All 36 processes preserve module origins/execution counts, WSGI/API results, resource hashes and app counts. Per-file SHA-256/CRC32 remains enabled; demand chunks verify trusted producer hashes before publication. The first admission matrix adds another 108 successful processes. Six focused admission unit tests cover bounds, chunk corruption, exact charged full admission, budget enforcement, cross-chunk reads and zero retention.

[Summary](summary.json) and [validation](validation.json) pin the ignored raw `results.json` by SHA-256 and length. That raw file contains the complete request/byte/wait counters, per-child results, timing observations and source identities. The source snapshot lives in the ignored work directory. Linux/Python/producer reproduction instructions are in the [guide](../../README.md).

Next compare adaptive/coalesced requests and bounded prefetch with this same consumer, and measure explicit independent useful-work overlap. Keep first-use and multi-consumer session clocks, producer cost, bytes and residency visible. A better native adapter is needed before attributing nominal overhead to the admission policy.
