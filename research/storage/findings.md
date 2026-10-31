# What the storage-service experiment establishes

The [first matched proof](../../experiments/storage/results/service-model/REPORT.md) holds the 455-module Django workload, compact index, logical bytes and per-read SHA-256/CRC checks fixed. Persistent installation is identical for both providers: two reads/29,263,010 bytes and three writes/29,263,283 bytes. Memory additionally imports/checks/copies/seals all 29,263,010 artifact bytes once; range demand uses 476 requests/6,736,215 bytes per fresh consumer.

At **1 ms per service request**, memory wins all three pairs: first total 919→376 ms and three-consumer session 2,716→987 ms, including installation and full admission. It avoids repeated service calls rather than interpreter execution or verification.

At **16 MiB/s read/write bandwidth**, full admission loses every pair: first total 4,347→5,621 ms and session 6,004→6,269 ms. Only part of the bundle is actually used; eager read amplification outweighs reuse over these three starts. The nominal zero-injection control has no reliable first/session advantage. Resident inputs help a latency-heavy boundary, but are not automatically best for bandwidth-limited demand.

All seven tests and 54 normal-exit application processes pass. Explicit range reads and sealed-memory access prevent private-file mmap from bypassing the model. Calibrations and exact request/byte assertions validate injected budgets; actual sleep overshoot is retained separately. These numbers are logical service calls, not physical disk IOPS. Warm page-cache reads would not necessarily encounter real block throttling, so no actual SSD/cold-storage or native compiler speedup follows from this result.
