# Generic binary resolved lock versus matched JSON

Final run `20261031T023718.134084Z`; five paired blocks, 20 retained observations after four correctness warmups. All 24 operations and 71 tests pass.

The same generic manifest shrinks **882,337→498,747 bytes** (43% smaller). Full whole-lock-pin/structure validation takes **9.24→2.84 ms CPU**, about **3.25× faster**; wall medians are 9.25/2.85 ms. The binary view retains validated tables instead of constructing all record dictionaries.

Separate traced parser allocations are **2,911,967/2,616 retained bytes** and **3,795,247/390,336 peak bytes** JSON/binary. Already provided encoded input is excluded: the binary view additionally retains its **498,747-byte body**. These are parser metadata allocations, not total memory/RSS. Binary validation uses bounded temporary sets; complete acquisition still creates cache-planning wrappers/state.

## Generic core and unchanged consumer

The [format proposal](../../../../components/artifact-host/generic-lock-research.md) defines optional ecosystem/name/opaque-version identities, algorithm-tagged digest+size descriptors, many-to-many package/artifact associations with opaque role/label strings, and independently addressed opaque metadata. One version need not correspond to one blob. Platform/ABI/graph/version semantics remain ecosystem-owned; the core represents an already resolved selection, not a solver.

Both encodings describe exactly the same **five packages, 3,932 content objects, 4,018 file associations and one Python-context reference**. This generic JSON control is newly defined, not the previous Python-specific JSON relabeled. The [earlier negative/compact results](../compact-python/REPORT.md) remain unchanged. The same pinned Django REST bytecode files, selected versions and [wheel provenance](provenance.json) are reused. The independently addressed context adds 487 bytes equally: cold content transfer is **28,590,716 bytes**, one missing-hash request and zero remote collection-index requests.

Both paths use the identical compact mapped loader, SHA-256 **plus** CRC32 on every read, matching logical content/hash/read work, the same 455 dependency modules/API/admin/resource checks and normal provider/interpreter shutdown. The lock format does not change child input or implementation.

## Complete operation costs

Cold timing begins before producing/hashing the chosen format. It includes actual JSON or binary lock parsing, all cached/received content verification, transfer, representation sealing/publication and receipt, explicit Python adaptation, retained compact-index construction, a fresh isolated Python workload and normal shutdown. Format production and consumer-index production are charged. Common resolved-input preparation/server admission and prior bytecode production are separately stated producer prerequisites. No measured JSON lock decoding is moved outside acquisition.

The cold Python adapter verifies/decodes the context and reconstructs the prior logical lock inside installation, costing **22.55/24.19 ms** JSON/binary. Reuse retains the admitted consumer index but still validates the actual generic lock/cache and starts another complete Python process; its endpoint is unavailable and network count must stay zero.

Medians in milliseconds. Install includes production/acquisition/adapter/index work. Independent column medians need not add.

| Profile / format | Format production | Lock parse | Acquisition | Complete install | Python process | Complete total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cold / json | 8.39 | 8.45 | 78.29 | 212.70 | 293.18 | 505.94 |
| cold / binary | 8.35 | 2.73 | 79.09 | 215.31 | 285.76 | 498.86 |
| reuse / json | 0.00 | 8.81 | 47.33 | 47.44 | 288.23 | 342.99 |
| reuse / binary | 0.00 | 2.85 | 42.51 | 42.61 | 290.73 | 333.14 |

Production medians are similar (8.39/8.35 ms). **Reuse acquisition improves 47.33→42.51 ms**, with binary winning four of five paired observations. **Cold acquisition does not improve reliably**: 78.29/79.09 ms, binary wins only two of five. Faster parsing is not enough to guarantee a complete-operation win; descriptor wrappers, cache indexes, content hashing and publication remain visible.

Complete total paired wins are two of five cold and four of five reuse. Cold binary-minus-JSON deltas are **+73.92 / −77.93 / −7.84 / +15.28 / +15.08 ms**; reuse **−10.94 / +15.66 / −16.80 / −3.73 / −17.64 ms**. The identical child timings still vary (per-case max/min reaches 1.26), so whole-operation median differences cannot be credited entirely to the format. The strongest attribution is the isolated ~6.4 ms parse reduction and lower parser allocation. Provisional runs are not pooled; this final run includes mutable-input ownership and public-index-bound corrections in its frozen sources.

## Integrity, bounds and evidence

The versioned binary layout uses bounded fixed-width tables, interned UTF-8 and a separate digest pool with explicit algorithm tags/lengths. Both parsers verify trusted whole-lock pins and validate versions, schema/counts, identities and references; binary additionally validates exact pool extents and UTF-8 offsets before lazy access. Only explicit SHA-256 is implemented; unknown algorithms, mandatory flags or versions fail. Prototype caps are 4 MiB encoded locks, 16,384 rows per principal table and 65,536 strings. Bytes input keeps a no-copy path; mutable bytearray input is frozen before validation/lazy access. Public binary record/string access rejects negative and out-of-range IDs.

The cache retains its 64 MiB quota, bounded staging and corruption checks. Atomic rename is used without fsync; durable crash recovery is unproven. Compact consumers preserve the same trusted-local-admission/stat identity and per-read checks. Package authority, mutable name lookup, version solving, native wheels, arbitrary filesystem consumers and distributed writers remain out of scope. Logical label/path interpretation stays in the Python adapter.

[Summary](summary.json) retains paired blocks and spread ratios; [parse/allocation evidence](parse-profile.json) separates uninstrumented CPU/wall from intrusive allocation tracing. [Validation](validation.json) binds raw evidence and matched-work checks; the [71-test log](correctness-tests.txt) includes malformed versions/counts/offsets/references, unsupported algorithms, invalid UTF-8, pins, empty manifests, opaque versions/multiple associations, post-parse mutation, public API bounds, acquisition and offline reuse. Full raw observations and exact measured source snapshots remain ignored local artifacts.

The result supports a reusable resolved-manifest core with a lazy binary encoding. The next boundary is passing descriptor views through cache planning without unnecessary conversion/state reconstruction, while preserving validation and publication. Portable test vectors and algorithm/extension policy are needed before standardization. This is not evidence for universal dependency semantics or faster Python execution merely from a different lock encoding.
