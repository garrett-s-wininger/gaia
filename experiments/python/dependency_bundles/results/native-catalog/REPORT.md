# Native bounded catalog experiment

Run: `20261029T042442.112831Z`. Status: **complete**.

Reuses the exact admitted archive/index and precomputed-table inputs from the prior catalog run. Every case uses the same freshly compiled bridge and bytes+slice handoff. Django changes only its dependency catalog; its stdlib reader stays reconstructed. Warm filesystem cache, 15 randomized fresh processes per case after correctness warmups.

* rebuilt: export catalog and construct Python entry/module/package/child tables.
* tables: read/hash/unmarshal pinned precomputed Python tables.
* native: validate the existing binary index, retain mapped string views, and build native file/module/directory hash slots plus child links in one fixed-capacity mmap arena. Python uses lazy lookup/enumeration adapters; no full catalog export or deserialization.

Arena capacity is **16.00 MiB** per native mount. Mandatory tables must fit; exhaustion returns MemoryError without increasing capacity or changing repository data. Metadata allocation does not grow during lookups. Used bytes and fixed handle size are reported separately. Mapping page rounding, mapped input pages, temporary path/hash/OpenSSL work, the CPython shim and all Python allocations are outside the arena budget. This is a metadata-allocation bound, not a total process/RSS bound.

| Workload | Catalog | Setup median ms | Ready/workload median ms | Process median ms | Peak RSS MiB | Arena used MiB |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| django | rebuilt | — | 452.871 | 919.021 | 67.72 | — |
| django | tables | — | 447.680 | 909.006 | 67.60 | — |
| django | native | — | 472.598 | 960.775 | 66.17 | 0.401 |
| 1024 | rebuilt | 8.626 | 10.358 | 195.196 | 21.96 | — |
| 1024 | tables | 8.748 | 10.187 | 182.891 | 22.05 | — |
| 1024 | native | 1.367 | 2.885 | 169.928 | 21.63 | 0.086 |
| 16384 | rebuilt | 51.873 | 53.858 | 248.898 | 30.96 | — |
| 16384 | tables | 37.649 | 38.923 | 233.010 | 31.50 | — |
| 16384 | native | 14.813 | 16.769 | 196.982 | 23.55 | 1.375 |
| 131072 | rebuilt | 436.960 | 441.449 | 718.886 | 100.33 | — |
| 131072 | tables | 301.811 | 303.165 | 555.969 | 104.70 | — |
| 131072 | native | 146.098 | 148.018 | 315.932 | 37.98 | 11.000 |

Scaling cases still import the first 32 leaves plus initializer from the same expanding flat package. Native names/lookup-query counters are captured before scaling validation; large catalogs must not yield more Python names simply because more unused leaves exist. Resource/miss/discovery boundary validation happens after the workload, using membership instead of materializing every child. Full process/RSS include that validation. Actual enumeration emits Python objects for the requested children; importing a module does not enumerate its siblings. Native directory enumeration filters native views before decoding matching child names.

Index pin, format, range/UTF-8/duplicate-directory checks, archive identity/full-hash policy and per-read CRC remain. The native path additionally rejects duplicate canonical modules. Names stay views of the mapped index; all variable-size persistent native metadata is in the arena. Close releases the arena/index/archive, deferred while a native bytecode decode is active. Returned Python strings, bytes and code own their data.

| Workload | Mode | Native-open median ms | Catalog/adapters median ms | Primary min–max ms |
| --- | --- | ---: | ---: | ---: |
| django | rebuilt | 1.444 | 10.758 | 360.332–490.669 |
| django | tables | 1.681 | 13.452 | 354.664–494.663 |
| django | native | 2.588 | 0.032 | 356.204–532.145 |
| 1024 | rebuilt | 0.268 | 0.469 | 7.318–15.025 |
| 1024 | tables | 0.273 | 7.833 | 6.317–17.708 |
| 1024 | native | 0.700 | 0.033 | 1.154–2.038 |
| 16384 | rebuilt | 3.613 | 19.869 | 40.632–63.285 |
| 16384 | tables | 3.572 | 32.264 | 30.079–49.600 |
| 16384 | native | 12.710 | 0.062 | 10.597–19.026 |
| 131072 | rebuilt | 25.374 | 140.614 | 354.727–535.007 |
| 131072 | tables | 23.696 | 278.692 | 245.438–411.961 |
| 131072 | native | 145.237 | 0.081 | 115.514–176.750 |

| Workload | Native reduction vs rebuilt (setup/ready) | Native faster in blocks |
| --- | ---: | ---: |
| django | -4.36% | 7/15 |
| 1024 | 84.15% | 15/15 |
| 16384 | 71.44% | 15/15 |
| 131072 | 66.56% | 15/15 |

Native open still hashes and scans the entire index and builds bounded native hash/child tables: total setup is still linear in catalog size. Python metadata materialization follows requested lookups/enumerations. This prototype uses regular pure-Python packages; native extensions/unbundled fallbacks keep their prior paths. Rebuilt remains the default. Original artifact conversion costs/storage are retained in the parent catalog report; native mode needs no additional derived artifact. Compilation is outside consumer timing.
