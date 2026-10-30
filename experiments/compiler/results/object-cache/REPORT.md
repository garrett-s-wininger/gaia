# Local compiled-object cache

Run `20261029T235526.613463Z`; **complete**; 5 randomized blocks, warm page cache, fresh consumer process per build.

Zstandard 1.5.7 portable C release library plus one explicit cache-invalidation probe (31 TUs). All modes use the same Odin/C++ binary, exact compile flags, per-request hermetic input views and ordered embedded LLD request. Off compiles all jobs. Whole keys additionally bind the complete admitted collection; scoped keys bind each complete visible namespace. All keys bind exact argv, logical working directory and admitted toolchain/execution-context identity.

| Scenario | Mode | Process ms | Child CPU ms | Executed compilers | Cache hits |
| --- | --- | ---: | ---: | ---: | ---: |
| unchanged | off | 4650.50 | 19966.69 | 31 | 0 |
| unchanged | whole | 54.61 | 53.91 | 0 | 31 |
| unchanged | scoped | 53.24 | 52.51 | 0 | 31 |
| implementation | off | 4623.51 | 20068.85 | 31 | 0 |
| implementation | whole | 4666.96 | 20101.90 | 31 | 0 |
| implementation | scoped | 116.99 | 115.18 | 1 | 30 |
| heavy-implementation | off | 4639.87 | 20197.50 | 31 | 0 |
| heavy-implementation | whole | 4663.69 | 20227.40 | 31 | 0 |
| heavy-implementation | scoped | 3766.59 | 3762.68 | 1 | 30 |
| shared-header | off | 4697.78 | 20135.60 | 31 | 0 |
| shared-header | whole | 4624.88 | 20114.73 | 31 | 0 |
| shared-header | scoped | 4652.73 | 20209.89 | 31 | 0 |
| generated-header | off | 4666.76 | 20177.49 | 31 | 0 |
| generated-header | whole | 4638.29 | 20160.08 | 31 | 0 |
| generated-header | scoped | 4641.82 | 20224.77 | 31 | 0 |
| flags | off | 4697.25 | 20071.11 | 31 | 0 |
| flags | whole | 4612.32 | 20053.21 | 31 | 0 |
| flags | scoped | 4645.23 | 20211.79 | 31 | 0 |

Every timed cache starts from a baseline-only seed, restored outside the consumer clock. Variant results from a previous observation are never left available, so an edit cannot silently turn into an all-hit unchanged build. Every build still performs a real link. Hits validate entry framing, key and payload SHA-256 before copying native object bytes into LLD input buffers. Successful misses publish entries via exclusive temporary files and atomic rename only after the complete build links successfully. Cache write failures leave a successful build usable.

Whole-process timing includes immutable-collection authentication, cache-key construction/lookup, payload integrity/copying, actual misses, linking, cache publication, captured-object validation hashes, reporting and normal teardown. Native workload counters stop before publication/reporting. Parent checks compare every object and ELF to fresh CLI references and execute the probe after timing. Input collection/admission production, reference builds, adapter build and baseline cache population are separately recorded producer/setup costs, not part of consumer latency.

Scoped inputs are caller-declared compiler namespaces: all admitted shared project/SDK headers and the selected job roots (plus any declared cross-root includes). There is no host-input fallback. The key covers optional-file presence as well as content; this is not a cache based only on previous positive dependency reads. Dependency discovery supplies this fixture, not a general complete SDK or arbitrary build-system adapter. Unsupported response files and volatile date/time macros are rejected. Toolchain/context identities are admitted by the benchmark before consumers; the child does not rehash installed compiler DSOs on every launch.

These are private local cache records with corruption detection, not authenticated remote artifacts. Publication is atomic but not fsync-durable, and there is no eviction/space quota. Compiler crashes, arbitrary plugins, PGO inputs, persistent services and general physical-filesystem equivalence are outside this prototype. All comparisons concern the same supplied immutable views.

Provenance note: toolchain receipts came from the pinned prior run and were verified against installed bytes after timing. Current reproduction checks them before preparation. A diagnostic-publication guard was added after timing and tested separately; all timed inputs were warning-free. See `diagnostic-fix-build.json`, `checks.json`, and `upstream-checks.json`.
