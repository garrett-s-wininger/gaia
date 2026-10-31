# Storage-service latency/bandwidth sensitivity of a real Python consumer

Run `20261031T044325.699070Z`. Three paired blocks, 18 complete install/consumer sessions and 54 fresh normal-exit Python processes. Seven correctness tests pass.

## What this measures

This is an **application-storage-service model**, not a slowed physical disk, cold page cache or device/cgroup benchmark. Every modeled synchronous read/write request costs latency + bytes/rate regardless of the host page cache. No global cache flush, device throttle, cgroup change or unrelated-workload slowdown is performed. The zero-injection case retains the same instrumented API; it is not a zero-overhead implementation claim.

The real pinned Django REST workload uses the prior portable packed artifact/index, 455 dependency modules and the same code/API/admin/resource validation. Both providers apply **SHA-256 plus CRC32 to every logical read**, use the same compact tables and exit through normal provider/database/interpreter cleanup.

- **Range provider:** explicitly reads the index and issues positional payload reads on demand; it has no extra application byte cache between process starts. It never maps private file data. Index bytes are first read through the model, then copied to sealed memory for table access.
- **Admitted-memory provider:** imports the entire published payload/index through the model, checks both full artifact hashes, copies/seals them and shares those read-only memfds across fresh child interpreters. The full import/check/copy cost is charged before the first child. Consumers then need no modeled storage requests, while retaining all per-logical-read checks.

This boundary intentionally charges even OS-page-cache-hit reads because they cross the modeled service. It is useful for a latency-bearing storage/byte-provider API, and **must not be extrapolated to warm filesystem reads under actual block throttling**. Shared interpreter/stdlib/native-extension/harness and project-fixture code, metadata lookup and IPC are outside the injected artifact-data service and remain identical controls. They can still use ordinary OS I/O/mmap.

## Results with installation and admission included

First total includes persistent installation, memory admission where needed and the first complete Python process. Session total includes installation/admission and three complete fresh processes. Medians are milliseconds; independent columns need not add.

| Service profile / provider | Persistent install | Memory admission | First total | Three-consumer session | Memory paired wins first/session |
| --- | ---: | ---: | ---: | ---: | --- |
| nominal / range | 34.76 | 0.01 | 360.31 | 1008.03 | — |
| nominal / memory | 37.54 | 26.21 | 380.07 | 996.57 | 1/3 · 1/3 |
| request-latency / range | 44.27 | 0.01 | 919.27 | 2716.07 | — |
| request-latency / memory | 44.22 | 29.03 | 375.51 | 986.69 | 3/3 · 3/3 |
| bandwidth / range | 3528.49 | 0.01 | 4347.00 | 6003.68 | — |
| bandwidth / memory | 3531.79 | 1772.88 | 5621.01 | 6269.32 | 0/3 · 0/3 |

The request-latency profile is **1 ms per read or write request**, with unlimited modeled byte rate. Admitted memory reduces first total **919→376 ms** and three-consumer total **2,716→987 ms**, winning all three pairs. It avoids repeated service requests, not Python execution or verification.

The bandwidth profile is **16 MiB/s independently for reads and writes**, with no added request latency. Full memory import loses all pairs: first total **4,347→5,621 ms**, session **6,004→6,269 ms**. Range demand reads only the bytes actually consumed; eagerly importing the whole bundle overfetches. The nominal case has no reliable first/session win (one of three pairs), despite small median differences. No universal in-memory speedup follows.

## Exact byte/request accounting

| Boundary | Read calls / bytes | Write calls / bytes |
| --- | ---: | ---: |
| Persistent installation, either provider | 2 / 29,263,010 | 3 / 29,263,283 |
| Additional full memory admission, once/session | 2 / 29,263,010 | 0 / 0 |
| One range consumer | 476 / 6,736,215 | 0 / 0 |
| One admitted-memory consumer | 0 / 0 | 0 / 0 |

Each consumer still makes **475 verified logical reads / 6,063,442 bytes**. The range service adds one 672,773-byte index read. Persistent installation reads both producer artifacts, verifies their pins and complete index geometry, writes both artifacts and a completion receipt. Writer buffers end with that service; the independent memory consumer subsequently imports from the published cache. It does not receive an uncharged pre-admitted payload from setup.

There is no ordinary-file extraction/materialization requirement for this consumer: code/templates/resources stay behind the provider. Required persistent artifact writes are included for both. The memory path pays full import, checksum and sealing, including temporary staging/copy memory; no process-RSS or minimum-memory-footprint claim is made. This is not evidence for a consumer that requires exported filesystem paths.

## Calibration and timing limits

Calibration reads/writes 64 KiB and 1 MiB buffers through the same service before main. Requested/observed sleep is **0/0 ms nominal**, **4.00/4.26 ms request latency**, and **132.81/133.31 ms bandwidth**. Actual read/write and atomic-publication work remains inside elapsed time. Sleeping acknowledges modeled service completion after real buffered writes; it does **not** fsync or prove hardware durability/writeback completion.

For three-consumer sessions, requested/observed injected sleep medians are **1,433/1,560 ms** range versus **7.00/7.82 ms** memory in the request profile, and **4,692.97/4,823.03 ms** versus **5,232.65/5,233.78 ms** in the bandwidth profile. Per-call timer/scheduler overshoot is visible and is not called exact hardware IOPS or bandwidth. [Summary](summary.json) retains every paired delta, calibrations and counters; raw observations retain child read/hash/setup clocks.

## Isolation, integrity and scope

The modeled dependency-artifact source/cache/receipt paths are private experiment paths. Range reads are explicitly audited against consumer logical reads and bytes; tests audit that private data is not file-mapped. Memory mode accepts only fully sealed descriptors and rejects ordinary file descriptors; tests prove write/resize refusal, detached snapshots and read-only mappings. Both index and requested payload corruption fail. All 54 processes match dependency origins/executions, versions, API/admin output and resource pins. The [validation](validation.json) and [seven-test log](correctness-tests.txt) retain these assertions.

The [capability inventory](capabilities.json) finds no effective capabilities, a read-only cgroup mount and no FUSE/userfaultfd device. A user-mode-only userfaultfd syscall nevertheless succeeds; sysctl zero alone does not prohibit that restricted API. No pager was built for this proof. Mechanism choices and authoritative references are explained in the [design/reproduction guide](../../README.md).

The existing pinned bytecode/artifact production and copying the reusable producer fixture are common setup, not part of client installation; input hashes and [wheel provenance](provenance.json) are retained. Python/version compatibility, warm host pages and Linux sealed-memfd support remain prerequisites. Full raw observations are ignored local data identified by [their portable identity](raw-identity.json); exact measured sources remain frozen alongside work data.

This first proof covers artifact/Python sensitivity only. It neither measures Ninja/Clang physical-disk behavior nor repeats a native mmap benchmark under a new label. A native follow-up needs an equally explicit input/publication boundary or verified private cold/block conditions. The practical result is a tradeoff: retaining verified inputs helps when request latency dominates, while full admission can lose when bandwidth and unused bytes dominate.
