# Next storage questions

## Reduce eager admission without weakening verification

The [bandwidth loss](../../experiments/storage/results/service-model/REPORT.md) comes from full admission of mostly unused bytes. The [verified chunk follow-up](../artifacts/followthrough.md#demand-admission-trades-bytes-against-requests) now demonstrates the request/byte tradeoff with real consumers: smaller chunks reduce bytes but can increase modeled latency. Next test coalesced demand ranges, longer reuse and actual transport overlap under the same hash/lifetime contract. Do not give memory providers uncharged inputs or bypass requested-content verification.

## Separate service latency from actual block I/O

A future physical-storage claim needs verified private cold/page-cache conditions and actual I/O accounting. Advisory eviction alone is insufficient. Investigate an explicitly scoped mechanism that can establish what reached backing storage without dropping unrelated caches or changing a shared device/cgroup. Account buffered writes, file-backed mmap faults, metadata and read-ahead explicitly. The successful user-mode-only userfaultfd descriptor probe permits further capability research, but no functioning pager or realistic device model has been demonstrated here.

## Carry the boundary to a native consumer deliberately

A native compiler study must identify every modeled source/cache/output boundary, including mapped inputs and publication/writeback. Retained sealed inputs can legitimately skip later reads, while their initial import/check/copy and any required persistent outputs remain charged. A reload-versus-retained-snapshot test would describe that API contract, not automatically compare against ordinary Ninja/Clang filesystem behavior. Reusing an existing native pread/mmap test under a new label would add little evidence.

## Measure memory and stronger storage semantics separately

This proof retains immutable data across fresh normal interpreters but does not optimize or measure peak RSS. Include temporary import buffers, sealed copies and consumer mappings when choosing a memory budget. Required ordinary-file materialization, fsync/durability, concurrent clients, global bandwidth queues and service caching are separate contracts; apply them equally and retain first-consumer/session clocks rather than adding hidden setup work to one control.
