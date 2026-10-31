# What artifact research establishes

Fewer requests and less repeated local metadata work improve delivery. A new wire format or archive helps only when the complete consumer benefits. The experiments separate remote fetch, verification, local publication, logical access and ordinary-file materialization.

## A known hash list avoids request amplification

In the initial generated 128-object workloads, coalesced HTTP reduces cold operations from 129 requests to two, including metadata. Loopback completion falls from about 51–53 to 9–13 ms; injected per-response delay makes batching more important. Sparse reuse exposes the tradeoff: coalescing can send substantially more than the missing bytes. The [HTTP baseline](../../experiments/artifacts/results/initial/REPORT.md) measures these request/byte costs separately.

A selected missing-hash list can fetch scattered objects in one payload request without gap overfetch. Under the matched delayed, mostly cached case, HTTP and binary batches both take 8.78 ms versus coalesced HTTP's 39.22 ms. Changing a serial envelope from HTTP to binary helps the Python implementation, but once both batch efficiently the differences are smaller and variable. This is not a universal HTTP limit. [Framing](../../experiments/artifacts/results/framing/REPORT.md), [buffered batching](../../experiments/artifacts/results/buffered/REPORT.md).

Pipelining independent requests overlaps readiness waits. A progressive known-list stream also delivers earlier verified bytes than buffering the complete response. With an established connection and independently scheduled 2 ms readiness, mixed packed completion is 47.03 ms for an eight-request window, 14.64 ms for a buffered list and 12.83 ms for a streamed list. The first verified bytes precede durable cache visibility; the model is application readiness, not WAN RTT. Large-object frame interleaving was not tested. [Pipeline report](../../experiments/artifacts/results/pipeline/REPORT.md).

## Local storage helps consumers that accept logical views

A verified immutable pack/index reduces cold publication from 130 files to five and fully cached data opens from 256 to two. It helps both transports under the same requested-content verification.

| Complete loopback operation | HTTP files | HTTP pack | Binary files | Binary pack |
| --- | ---: | ---: | ---: | ---: |
| Small cold | 9.90 ms | 4.22 ms | 10.44 ms | 3.67 ms |
| Mixed cold | 15.66 ms | 10.72 ms | 15.59 ms | 10.46 ms |
| Mixed cached, offline | 7.78 ms | 5.88 ms | 7.90 ms | 5.92 ms |

Creating ordinary files changes the conclusion. Mixed cold HTTP plus materialization takes 15.94 ms for the file cache and 16.99 ms for the pack; cached totals are 8.06 and 11.88 ms. A legacy tool does not receive the direct-view gain for free. The [local-admission report](../../experiments/artifacts/results/admission/REPORT.md) charges both interfaces.

## Producer indexes matter more than an intrinsic ZIP advantage

A real Django consumer imports 455 dependency modules and reads templates/resources directly from retained packed bytes. The initial integration loses to indexed ZIP. Retaining compact binary metadata cuts pack reader setup from about 53 to 1.2 ms, but building that index cold costs about 97 ms. A faster child process did not make the complete cold installation faster. [Initial consumer](../../experiments/artifacts/results/locked-python/REPORT.md), [compact metadata](../../experiments/artifacts/results/compact-python/REPORT.md).

Giving both flat payloads and stored ZIP a portable producer-built index removes that receiver construction. Each format then transfers two content-addressed objects, uses the same mapped reader, and retains SHA-256 plus CRC32 checks on every read.

| Operation | Flat payload | Stored ZIP |
| --- | ---: | ---: |
| Cold install, including transfer/admission | 45.30 ms | 45.57 ms |
| Cold install and complete Python process | 322.72 ms | 336.15 ms |
| Reuse and complete Python process | 297.41 ms | 298.15 ms |

Flat wins only three of five complete-operation pairs in both profiles. It sends 2.7% fewer bytes and saves about 0.3–0.7 ms of cached acquisition, but there is no reliable overall startup lead. Package-level payloads also overfetch when only sparse logical files are needed. The [preindexed comparison](../../experiments/artifacts/results/preindexed-bundle/REPORT.md) preserves that distinction.

## A binary lock can describe resolved contents across ecosystems

The generic lock carries opaque ecosystem/name/version identities, algorithm-tagged content, many-to-many package/artifact associations and separately addressed metadata. It describes an already resolved set; ecosystem-specific version and target rules stay outside the format.

On the same five-package dataset, binary encoding reduces 882,337 bytes to 498,747 and verified parse CPU from 9.24 to 2.84 ms. Reuse acquisition improves from 47.33 to 42.51 ms, with four of five paired wins. Cold acquisition does not improve reliably. The retained binary view still owns its input body, so small parser-object counts are not a total memory claim. [Generic lock report](../../experiments/artifacts/results/generic-lock/REPORT.md).

## Demand admission trades payload bytes against service calls

The [shared-data follow-up](followthrough.md) admits verified producer chunks while actual Django imports execute. Across three fresh starts, 4 KiB chunks fetch 7.63 MB through 1,862 modeled storage calls; 64 KiB chunks fetch 20.66 MB through 316 calls; full admission reads 28.59 MB once. The range control reads 18.19 MB through 1,425 calls. These are payload access counts, separate from the identical charged installation.

The frozen confirmation has one matched block per profile/policy. It shows the expected latency/bandwidth tradeoff, not a universal preferred chunk size. Every policy pays the same Python socket dispatch/copies, which can dominate nominal startup. Code executes before the last demand fetch; asynchronous CPU/network overlap has not been demonstrated. The earlier three-block matrix remains exploratory because a constructor changed during execution.

## Direct metadata queries avoid rebuilding equivalent objects

A 4,018-row real dependency catalogue is consumed independently by Python, Odin and Node. In the [fused control](../../experiments/artifacts/followthrough/results/catalogue-fused/REPORT.md), verified read/validation/query takes 4.791 ms through Python JSON objects, 2.356 ms through direct Python binary queries and 0.396 ms through the borrowed-buffer Odin ABI. Node takes 5.734 versus 2.754 ms. Direct queries beat their JSON controls in all five blocks.

The result combines representation size, validation/query algorithms and runtime iteration; it is not a format-only comparison or complete-startup gain. Odin borrows an immutable Python-owned buffer for the call and returns scalars. Node reads the same representation independently; this does not establish physical page sharing between processes. Binary-to-object conversion loses to JSON here, making retained representation an important part of the interface.

## Cache lifetime changes the cost of one lookup

At 3,931 real objects, an already-open packed cache retrieves one selected object in about 0.017 ms, but reopening and looking it up costs 12.71 ms. The file-store reopen operation takes about 0.052 ms in this fixture. The [lifecycle study](../../experiments/artifacts/followthrough/results/lifecycle/REPORT.md) also exercises eviction, consolidation, interrupted bodies, publication failure and corrupt locators.

Retained views here are independently owned bytes, not leases on a mapped pack. Corrupt metadata follows the existing empty-cache recovery policy; authoritative offline recovery and stronger durability remain open. A persistent service can amortize index reconstruction, but its lifetime and memory must be charged.

## What the tests do and do not cover

Reports retain requested-content identities, matching Python behavior, offline cache reuse, corruption repair, partial caches and framing/index bounds. The latest preindexed study passes 74 tests and 24 full application operations; earlier studies retain their own checks and negative results. A minimal pinned name/version catalog demonstrates lock discovery, not a complete registry or resolver.

Most transfer timings use resident Python loopback endpoints and warm local storage. Delays are controlled models. Native HTTP/binary implementations, WAN bandwidth/loss, TLS/authentication, uploads, concurrent writers, crash-durable storage and process-wide memory bounds remain unmeasured. The [research contracts](../../components/artifact-host/README.md) describe the boundaries; the [prospects](prospects.md) identify which uncertainty to address next.
