# Exploratory demand-admission matrix

This three-block matrix completed 108 fresh normal-exit Django processes with matching application behavior and per-file SHA-256/CRC32 checks. It is exploratory: `admission.py` received a constructor resource-cleanup fix during execution. The changed lines move opening the payload stream until after argument/manifest geometry validation. Measured valid-input behavior is unchanged, but the run did not snapshot/check every loaded source version before and after execution.

The separate [frozen confirmation](../admission-frozen/REPORT.md) is the primary reproducible result. Keep this matrix to expose variation and the complete deterministic byte/request observations; do not promote its medians as frozen-source measurements.

Across three consumers, payload service traffic is deterministic: range 18,190,326 bytes/1,425 reads; demand 4 KiB 7,626,752 bytes/1,862 reads; demand 64 KiB 20,660,381 bytes/316 reads; full 28,590,237 bytes/one read. Index reads and identical persistent installation are additional and charged. Smaller chunks reduce overfetch while increasing per-request latency cost.

Raw observations remain in ignored `results.json`. [Summary](summary.json) and [validation](validation.json) retain its SHA-256 identity and measured outcomes. The model applies logical application-service latency/bandwidth to warm host files; there is no physical-device or real-network claim.
