# Next storage questions

## Reduce eager admission without weakening verification

The [bandwidth loss](../../experiments/storage/results/service-model/REPORT.md) comes from reading a full 29.3 MB bundle when a process requests about 6.7 MB through storage. Test bounded demand admission or producer-defined chunks/proofs with the same hash and lifetime contract. Do not give the memory provider uncharged inputs or bypass requested-content verification. More than three consumers can change amortization, but should be measured rather than inferred from one-shot timings.

## Separate service latency from actual block I/O

A future physical-storage claim needs verified private cold/page-cache conditions and actual I/O accounting. Advisory eviction alone is insufficient. Investigate an explicitly scoped mechanism that can establish what reached backing storage without dropping unrelated caches or changing a shared device/cgroup. Account buffered writes, file-backed mmap faults, metadata and read-ahead explicitly. The successful user-mode-only userfaultfd descriptor probe permits further capability research, but no functioning pager or realistic device model has been demonstrated here.

## Carry the boundary to a native consumer deliberately

A native compiler study must identify every modeled source/cache/output boundary, including mapped inputs and publication/writeback. Retained sealed inputs can legitimately skip later reads, while their initial import/check/copy and any required persistent outputs remain charged. A reload-versus-retained-snapshot test would describe that API contract, not automatically compare against ordinary Ninja/Clang filesystem behavior. Reusing an existing native pread/mmap test under a new label would add little evidence.

## Measure memory and stronger storage semantics separately

This proof retains immutable data across fresh normal interpreters but does not optimize or measure peak RSS. Include temporary import buffers, sealed copies and consumer mappings when choosing a memory budget. Required ordinary-file materialization, fsync/durability, concurrent clients, global bandwidth queues and service caching are separate contracts; apply them equally and retain first-consumer/session clocks rather than adding hidden setup work to one control.
