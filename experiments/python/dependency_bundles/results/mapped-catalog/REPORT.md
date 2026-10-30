# Directly mapped lookup catalog experiment

Run: `20261029T123751.173467Z`. Status: **complete**.

Same admitted archives/range indexes and newly compiled bridge across rebuilt Python catalogs, runtime-constructed native tables, and producer-built mapped native tables. Same bytes+slice bytecode handoff and reconstructed stdlib reader. Warm filesystem cache, 15 randomized fresh processes per case after correctness warmups.

The experimental v1 artifact has a 256-byte versioned header, original-index SHA-256 binding, offset/length directory records and aligned little-endian u64 name offsets, hash slots and child heads/counts/links. It contains no pointers, native strings or executable code. Current zero-copy integer-array views support Linux amd64; the on-disk scalars have explicit width/endianness. Module lookup semantics are certified once by the pinned producer. This local experiment is not yet an open standardized protocol.

Mapped consumers hash both index and lookup artifact, check binding/header/array bounds, validate table value domains/counts, and rescan original ranges/names for UTF-8 and offset agreement. Directory lookup binding is checked. They retain archive identity/full-hash policy and per-read payload CRC. They do not rebuild or re-prove every file/module hash placement; trusted immutable producer outputs are required, as with the earlier Python precomputed tables. Probing and child iteration are bounded against malformed inputs.

| Workload | Catalog | Setup median ms | Ready/workload median ms | Process median ms | Peak RSS MiB | Mutable arena bytes |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| django | rebuilt | — | 375.685 | 752.437 | 67.64 | — |
| django | native | — | 382.140 | 754.565 | 66.17 | 420960 |
| django | mapped | — | 381.362 | 755.130 | 66.30 | 42640 |
| 1024 | rebuilt | 7.856 | 9.287 | 156.886 | 22.06 | — |
| 1024 | native | 1.270 | 2.693 | 149.822 | 21.69 | 90288 |
| 1024 | mapped | 0.947 | 2.361 | 155.466 | 21.70 | 32 |
| 16384 | rebuilt | 41.408 | 43.557 | 206.455 | 30.99 | — |
| 16384 | native | 12.315 | 13.753 | 171.338 | 23.60 | 1441968 |
| 16384 | mapped | 4.105 | 5.439 | 160.074 | 23.60 | 32 |
| 131072 | rebuilt | 397.880 | 402.900 | 644.047 | 100.32 | — |
| 131072 | native | 124.709 | 126.173 | 278.717 | 38.04 | 11534512 |
| 131072 | mapped | 24.787 | 26.433 | 177.334 | 38.04 | 32 |

Each scaling case imports the same 32 leaves plus initializer, independent of the available module count. Miss/resource/discovery checks follow the timed workload, using membership instead of materializing all children. Python lookup/name counters must stay small. Full process/RSS include common harness initialization, validation and exit. Django retains all application/output/origin/source-inspection/no-network checks.

| Workload | Catalog | Integrity median ms | Structure/setup median ms | Table construction median ms | Native open median ms |
| --- | --- | ---: | ---: | ---: | ---: |
| django | native | 0.356 | 0.644 | 1.583 | 2.641 |
| django | mapped | 0.826 | 0.536 | 0.000 | 1.502 |
| 1024 | native | 0.093 | 0.062 | 0.538 | 0.766 |
| 1024 | mapped | 0.208 | 0.058 | 0.000 | 0.357 |
| 16384 | native | 0.958 | 0.612 | 9.508 | 11.149 |
| 16384 | mapped | 2.651 | 0.738 | 0.000 | 3.514 |
| 131072 | native | 6.397 | 4.186 | 113.190 | 124.076 |
| 131072 | mapped | 18.719 | 5.120 | 0.000 | 24.163 |

Integrity includes SHA-256 of the original index, additionally the lookup artifact for mapped mode, and archive identity/full-hash policy checks. Structure/setup includes format/range/UTF-8/table checks and directory-view setup; native mode also builds its directory hash in that phase. Construction covers native file/module/child table building and archive mapping; mapped mode performs no reconstruction. Native-open includes remaining mapping/glue. Independent medians do not add. All phases remain inside startup timing; no trust checks are timed away.

| Input | Lookup bytes | Production/certification ms |
| --- | ---: | ---: |
| django | 421216 | 24.571 |
| 1024 | 90544 | 6.594 |
| 16384 | 1442224 | 92.221 |
| 131072 | 11534768 | 787.505 |

| Workload | Mapped vs native reduction (setup/ready) | Mapped faster in blocks | Primary mapped min–max ms |
| --- | ---: | ---: | ---: |
| django | 0.20% | 8/15 | 352.261–429.520 |
| 1024 | 25.43% | 15/15 | 0.745–1.258 |
| 16384 | 66.66% | 15/15 | 3.821–4.757 |
| 131072 | 80.12% | 15/15 | 23.736–29.925 |

The producer constructs the existing bounded native catalog, exhaustively checks every file-to-ordinal, module-to-member and directory binding against the admitted index, and writes its pointer-free tables with an external SHA pin. Production/storage are outside consumer timings and are not free. The consumer still scans and hashes inputs, so mount remains linear even though table reconstruction is removed. Mutable metadata stays within the 16.00 MiB logical arena budget; read-only mapped lookup/index/archive pages and fixed handles are accounted through process RSS separately. Mapped file pages remain subject to OS paging. Close owns all three input mappings and defers release while native decoding is active. Rebuilt remains the default.
