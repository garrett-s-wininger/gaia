# Verified local pack/index cache experiment

This is a disposable local-cache research implementation, not the authoritative artifact repository format or a selected public protocol. It tests the shared publication work identified by the [buffered transport experiment](../../experiments/artifacts/results/buffered/REPORT.md). HTTP and buffered binary retain their transfer plans and verification rules; the local admission representation changes on both.

## Logical access contract

A caller supplies the already trusted manifest descriptor and a selected set of logical blob identities. Acquisition verifies the manifest and each cached or fetched requested blob. The access API then reopens the cache, rechecks the manifest and requested blobs and returns a digest-to-view map. Views are read-only and backed by owned immutable read buffers; they do not borrow mutable mmap pages or require later reads to become usable. Closing the store, repairing cached files or releasing the cache lease cannot mutate returned values.

Both file and packed layouts implement this contract. The measured complete operation includes acquisition, publication/receipt and the fresh verified logical access. Requested logical/manifest hash work must match; packed representation/index hashes are extra charged work. This fresh-consumer clock is stronger than the earlier transport-only endpoint, so its absolute medians should not be compared with old results without remeasuring controls.

Ordinary-file consumers are a different interface. The file control already has per-digest files; packed content must be materialized if the consumer needs those paths. That step is measured separately and included in a second combined endpoint. The adapter returns digest-to-path mappings, not an ecosystem-specific directory tree. Writable copies, permissions, namespace reconstruction and actual tool execution remain separate costs.

## Local representation

| Record | Experimental representation |
| --- | --- |
| Data pack | `GAPK0001` followed by concatenated verified blob payloads. Its descriptor includes SHA-256 and exact byte length. |
| Immutable index | `GAIX0001`, an unsigned big-endian 64-bit JSON-body length, then a versioned JSON record. |
| Index contents | Schema version, digest algorithm, bounded pack descriptors and blob digest/size/pack/offset entries. |
| Current head | Atomically replaced `head.json` containing its own schema version and the immutable index descriptor. |
| Completion receipt | The existing requested-set receipt, separate from local storage metadata. |

Pack and index filenames are derived from their content identities. The index body is bounded and checked for duplicate keys, unsupported versions/algorithms, invalid descriptors, bounds, overlapping extents and duplicate logical identities. Reopening verifies the selected index against the head's descriptor. Requested blob contents must independently match the trusted manifest; local filenames, offsets and checksums are not substitutes for that proof.

A whole-pack seal is computed during publication. Sparse access verifies the index and requested logical blobs without rehashing unrequested pack bytes. This does not prove that an externally corrupted whole pack still matches its former seal. The cache ownership contract uses immutable publication; returned buffers additionally own their bytes independently of later filesystem changes.

## Publication transaction

1. Hold the local cache lease and recover bounded owned staging/orphan files.
2. Reuse only locally available blobs that verify against the requested descriptors. Missing or corrupt content follows the unchanged transport plan.
3. Append newly verified blobs to one staged pack. The old head remains valid.
4. Seal and atomically publish the data pack, then publish its immutable index.
5. Atomically replace the head to select the new index. Retire unreachable owned packs/indexes with a bounded scan.
6. Publish the requested-set receipt only when acquisition succeeds. The fresh logical access follows inside the measured complete operation.

A small delta can add a pack and update the index while retaining existing data packs. It need not rewrite every cached payload. The eight-pack or physical-byte boundary triggers consolidation of verified live content inside the operation. A failed transfer may publish an already verified prefix as partial cache content, but does not publish a completed-set receipt. Failure before head replacement leaves the prior committed mapping intact; interrupted owned staging and unreachable files are recovered on reopening.

Atomic replacement supplies visibility in the experiment. Fsync, crash/power-loss durability across directories and a distributed-filesystem commit protocol are not established.

## Bounds and ownership

The packed cache allows 16,384 live blobs, 64 MiB live payload and eight referenced packs. Referenced physical data is bounded to that payload budget plus pack headers. One staged pack can coexist with the old data, roughly 128 MiB total data at the boundary. Each current/new index is bounded to about 4 MiB. Recovery scans have fixed entry limits: staging, current/next index and at most one newly published data orphan beyond the eight-pack limit. The common manifest cache is outside the pack data/index quota: each manifest is bounded to 4 MiB, but a global manifest-count/eviction quota is not implemented. A caller-managed ordinary-file materialization destination is also outside that quota; requested bytes and publications are reported separately. Unknown owned-directory entries and quota exhaustion produce explicit errors; no global eviction policy is implemented.

The reader combines only adjacent requested extents into reads, targeting at most 4 MiB per span; a single larger bounded blob can exceed that target. It does not pull unrequested gap bytes. Returned owned buffers are bounded by the requested data; retaining a small view can keep its whole adjacent read span alive. Entry/data limits do not establish a strict process RSS quota or bound caller-retained results across many operations.

A Linux advisory lease serializes each mutation/access transaction. Multiple cooperating processes receive an explicit busy error rather than racing the mutable head. Long-lived borrowed views do not hold that lease because their backing bytes are owned. Noncooperating external cache mutation, multiwriter fairness, distributed locks and non-Linux platform behavior are unmeasured.

The file control preserves its original per-blob layout and no-global-disk-quota policy. Its measured namespace obeys the same manifest/corpus bounds. It is not given an artificial quota scan/index merely to make the packed layout look cheaper.

## Corruption and compatibility

Requested corrupt blobs are rejected and can be reacquired independently. A damaged locator index can invalidate all packed cache availability and require online reacquisition; opaque pack bytes alone do not reconstruct lost geometry offline. This is a cache, not the sole copy of user work. Unsupported schema versions or digest algorithms fail while preserving the cached files rather than silently converting future data.

Tests cover a failed head publication, stale staging and orphan cleanup, partial verified-prefix retention, individual blob corruption, index corruption, future-version preservation, lease conflicts, bounded consolidation and quota exhaustion. The same transport/framing error suite still applies.

## Result and next boundary

The [measured comparison](../../experiments/artifacts/results/admission/REPORT.md) reduces cold complete logical access from about 10 to 4 ms for small data and 16 to 11 ms for mixed data on both transports, with 130 publications reduced to five. Fully cached logical access also improves while staying offline. Tiny selections and metadata-only operations can lose to fixed index/setup cost. Requiring ordinary files reverses many mixed/cache-reuse wins.

The result supports a direct logical-byte interface. It does not show that a packed cache automatically speeds up every filesystem consumer or that the storage gain belongs to binary framing. Native Odin admission/access, lazy or binary indexes, real artifact sets, larger bounded traces, eviction and durable recovery remain future work.
