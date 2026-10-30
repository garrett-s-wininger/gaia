# Unified and compact mapped metadata experiment

Run: `20261029T131301.330434Z`. Status: **complete**.

Same archives and admitted range-index contents across all cases; same freshly compiled bridge, bytes+slice handoff and reconstructed stdlib reader. Warm filesystem cache, 15 randomized fresh processes per case after correctness warmups.

* mapped: original range index plus mapped 64-bit lookup artifact, two metadata hashes/maps.
* unified: same embedded range index and sparse 64-bit tables in one authenticated envelope.
* compact: unified envelope with eligible 32-bit offsets/ordinals/counts, independent file/module table sizing and a maximum 75% load factor. It falls back to the 64-bit layout if counts or embedded-index offsets do not fit. Names and payload range records are unchanged.

Experimental unified v1 has a 256-byte explicit-width/endianness header and embedded original range index, directory offset/length records, and mapped hash/child arrays. No pointers are serialized. The trusted SHA pin authenticates the entire envelope, including embedded index bytes. Its original-index SHA field is producer-certified lineage checked against the requested input; the embedded index is not separately rehashed. Thus one envelope hash replaces two independent metadata hashes without leaving embedded bytes unauthenticated. Trusted producer lookup semantics, range/UTF-8/table-domain/count checks, bounded probing and iteration, archive identity/full-hash policy and per-read CRC remain.

| Input | Mode | Metadata bytes | Producer ms |
| --- | --- | ---: | ---: |
| django | mapped | 686150 | 0.000 |
| django | unified | 686152 | 14.904 |
| django | compact | 434712 | 77.961 |
| 1024 | mapped | 135831 | 0.000 |
| 1024 | unified | 135832 | 1.936 |
| 1024 | compact | 74304 | 15.049 |
| 16384 | mapped | 2163351 | 0.000 |
| 16384 | unified | 2163352 | 21.620 |
| 16384 | compact | 1180224 | 243.302 |
| 131072 | mapped | 17302167 | 0.000 |
| 131072 | unified | 17302168 | 232.275 |
| 131072 | compact | 9437760 | 2074.228 |

Mapped production is inherited from the parent report; zero in this table means no new production in this run. Unified/compact production includes validation of retained inputs and transformation; the original mapped-artifact production cost remains separate. Every startup includes all metadata mapping, authentication and structural validation.

| Workload | Mode | Setup median ms | Ready/workload median ms | Process median ms | Peak RSS MiB |
| --- | --- | ---: | ---: | ---: | ---: |
| django | mapped | — | 368.766 | 722.688 | 66.30 |
| django | unified | — | 361.896 | 718.934 | 66.33 |
| django | compact | — | 374.612 | 736.301 | 66.02 |
| 1024 | mapped | 0.874 | 2.251 | 154.617 | 21.62 |
| 1024 | unified | 0.865 | 2.458 | 158.518 | 21.64 |
| 1024 | compact | 0.842 | 2.154 | 157.995 | 21.57 |
| 16384 | mapped | 4.139 | 5.604 | 155.737 | 23.57 |
| 16384 | unified | 4.303 | 5.662 | 154.068 | 23.56 |
| 16384 | compact | 2.953 | 4.403 | 161.079 | 22.61 |
| 131072 | mapped | 26.124 | 27.994 | 184.285 | 38.00 |
| 131072 | unified | 29.028 | 30.848 | 186.316 | 37.97 |
| 131072 | compact | 16.583 | 17.886 | 173.848 | 30.48 |

Scaling imports remain the same 32 leaves plus initializer. Validation happens afterward without materializing unused siblings; Python name/query counters must remain small. Full process/RSS include common harness and validation. Django preserves all application origins/executions, responses, resources, source inspection and no-network checks.

| Workload | Mode | Integrity ms | Structure/setup ms | Native open ms | Primary min–max ms |
| --- | --- | ---: | ---: | ---: | ---: |
| django | mapped | 0.930 | 0.528 | 1.677 | 343.333–410.185 |
| django | unified | 0.759 | 0.677 | 1.552 | 319.896–414.920 |
| django | compact | 0.489 | 0.580 | 1.180 | 357.705–410.497 |
| 1024 | mapped | 0.214 | 0.057 | 0.353 | 0.741–1.222 |
| 1024 | unified | 0.192 | 0.090 | 0.371 | 0.773–1.132 |
| 1024 | compact | 0.137 | 0.061 | 0.287 | 0.679–1.194 |
| 16384 | mapped | 2.856 | 0.581 | 3.606 | 3.848–5.420 |
| 16384 | unified | 2.368 | 1.121 | 3.690 | 3.851–6.216 |
| 16384 | compact | 1.452 | 0.663 | 2.288 | 2.409–4.160 |
| 131072 | mapped | 19.969 | 5.144 | 25.440 | 24.111–35.429 |
| 131072 | unified | 19.481 | 8.604 | 28.254 | 26.280–36.195 |
| 131072 | compact | 10.772 | 4.407 | 15.871 | 14.903–21.386 |

| Workload | Variant | Setup/ready reduction vs mapped | Faster in trial blocks |
| --- | --- | ---: | ---: |
| django | unified | 1.86% | 7/15 |
| django | compact | -1.59% | 6/15 |
| 1024 | unified | 1.03% | 6/15 |
| 1024 | compact | 3.64% | 10/15 |
| 16384 | unified | -3.98% | 6/15 |
| 16384 | compact | 28.64% | 14/15 |
| 131072 | unified | -11.12% | 1/15 |
| 131072 | compact | 36.52% | 15/15 |

All native tables stay mapped read-only; mutable arena data remains directory descriptors under the same logical budget. Extra file mappings/pointers are owned until close and release is deferred across native decoding. Compact tables trade denser probes and 32-bit reads against fewer bytes authenticated/touched. Total setup is still linear in metadata bytes/entries. Current zero-copy views target Linux amd64. Rebuilt remains the default; this experimental format is not an open protocol standard.
