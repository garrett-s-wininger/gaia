# Verified local pack/index admission and access

Run `20261031T005250.489572Z`; complete; 7 randomized blocks per case.

Complete operation timing includes acquisition (metadata, cache verification, transfer, logical digest validation and publication/receipt), followed by a fresh verified logical-byte access. The latter reopens the store and returns read-only views backed by owned immutable buffers. File and pack layouts perform the same requested logical verification. Pack/index representation checks and sealing hashes are extra work, recorded separately.

Ordinary-file materialization is timed afterward and reported separately and as a combined operation. File controls reuse their existing per-blob paths; packed views must pay to create requested ordinary files. Source/server/cache-seed initialization and parent validation are excluded. Injected delay is a per-response application sleep, not a WAN model.

## small; injected response delay 0 ms

| Scenario / transfer mode | HTTP files | HTTP packed | Buffered binary files | Buffered binary packed |
| --- | ---: | ---: | ---: | ---: |
| metadata-only / pack-coalesced | 1.30 ms | 1.57 ms | 1.20 ms | 1.43 ms |
| metadata-only / selected-batch | 1.47 ms | 1.73 ms | 1.25 ms | 1.44 ms |
| cold-all / pack-coalesced | 9.90 ms | 4.22 ms | 10.44 ms | 3.67 ms |
| cold-all / selected-batch | 10.42 ms | 4.12 ms | 9.96 ms | 3.99 ms |
| cached-all / pack-coalesced | 4.10 ms | 2.13 ms | 4.19 ms | 2.13 ms |
| cached-all / selected-batch | 4.12 ms | 2.06 ms | 4.06 ms | 2.24 ms |
| cached-90 / pack-coalesced | 6.09 ms | 3.89 ms | 6.17 ms | 3.49 ms |
| cached-90 / selected-batch | 5.64 ms | 3.72 ms | 5.20 ms | 3.34 ms |
| sparse-10 / pack-coalesced | 3.45 ms | 2.75 ms | 3.07 ms | 2.69 ms |
| sparse-10 / selected-batch | 2.50 ms | 2.21 ms | 2.35 ms | 2.16 ms |
| one-missing / pack-coalesced | 5.16 ms | 3.34 ms | 4.86 ms | 3.04 ms |
| one-missing / selected-batch | 5.43 ms | 3.02 ms | 4.90 ms | 3.04 ms |

## small; injected response delay 2 ms

| Scenario / transfer mode | HTTP files | HTTP packed | Buffered binary files | Buffered binary packed |
| --- | ---: | ---: | ---: | ---: |
| metadata-only / pack-coalesced | 3.84 ms | 3.77 ms | 3.44 ms | 3.47 ms |
| metadata-only / selected-batch | 3.41 ms | 3.60 ms | 3.30 ms | 3.83 ms |
| cold-all / pack-coalesced | 15.28 ms | 8.66 ms | 14.87 ms | 8.60 ms |
| cold-all / selected-batch | 15.04 ms | 9.29 ms | 14.58 ms | 8.09 ms |
| cached-all / pack-coalesced | 3.93 ms | 2.15 ms | 3.96 ms | 2.13 ms |
| cached-all / selected-batch | 3.96 ms | 2.41 ms | 4.02 ms | 2.10 ms |
| cached-90 / pack-coalesced | 11.04 ms | 8.04 ms | 10.48 ms | 8.62 ms |
| cached-90 / selected-batch | 7.93 ms | 5.44 ms | 7.34 ms | 5.29 ms |
| sparse-10 / pack-coalesced | 12.38 ms | 12.40 ms | 11.49 ms | 11.11 ms |
| sparse-10 / selected-batch | 7.20 ms | 6.66 ms | 6.83 ms | 6.80 ms |
| one-missing / pack-coalesced | 7.13 ms | 5.09 ms | 7.57 ms | 5.22 ms |
| one-missing / selected-batch | 7.36 ms | 5.17 ms | 6.91 ms | 4.97 ms |

## mixed; injected response delay 0 ms

| Scenario / transfer mode | HTTP files | HTTP packed | Buffered binary files | Buffered binary packed |
| --- | ---: | ---: | ---: | ---: |
| metadata-only / pack-coalesced | 1.51 ms | 1.45 ms | 1.24 ms | 1.37 ms |
| metadata-only / selected-batch | 1.37 ms | 1.46 ms | 1.31 ms | 1.33 ms |
| cold-all / pack-coalesced | 15.66 ms | 10.72 ms | 15.59 ms | 10.46 ms |
| cold-all / selected-batch | 16.24 ms | 11.46 ms | 16.18 ms | 10.80 ms |
| cached-all / pack-coalesced | 7.78 ms | 5.88 ms | 7.90 ms | 5.92 ms |
| cached-all / selected-batch | 7.93 ms | 5.87 ms | 8.03 ms | 5.71 ms |
| cached-90 / pack-coalesced | 13.24 ms | 10.79 ms | 11.94 ms | 8.96 ms |
| cached-90 / selected-batch | 9.60 ms | 7.86 ms | 9.20 ms | 7.99 ms |
| sparse-10 / pack-coalesced | 6.60 ms | 5.71 ms | 4.88 ms | 4.43 ms |
| sparse-10 / selected-batch | 3.50 ms | 3.49 ms | 3.01 ms | 3.16 ms |
| one-missing / pack-coalesced | 9.02 ms | 7.25 ms | 8.72 ms | 6.78 ms |
| one-missing / selected-batch | 8.95 ms | 7.48 ms | 8.99 ms | 6.94 ms |

## mixed; injected response delay 2 ms

| Scenario / transfer mode | HTTP files | HTTP packed | Buffered binary files | Buffered binary packed |
| --- | ---: | ---: | ---: | ---: |
| metadata-only / pack-coalesced | 3.69 ms | 3.85 ms | 3.60 ms | 4.26 ms |
| metadata-only / selected-batch | 3.62 ms | 4.08 ms | 3.56 ms | 3.94 ms |
| cold-all / pack-coalesced | 20.48 ms | 15.56 ms | 20.49 ms | 15.34 ms |
| cold-all / selected-batch | 21.51 ms | 16.20 ms | 20.43 ms | 15.93 ms |
| cached-all / pack-coalesced | 7.80 ms | 5.89 ms | 7.73 ms | 5.77 ms |
| cached-all / selected-batch | 7.76 ms | 5.87 ms | 7.68 ms | 5.84 ms |
| cached-90 / pack-coalesced | 40.43 ms | 38.27 ms | 38.87 ms | 36.00 ms |
| cached-90 / selected-batch | 11.72 ms | 10.53 ms | 11.84 ms | 10.51 ms |
| sparse-10 / pack-coalesced | 31.67 ms | 30.56 ms | 30.65 ms | 28.66 ms |
| sparse-10 / selected-batch | 8.04 ms | 8.19 ms | 7.89 ms | 7.97 ms |
| one-missing / pack-coalesced | 11.89 ms | 9.96 ms | 10.65 ms | 10.00 ms |
| one-missing / selected-batch | 11.41 ms | 10.20 ms | 11.47 ms | 9.51 ms |

[Summary](summary.json) includes paired results, access/materialization costs and storage counters; [validation](validation.json) binds ignored raw observations.

## Shared local admission wins for logical-byte consumers

The cache layout changes on both transports. It is not a binary-framing gain. All transfer plans, requested identities, received content bytes and requested logical digest work remain matched; pack/index sealing and metadata verification add explicitly recorded representation work.

Representative complete loopback operations, including acquisition and a fresh verified logical-byte reopen:

| Operation | HTTP files | HTTP packed | Buffered binary files | Buffered binary packed | Packed paired wins, HTTP / binary |
| --- | ---: | ---: | ---: | ---: | --- |
| Small cold coalesced | 9.90 ms | 4.22 ms | 10.44 ms | 3.67 ms | 7/7 / 7/7 |
| Small cached coalesced, offline | 4.10 ms | 2.14 ms | 4.19 ms | 2.13 ms | 7/7 / 7/7 |
| Mixed cold coalesced | 15.66 ms | 10.72 ms | 15.59 ms | 10.46 ms | 7/7 / 7/7 |
| Mixed cached coalesced, offline | 7.78 ms | 5.88 ms | 7.90 ms | 5.92 ms | 7/7 / 7/7 |
| Mixed 90%-cached selected batch | 9.60 ms | 7.86 ms | 9.20 ms | 7.99 ms | 7/7 / 7/7 |
| Mixed one-missing selected batch | 8.95 ms | 7.48 ms | 8.99 ms | 6.94 ms | 7/7 / 7/7 |

Small cold coalesced operations improve by about 57% over HTTP and 65% over buffered binary file controls. Mixed cold improves about 32–33%. Offline complete-cache operations improve without any network traffic. These controls were all remeasured with the stronger consumer-access clock; earlier transport-only medians are not substituted.

The gain is not universal. Metadata-only requests need no blob store and often pay a small extra packed-layout setup cost. Sparse-10 selected-batch cases have only 12 requested objects: mixed loopback HTTP files/packed are 3.50/3.49 ms (three paired wins), and buffered binary 3.01/3.16 ms (four paired wins). Fixed pack/index metadata overhead can outweigh the saved file operations for small selections. The one-missing scenario still requests the complete 128-object collection with 127 already cached; it is not a single-object lookup scalability benchmark.

## What changed locally

Newly verified missing blobs are staged into one immutable pack. A versioned immutable index maps logical SHA-256 identities/sizes to pack descriptors and offsets. An atomic head update selects that index. The completed requested-set receipt remains separate. If a request adds a small delta, the index can reference the previous pack and the new one instead of rewriting every cached byte.

The public experimental access function returns read-only logical views backed by owned immutable read buffers. It does not return mutable mmap aliases or defer input reads. The packed reader groups adjacent requested spans without gap overfetch, opens each needed pack once, checks geometry/header/size and hashes each requested blob against the trusted manifest. Returned views remain valid after files are closed or later cache repairs occur. The file control exposes the same logical-view contract.

Atomic publication and successful local data-open counts:

| Scenario, 128-object collection | File publications | Packed publications | Successful file data opens, acquisition + fresh access | Packed data opens |
| --- | ---: | ---: | ---: | ---: |
| Cold all | 130 | 5 | 128 | 1 |
| Cached all | 1 | 1 | 256 | 2 |
| 90% cached | 14 | 4 | 243 | 3 |
| One missing | 2 | 4 | 255 | 3 |

Cold packed publication consists of manifest, data pack, index, head and receipt. With metadata already cached, a new pack/index/head plus receipt costs four publications even for one missing object. The one-missing logical-access gain therefore comes from fewer subsequent opens/reads, not fewer publication operations. Fully cached requests publish only the common receipt. All operation counts are asserted rather than inferred from wall time.

For mixed cached-all, the file control makes 256 logical data reads across acquisition validation and consumer reopen. Packed makes four: two pack-header reads and two contiguous requested-data reads. It hashes the same logical content bytes. These are store-level successful-read/open counters; absent-file open attempts and metadata operations are excluded, and one logical read can involve multiple underlying reads. They are not a complete syscall trace.

## Verification and representation costs stay inside the clock

The complete operation first acquires the requested set, verifying cached or transferred blob bytes and publishing the cache/receipt. It then closes/reopens the store through a separate logical access API, revalidates the pinned manifest and every requested blob, and returns the verified views. Thus both layouts pay a fresh consumer read and logical hash pass. No data needed by that API remains to be loaded after the endpoint.

For mixed cold coalesced HTTP, acquisition/access medians are 11.66/3.92 ms for files and 7.90/2.89 ms for packed. For the small set they are 7.94/1.98 versus 3.00/1.04 ms. These independent phase medians need not add exactly to the complete median. Metadata, transport, logical verification and local publication remain timed in acquisition.

Both mixed layouts hash 7,892,116 logical/manifest bytes in the complete operation: the 3,932,160 requested content bytes twice plus the trusted manifest twice. Packed also hashes 3,978,988 representation bytes for its new pack seal, immutable index and fresh index verification. That extra work is not omitted or charged to another process. A valid cached-all packed operation adds 46,820 index-verification bytes without resealing data. Compaction has separate hash/read counters and would also remain inside the request; the main matrix needs at most two packs, so compaction is covered by correctness tests rather than these timing conclusions.

## Ordinary-file demand is explicitly different

The logical API is equivalent across layouts; the physical file interface is not. The file cache already has one ordinary file per requested digest. Packed must create those files if a consumer requires them. The experiment times that step after logical access, includes it in a combined endpoint and independently compares every returned file byte.

| Loopback coalesced operation | Logical API, files / packed | Extra ordinary-file time, files / packed | Combined logical access + ordinary paths, files / packed |
| --- | ---: | ---: | ---: |
| Small cold HTTP | 9.90 / 4.22 ms | 0.25 / 5.24 ms | 10.12 / 9.52 ms |
| Mixed cold HTTP | 15.66 / 10.72 ms | 0.27 / 6.02 ms | 15.94 / 16.99 ms |
| Mixed cached HTTP | 7.78 / 5.88 ms | 0.28 / 6.00 ms | 8.06 / 11.88 ms |
| Mixed cold buffered binary | 15.59 / 10.46 ms | 0.26 / 5.82 ms | 15.79 / 16.46 ms |
| Mixed cached buffered binary | 7.90 / 5.92 ms | 0.26 / 6.07 ms | 8.16 / 12.02 ms |

Independent phase medians can differ from the median combined endpoint. Mixed cold packed loses most combined comparisons, and all mixed cached packed comparisons lose after requiring 128 materialized files. Packed cached logical access is faster, but rematerializing unchanged files is unnecessary work for an already-file-backed consumer. The result supports direct logical-byte consumers; it is not a claim that every existing filesystem/CLI workflow improves.

The ordinary-file adapter returns digest-to-path mappings. Mapping blobs into an ecosystem's logical directory hierarchy, permissions, writable working copies, hardlink/symlink policy and tool execution are not modeled. A pure file-only consumer might skip the logical-view API entirely; the combined table deliberately retains the same proved logical access on both sides before adding file demand. No broader legacy-tool speedup is inferred.

## Format, staging, quotas and recovery

The on-disk experiment is separate from transport framing. Data packs start with `GAPK0001`; framed indexes start with `GAIX0001` and a fixed-endian JSON length, with explicit schema version and digest algorithm. Pack and index descriptors contain algorithm, digest and byte length. Immutable data/index names are content addressed; `head.json` is the atomically replaced pointer to the current index. Unsupported versions/algorithms fail while preserving cached files.

The packed cache is bounded to 16,384 live blobs, 64 MiB of live payload and eight referenced packs. Physical referenced data is limited to that payload budget plus pack headers. One staging pack is bounded to the same size; old and staged data can coexist, up to approximately 128 MiB plus headers and bounded metadata. The current and next index are each bounded to about 4 MiB. Staging and recovery scans have fixed entry limits. The eight-pack/physical-byte boundary triggers timed consolidation of verified live content; corruption discovered during consolidation is not copied as trusted data. Logical capacity exhaustion is an explicit quota error, without a global eviction policy.

A Linux advisory lease serializes each cache mutation/access transaction. Logical views own their backing memory after the lease is released. This is not a multiwriter/distributed-filesystem protocol, and byte/entry bounds do not establish a strict process RSS limit. The common manifest cache has a 4 MiB per-record bound but no global manifest-count/eviction quota; caller-owned materialization output is also outside the pack data/index quota. The original per-file control keeps its prior no-global-disk-quota policy; its measured namespace is bounded by the same manifest/corpus limits, without adding an artificial directory scan or quota index to the control.

A valid head selects either the prior or new immutable index. Failure before head publication leaves the prior committed mapping intact; unreachable owned files/staging are reclaimed with bounded recovery. A failed download can retain an already verified prefix as a partial cache admission but never publishes a completed-set receipt. Per-blob corruption is detected on requested reads and can be repaired by fetching only that blob. An unusable index can invalidate the packed cache's locator map and require online reacquisition; offline access cannot reconstruct lost geometry from opaque concatenated data. This is disposable cache recovery, not recovery of a sole authoritative repository copy.

Whole-pack digests are computed during sealing. Reopened access proves requested logical blob identities and verifies the index, not unrequested pack bytes; it does not rehash every complete pack for a sparse read. Single-owner immutable publication and owned read buffers prevent later file mutation from altering returned views. External concurrent cache mutation is outside the ownership contract.

## Verification and scope

All 1,344 complete operations and 117,376 requested-object checks pass. Every logical view, ordinary-file byte and receipt matches independently generated data. Transfer plans/counts/content bytes/requested hash work match across both layouts and transports. Extra representation hash work, publication counts and materialization counts are checked or reported separately. Fully cached operations use zero network on both layouts. All 49 [tests](correctness-tests.txt) pass, including both transports/all transfer modes, corruption repair, future-version preservation, owned-view lifetime, interrupted-prefix retention, publication failure, bounded compaction/quota behavior, cache leases and stale-file recovery.

This is a Python/Linux prototype over generated immutable corpora. Network servers/client interpreters stay resident. Cache directory/seed initialization, source/server admission and independent parent verification are setup outside timing. Every measured operation includes lease/open, metadata acquisition/verification, cache validation, transfer, digest work, publication, fresh logical access and connection closure. The file materialization endpoint is separately explicit. Writes use atomic visibility without fsync/power-loss durability. The response sleep remains an application-delay model, not a WAN, bandwidth, TLS or HTTP/2 result. Native Odin consumers, production quotas/eviction, longer fragmentation traces and real ecosystem workloads remain future work.

The gain belongs to shared local admission/access representation. It must stay separate from the earlier chatty-framing, selected-batch and bounded-buffer findings. [Format/access design](../../../../components/artifact-host/local-cache-research.md), [reproduction](../../README.md#verified-local-packindex-admission-and-logical-access), [summary](summary.json), [validation](validation.json).
