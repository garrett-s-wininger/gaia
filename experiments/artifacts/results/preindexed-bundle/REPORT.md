# Producer-preindexed flat bundle versus indexed stored ZIP

Run `20261031T030432.875992Z`; five randomized paired blocks after one correctness warmup. All 24 operations, 20 retained observations and 74 tests pass.

## Result

Prebuilding and shipping the portable index eliminates receiver table construction and the 4,018-file lock from **both** formats. Cold receiver install is **45.30 ms flat / 45.57 ms ZIP**, including transfer, integrity checks, complete table admission and local binding. Both use two CAS artifacts and the same mapped reader with SHA-256 plus CRC32 on every imported/resource read.

Flat has a lower observed cold complete median (**322.72 versus 336.15 ms**), but wins only **three of five paired blocks**. Cached reuse is effectively equal (**297.41/298.15 ms**), also three of five wins. This is a working package-level preindexing improvement and near-parity comparison, **not a reliable universal win over preindexed ZIP**.

## Producer and representation costs

The same pinned Django REST bytecode/resource set is rebuilt as both representations: 4,018 logical files, 455 imported dependency modules, selected versions and [wheel provenance](provenance.json) from the prior experiments. Flat uses the existing immutable raw pack with deduplicated content; ZIP uses stored entries. Each portable index has identical logical/offset/digest/CRC/module/resource semantics and no producer-local pathname, inode or timestamps.

| Artifact | Flat bytes | Stored ZIP bytes |
| --- | ---: | ---: |
| Payload | 28,590,237 | 29,396,999 |
| Portable index | 672,773 | 672,772 |
| Total cold content transfer | 29,263,010 | 30,069,771 |

Flat transfers 806,761 fewer bytes (~2.7%). Both generic binary locks select exactly two artifacts and both use one missing-list request, without remote collection metadata discovery. Content-addressed artifact hashes and bytes differ by physical representation; requested logical runtime read counts/bytes match.

Producer construction is separately recorded: **212.19 ms flat / 280.05 ms ZIP** in single setup observations. This includes data writing/sealing, logical content validation, portable-index production and generic-lock encoding. It is not a randomized producer benchmark and should not be combined with receiver medians as a measured one-shot total. Precompiled bytecode production and shared logical input preparation precede both. No custom-index rebuild cost is hidden in receiver setup; that work has explicitly moved to artifact production.

## Complete receiver and first-process observations

Cold timing includes actual generic-lock parse, transfer, artifact SHA-256, atomic CAS publication/receipt, index/payload cross-binding, full table order/geometry/reference validation, small local binding and installed receipt. It then launches a fresh `python -I -S -B` process, runs the unchanged WSGI/checks/ORM/API/admin workload, validates module/code/resource behavior and waits for normal provider/database/interpreter shutdown. Child execution starts only after complete artifact admission. No loose dependency extraction or early-exit shortcut is used.

Reuse rehashes cached artifacts and runs the full child again against an unavailable endpoint, with zero network requests. The receiver retains its portable tables rather than reconstructing them or rewriting the whole index. Admission is about **5.9 ms** cold; reading the small existing receipt is about **0.08 ms** on reuse. Index/map open and binding validation are included again in each child.

Milliseconds; independent medians need not add. Install includes acquisition and admission.

| Profile / format | Acquisition | Admission/receipt | Complete install | Full Python process | Complete total | Reader setup |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cold / flat | 39.29 | 5.93 | 45.30 | 277.63 | 322.72 | 1.08 |
| cold / zip | 39.60 | 5.80 | 45.57 | 289.80 | 336.15 | 1.48 |
| reuse / flat | 14.26 | 0.08 | 14.35 | 283.13 | 297.41 | 1.10 |
| reuse / zip | 14.81 | 0.08 | 14.88 | 283.26 | 298.15 | 1.11 |

Cold flat-minus-ZIP complete paired deltas are **−13.86 / +2.51 / −40.62 / +15.74 / −16.85 ms**; reuse **−4.16 / +8.59 / −28.12 / −0.74 / +13.84 ms**. Per-case child max/min ratios range **1.05–1.17**. Reuse acquisition favors flat by about 0.3–0.7 ms in every pair, consistent with its smaller artifact bytes, while child variation dominates total differences. It is not evidence that the file format inherently accelerates Python execution.

Prior [file-level/receiver-index results](../compact-python/REPORT.md) remain preserved. They perform different transfer/index work and used different filesystem placements; their absolute times are not subtracted as a new matched speedup. This experiment rebuilds a competent producer-preindexed ZIP control too, rather than leaving ZIP with artificial receiver work.

## Where time remains

Both consumers make **475 reads / 6,063,442 logical bytes**. Cold read/copy lookup clocks are roughly **3.53/3.83 ms flat/ZIP**, SHA-256+CRC about **4.49/4.71 ms** and reader setup **1.08/1.48 ms**. These exclude other finder lookups and framework execution.

The separate [intrusive full-workload profile](lookup-profile.json) records **2,322 binary lookups, 23,889 name accesses and 26,006 row accesses**. Lookup cumulative time is about 22 ms under profiling, but its functions overlap and profiling changes their cost: that is not a 22 ms uninstrumented latency contribution. Generic lookup memoization/hash tables could reduce common reader overhead for **both** payload formats; it should not be credited as a binary-container advantage. No extra optimization sweep or native helper is included in this first proof.

## Correctness, portability and limits

The [contract](../../../../components/artifact-host/preindexed-bundle-research.md) separates portable artifact metadata from local stat bindings and artifact-ready from consumer-installed receipts. Whole artifact/index checks and per-read SHA-256+CRC policies match. Tests prove cross-directory rebinding, cached-payload/index-only retrieval, fully offline reuse, corruption detection in an open reader, online repair/rebinding, malformed versions/header bounds and payload/index cross-binding rejection. [Validation](validation.json), [74-test log](correctness-tests.txt), [paired summary](summary.json) and raw identities in the evidence manifest retain the proof.

The shared cache has bounded 64 MiB admission, immutable CAS files and atomic rename without fsync; durable crash recovery and hostile writers remain outside the trusted local-admission model. Repair/moving a payload requires rebinding local identity. Metadata algorithms/versions are explicit and unsupported data fails.

Package-level blobs trade away cheap sparse-file acquisition: a small missing logical file may require the complete payload. The partial-cache test fetches only a missing index when the payload already exists; no sparse-file/WAN/bandwidth claim follows. Payloads are served from separate-process loopback memory, filesystem pages are warm and generated data lives on the available SSD. Namespace/native wheels, arbitrary host-path consumers, upload, eviction and real remote transport remain separate work.

The strongest demonstrated change is moving reusable index work to production and reducing receiver inputs to a few pinned artifacts. The remaining matched format difference is small; further progress should follow common lookup/consumer profiles rather than assume another container alone will produce a universal win.
