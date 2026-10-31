# Digest-provider compile-heavy correctness

One independent observation per engine/scenario, supporting correctness only. LLVM SHA-256, OpenSSL SHA-256 and BLAKE3 all pass:

| Scenario | Compilers per engine | Reused/new fragments | Validation/compiler trees |
| --- | ---: | --- | --- |
| Real high-fanout header | 26 | 5 / 26 | 1 / 26 |
| Changed global flags | 31 | 0 / 31 | 0 / 31 |
| Clean build | 31 | 0 / 31 | 0 / 31 |

All nine libraries and 279 object identities match independent CLI references and runtime probes. BLAKE3 snapshots carry tagged pins and their new header, and the current exporter consumes their new journal version. Each engine has its own serial worker and per-request state is released before completion. Cache record/fragment checks and expected zero new native processes all pass.

[Validation](boundary-validation.json) binds ignored `boundary-raw/results.json`; [summary](boundary-summary.json) retains counters and source hashes. Timings are single observations and support no compile-heavy speed claim.
