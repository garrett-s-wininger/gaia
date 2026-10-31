# A growing cache needs a retained index and a recovery policy

The existing packed-cache prototype can serve one selected object cheaply through a retained index. Reopening it reconstructs metadata proportional to the populated cache. At 3,931 unique real dependency objects, the observed median is 0.017 ms for an open-store lookup versus 12.708 ms for reopen plus lookup. This is a small local trace, not evidence that a packed format is universally faster than files.

## Growth trace

The probe derives 3,931 unique content objects from the 4,018-file Django dependency catalogue, verifies their producer hashes, and publishes them across five growth epochs. Both layouts receive the same objects and single-object requests. Seven lookup/reopen samples are taken at each epoch.

| Objects | Files: open lookup | Files: reopen + lookup | Packed: open lookup | Packed: reopen + lookup |
| --- | ---: | ---: | ---: | ---: |
| 100 | 0.047 ms | 0.064 ms | 0.017 ms | 0.587 ms |
| 400 | 0.043 ms | 0.119 ms | 0.041 ms | 2.432 ms |
| 900 | 0.036 ms | 0.184 ms | 0.016 ms | 3.340 ms |
| 1,600 | 0.084 ms | 0.104 ms | 0.100 ms | 5.309 ms |
| 3,931 | 0.019 ms | 0.052 ms | 0.017 ms | 12.708 ms |

The packed reopen path verifies/parses its index and checks recovery state. File lookup does not enumerate or authenticate every cached object. That policy difference is intentionally visible: using a pack should not force every request to rebuild a global index. These samples are one growth trace, with files measured before packed and changing selected objects; they are descriptive and do not establish a general latency ratio or a million-object scaling result.

## Eviction and retained views

An explicit experimental wrapper evicts alternating objects, forces compaction, and publishes the reduced live set. It verifies retained content, absence of evicted content and eight earlier reader views after consolidation. The old views are independently owned immutable buffers returned by the existing API. This does not test mmap leases or concurrent readers holding store locks across publication; the existing one-writer/access lease remains unchanged.

## Failure probes

Four separate probes pass:

- A verified complete prefix survives an interrupted following body. Incomplete bytes never reach `put_verified`.
- Injected ENOSPC during staged data writing leaves the prior head readable.
- Injected head-publication failure after pack/index publication recovers the previous index and removes orphaned data on reopen.
- An index with a correctly hashed but invalid locator is rejected. The current implementation discards availability and starts an empty cache; it does not recover a prior good index.

The interruption probe is at the body-verification/publication boundary, rather than a new socket-transport fault test; earlier transfer tests cover frame truncation. These probes exercise orderly exception/reopen behavior, not abrupt process death, torn writes, power loss or an fsync durability contract. There is no new concurrent-writer or authoritative-offline durability claim.

[Summary](summary.json) records samples/check names and the identity of ignored raw `results.json`. The raw file contains growth counters, compilation-independent timing observations, source hashes and corpus identities. [Reproduction](../../README.md) uses caller-supplied generated producer inputs and fresh work directories.

The useful follow-up is a bounded retained-index interface and an explicit prior-index/durable publication policy, followed by longer eviction histories and reader leases. Adding a binary local index may reduce parsing, but should be compared with retaining the existing index before introducing another format.
