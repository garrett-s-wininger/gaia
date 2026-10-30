# Dependency journals and incremental snapshot production

Run `20261030T003643.076432Z`; **complete**; 5 randomized blocks; warm cache; fresh producer and consumer processes.

Same 31-TU Zstandard-plus-probe target, explicit input views, compiler flags and ordered LLD inputs per scenario. Scoped keys conservatively bind every visible input. Journal candidates bind argv/cwd/context and validate the prior observed filesystem queries against the new view before reuse. Every timed cache starts from a baseline-only seed.

| Scenario | Snapshot | Cache | Producer ms | Consumer ms | Combined ms | Compilers | Hits |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| unchanged | delta | off | 16.98 | 4657.82 | 4675.24 | 31 | 0 |
| unchanged | delta | scoped | 20.64 | 56.94 | 77.19 | 0 | 31 |
| unchanged | delta | journal | 21.08 | 83.57 | 104.36 | 0 | 31 |
| unchanged | full | journal | 23.40 | 77.55 | 103.44 | 0 | 31 |
| implementation | delta | off | 17.94 | 4642.77 | 4659.25 | 31 | 0 |
| implementation | delta | scoped | 18.91 | 108.82 | 128.90 | 1 | 30 |
| implementation | delta | journal | 18.46 | 146.77 | 164.07 | 1 | 30 |
| implementation | full | journal | 25.23 | 137.74 | 163.88 | 1 | 30 |
| shared-header | delta | off | 19.15 | 4628.24 | 4648.64 | 31 | 0 |
| shared-header | delta | scoped | 15.85 | 4608.88 | 4624.07 | 31 | 0 |
| shared-header | delta | journal | 17.54 | 91.60 | 109.96 | 1 | 30 |
| shared-header | full | journal | 27.09 | 94.38 | 123.36 | 1 | 30 |
| generated-header | delta | off | 18.08 | 4719.20 | 4740.59 | 31 | 0 |
| generated-header | delta | scoped | 19.06 | 4657.84 | 4678.20 | 31 | 0 |
| generated-header | delta | journal | 19.06 | 96.51 | 115.51 | 1 | 30 |
| generated-header | full | journal | 23.65 | 99.01 | 125.41 | 1 | 30 |
| optional-header | delta | off | 18.75 | 4636.12 | 4652.78 | 31 | 0 |
| optional-header | delta | scoped | 19.19 | 4663.79 | 4683.11 | 31 | 0 |
| optional-header | delta | journal | 16.14 | 97.48 | 115.11 | 1 | 30 |
| optional-header | full | journal | 25.19 | 96.33 | 120.83 | 1 | 30 |
| shadow-header | delta | off | 19.61 | 4644.86 | 4660.85 | 31 | 0 |
| shadow-header | delta | scoped | 19.66 | 4602.74 | 4620.33 | 31 | 0 |
| shadow-header | delta | journal | 18.54 | 100.52 | 118.57 | 1 | 30 |
| shadow-header | full | journal | 24.80 | 95.29 | 117.62 | 1 | 30 |
| unused-header | delta | off | 22.43 | 4668.77 | 4694.05 | 31 | 0 |
| unused-header | delta | scoped | 19.94 | 4694.26 | 4710.51 | 31 | 0 |
| unused-header | delta | journal | 19.34 | 81.46 | 101.88 | 0 | 31 |
| unused-header | full | journal | 25.00 | 78.72 | 103.72 | 0 | 31 |
| new-directory | delta | off | 20.52 | 4629.85 | 4653.75 | 31 | 0 |
| new-directory | delta | scoped | 18.59 | 4669.13 | 4692.25 | 31 | 0 |
| new-directory | delta | journal | 17.82 | 100.27 | 120.79 | 1 | 30 |
| new-directory | full | journal | 28.65 | 97.30 | 125.14 | 1 | 30 |

Combined timing begins before launching the snapshot producer and ends after normal consumer exit. It includes snapshot construction/publication, receipt handoff/validation, collection authentication, dependency checks, actual misses, linking, cache publication, reporting/result hashes and both process lifecycles. Parent reference/runtime checks follow timing. Source edit notification/delta creation, cache reset, initial SDK admission, CLI reference builds and initial cache population are outside the combined clock.

Full refresh rereads every named input from the host filesystem; delta production applies explicit caller-supplied changes to an authenticated prior snapshot and opens zero loose project/SDK files. Both serialize and hash the complete new collection, and must produce identical bundle/view pins. This compares updating an existing admitted namespace, not discovering a complete SDK after arbitrary new compiler configurations. No filesystem watcher or change-discovery service is implemented.

The journal records metadata/existence/open/realpath/directory/locality/cwd results, including negative outcomes. Opened bytes are content-hashed; all replay uses the actual new hermetic view. Numeric InMemoryFS IDs are normalized to canonical path identity because this provider has only independent regular files and implicit directories, with fixed metadata and no hardlinks/symlinks. Unrepresentable or oversized observations bypass publication. The LLVM-specific shim is not a portable general filesystem observation protocol.

Each action retains one latest journal/object candidate in a single atomically replaced record whose checksum binds action, lengths, journal and payload. Incompatible candidates miss; corruption is rejected. Historical variants, eviction/quotas, authenticated remote records, crash isolation and arbitrary plugins/side inputs remain outside this prototype. Diagnostics bypass storage. All object/ELF hashes must match independently rebuilt CLI references and observable probe values.
