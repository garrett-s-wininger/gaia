# Precomputed catalog experiment

Run: `20261029T040556.156420Z`. Status: **complete**.

Same freshly compiled native bridge, archive bytes, binary range index, local immutable admission and per-read CRC in every mode. Bytecode handoff stays bytes+slice. Only the dependency catalog changes in Django; its admitted stdlib reader remains reconstructed.

* rebuilt: export/decode native names, allocate every Python entry wrapper, derive module/package/child tables.
* rows: read/hash/unmarshal a producer-built name-to-native-row map; entry wrappers are lazy; derive provider tables normally.
* tables: read/hash/unmarshal rows plus producer-built module/package/child tables; adopt those tables and bind package paths to the mount.

Derived metadata is experimental v1, SHA-pinned, bound to the exact binary-index digest and interpreter identity. It uses Python marshal as a local acceleration artifact, not an open portable protocol. Consumers still deserialize Python dictionaries/strings, and Odin still validates the original index and constructs its native name/directory buffers. This avoids Python reconstruction; it is not direct in-place table lookup.

15 randomized fresh processes per case after correctness warmups; warm filesystem cache. Input generation, catalog production and bridge compilation are outside consumer timing. Catalog file reading, hashing, unmarshalling and table adoption are inside setup/application timing. All cases share common harness imports.

| Workload | Catalog | Samples | Setup median ms | Ready/workload median ms | Process median ms | Peak RSS MiB | Entry wrappers |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| django | rebuilt | 15 | — | 465.475 | 971.434 | 67.34 | 4018 |
| django | rows | 15 | — | 477.844 | 969.691 | 67.29 | 4018 |
| django | tables | 15 | — | 488.013 | 998.279 | 67.36 | 0 |
| 1024 | rebuilt | 15 | 10.310 | 11.779 | 198.416 | 21.81 | 1026 |
| 1024 | rows | 15 | 11.218 | 12.232 | 195.769 | 21.82 | 1026 |
| 1024 | tables | 15 | 11.174 | 12.305 | 187.244 | 21.89 | 0 |
| 16384 | rebuilt | 15 | 50.545 | 52.236 | 246.268 | 30.78 | 16386 |
| 16384 | rows | 15 | 55.565 | 58.451 | 252.518 | 29.92 | 16386 |
| 16384 | tables | 15 | 40.881 | 42.406 | 235.637 | 31.36 | 0 |
| 131072 | rebuilt | 15 | 470.236 | 472.072 | 751.775 | 100.14 | 131074 |
| 131072 | rows | 15 | 517.307 | 519.298 | 761.849 | 92.25 | 131074 |
| 131072 | tables | 15 | 314.022 | 315.815 | 560.847 | 104.56 | 0 |

Django readiness includes initialization/system checks and the same actual REST/admin/SQLite workload follows; full process includes unchanged validation/source inspection. The scaling cases contain an expanding flat package with one initializer and N trivial bytecode leaves plus one resource. Each imports the same first 32 leaves (33 modules total). Timed setup includes mount, native reader open and complete provider indexing. Miss/resource/discovery validation runs afterward without importing additional leaves. This isolates catalog scaling rather than asserting these module counts are typical Python applications.

| Input | Mode | Catalog bytes | Producer ms |
| --- | --- | ---: | ---: |
| django | rows | 331431 | 34.485 |
| django | tables | 393133 | 37.012 |
| 1024 | rows | 43398 | 4.762 |
| 1024 | tables | 102916 | 5.528 |
| 16384 | rows | 688518 | 80.209 |
| 16384 | tables | 1638916 | 116.481 |
| 131072 | rows | 5505414 | 980.053 |
| 131072 | tables | 13107716 | 1495.993 |

The producer validates the pinned binary index and admitted local archive before deriving metadata. Existing module ambiguity rejection is preserved. Trusted immutable producer outputs are required, as with the existing sidecar. Catalogs add storage and an additional input read; smaller application runs may not recover that cost. Timing ranges and per-phase native timings remain in raw JSON.

## Setup phases and variability

| Workload | Mode | Native open ms | Export or load catalog ms | Provider/install remainder ms | Primary min–max ms |
| --- | --- | ---: | ---: | ---: | ---: |
| django | rebuilt | 1.863 | 10.872 | — | 430.028–504.320 |
| django | rows | 1.896 | 3.400 | — | 441.551–504.712 |
| django | tables | 1.895 | 13.983 | — | 447.621–517.446 |
| 1024 | rebuilt | 0.274 | 0.476 | 8.986 | 9.204–18.702 |
| 1024 | rows | 0.298 | 0.600 | 9.322 | 7.914–16.380 |
| 1024 | tables | 0.306 | 10.312 | 0.116 | 8.372–17.462 |
| 16384 | rebuilt | 4.087 | 19.146 | 26.705 | 45.205–64.621 |
| 16384 | rows | 3.785 | 8.726 | 40.058 | 47.319–75.076 |
| 16384 | tables | 3.372 | 35.924 | 0.145 | 35.010–52.570 |
| 131072 | rebuilt | 26.748 | 142.415 | 288.937 | 425.410–497.900 |
| 131072 | rows | 27.973 | 86.072 | 404.190 | 491.752–569.192 |
| 131072 | tables | 27.490 | 285.949 | 0.144 | 285.894–431.120 |

Native open includes original range-index verification and name/directory buffer construction. Catalog time includes export/decode/wrapper creation for rebuilt, or file read/hash/unmarshal and lazy-map setup for precomputed modes. The scaling remainder includes provider table derivation or adoption plus mounting/glue. It is a per-observation subtraction, not a sum/subtraction of independent medians. Django primary ranges show readiness; scaling ranges show setup. Interpreter/common harness initialization is outside setup and remains in full process; native extension load is separately retained in raw JSON.

## Interpretation

| Workload | Tables setup/ready reduction of medians | Tables faster in blocks |
| --- | ---: | ---: |
| django | -4.84% | 4/15 |
| 1024 | -8.39% | 9/15 |
| 16384 | 19.12% | 14/15 |
| 131072 | 33.22% | 15/15 |

The precomputed table path has a clear benefit in the largest scaling fixture, but no Django startup win. Rows-only does not avoid wrapper construction overall: the unchanged provider calls infolist and materializes all wrappers while deriving tables. The table path avoids that pass, at the cost of a larger derived artifact and Python dictionary/string deserialization. Large-archive setup is still linear in available catalog size. This supports testing direct/lazy indexed lookup next, rather than treating deserialized precomputed tables as the final interface. Rebuilt remains the default.
