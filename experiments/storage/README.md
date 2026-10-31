# Explicit storage-service sensitivity

This track asks how verified in-memory inputs behave when dependency-data reads/writes become expensive. The first [report](results/service-model/REPORT.md) is a controlled **application-storage-service model**, not a degraded physical device, cold-cache benchmark or global filesystem throttle.

The same real Django REST dependency bytes run through two providers: explicit positional packed reads, or a fully imported/verified/sealed-memory input retained across fresh normal-exit Python processes. Both use the same compact index and per-logical-read SHA-256 plus CRC32. Persistent installation and full memory import are charged rather than hidden in setup.

## Why a separate model is necessary

Block controls such as cgroup `io.max` constrain device BPS/IOPS, not every application read; page-cache hits need not issue device requests. Buffered writes and shared mappings also reach backing storage asynchronously. Those boundaries are described by the [kernel cgroup documentation](https://docs.kernel.org/admin-guide/cgroup-v2.html#io). Slowing a device alone would not establish that a warm-cache workload paid that cost.

On the measured host, the [capability probe](results/service-model/capabilities.json) found an empty effective capability set, read-only cgroups and absent FUSE/userfaultfd device nodes. It could still open a `UFFD_USER_MODE_ONLY` descriptor: the [kernel userfaultfd documentation](https://docs.kernel.org/admin-guide/mm/userfaultfd.html#creating-a-userfaultfd) explicitly distinguishes user-only faults from kernel-fault permissions. Registration/features and a functioning pager were not tested. Repeat the probe on a new host; those observations are not prerequisites for this service model or proof of a functioning fault-controlled filesystem.

Private file advice is another possible tool, but [`POSIX_FADV_DONTNEED`](https://man7.org/linux/man-pages/man2/posix_fadvise.2.html) is advisory and dirty pages may remain unless written back. It cannot by itself justify a storage-cold claim. This experiment changes no cgroups, devices, global cache state or sysctls.

## Model and scope

Every selected synchronous service request costs:

`request latency + successful byte count / configured byte rate`

A zero rate means unlimited modeled bandwidth. Read/write rates and latencies are separate. The default profiles are:

| Profile | Read latency | Write latency | Read/write bandwidth |
| --- | ---: | ---: | ---: |
| nominal | 0 | 0 | Unlimited |
| request-latency | 1 ms | 1 ms | Unlimited |
| bandwidth | 0 | 0 | 16 MiB/s each |

This is per **logical service request**, not per syscall, page, physical I/O or SSD command. Host filesystem pages remain warm; the model deliberately charges a request even if the underlying `pread` hits the OS cache. The range backend has no additional application byte cache across processes. Consequently the result predicts sensitivity to that service contract, not what block throttling would do to warm ordinary files.

The source artifacts, persistent dependency cache and completion receipt are private to the run. All their logical data reads/writes pass through `ModelIO`. Interpreter/stdlib/native-extension/harness/project-fixture code, validation instructions passed over IPC and metadata lookup remain outside the injected boundary identically. This is not an audit of every process syscall or a whole-program filesystem simulation.

Writes perform the real buffered write/close/atomic rename, then delay the synchronous service acknowledgement. They do not call fsync or establish durability. Async kernel writeback therefore cannot be silently presented as throttled physical I/O. Metadata operations have normal measured CPU/filesystem cost but receive no invented latency.

## No private-file mmap bypass

Range consumers obtain index bytes through one modeled read, seal those bytes and map only that memory. Payload access uses explicit modeled positional reads. Admitted-memory consumers fully read/hash/copy/seal the payload and index from the published cache once, then map only those sealed descriptors. They reject ordinary file descriptors in memory mode. All consumers verify each requested logical file with SHA-256 and CRC32.

A persistent-store call first reads/verifies producer artifacts, validates full portable-index geometry and writes payload/index/receipt. That producer service ends with no admitted consumer payload. The independent memory consumer must pay its own import from the published cache. This matches a consumer beginning with installed persistent artifacts, not a pipeline retaining network buffers for free. Fresh child interpreters share sealed descriptors; no preloaded Django modules, early exits or loose source/template extraction are used.

The workload genuinely accepts logical bytes, so ordinary-file materialization is unnecessary and zero. This does not establish savings for a legacy tool that requires real exported paths. Temporary heap/sealed-memory copy cost is included, but peak RSS/minimum memory use is not measured.

## Reproduce

Python 3 with Linux sealed memfd support and interpreter-compatible prior artifacts is sufficient. No native build, kernel administration or package installation is needed by this track.

```sh
python3 -B -m unittest discover -s experiments/storage -p 'test_*.py' -v
python3 -B experiments/storage/capabilities.py
python3 -B experiments/storage/run_python.py \
  --payload /path/to/preindexed-flat-payload.gap \
  --index /path/to/portable.gpi \
  --output experiments/storage/_work/runs/main \
  --trials 3 --consumers 3
```

Use the pinned inputs from the [producer-preindexed artifact experiment](../artifacts/README.md#producer-preindexed-portable-payloadindex-pairs). The default descriptor/expected-data source is its retained flat-artifact summary. Reproducing under another Python version may require regenerating compatible bytecode/artifacts; pass that producer's summary with `--descriptors /path/to/summary.json`. Both full artifact hashes must match before any comparison.

A quick correctness smoke uses `--trials 1 --consumers 1 --profiles nominal`. Output directories must be fresh. Large source/cache/frozen data belongs under ignored `_work`; point it at a private adequately sized SSD directory when the worktree is on a constrained temporary filesystem. Machine-specific storage symlinks are ignored.

The runner calibrates all requested profiles first, then executes three shuffled paired blocks: 18 sessions and 54 actual consumer processes. First-total and complete-session clocks include persistent installation; admission and each child are also retained separately. Counter assertions require two installation reads/three writes, two additional full admission reads only for memory, exact range calls/bytes and zero modeled storage from sealed consumers. The same requested content/code/API/resource signatures and SHA/CRC policy must match throughout.

[Summary](results/service-model/summary.json), [validation](results/service-model/validation.json), [calibrations](results/service-model/summary.json), [capabilities](results/service-model/capabilities.json), [provenance](results/service-model/provenance.json), [seven-test log](results/service-model/correctness-tests.txt) and [raw identity](results/service-model/raw-identity.json) support review. Full exact-path observations and measured source snapshots remain ignored local data. The [findings](../../research/storage/findings.md) and [prospects](../../research/storage/prospects.md) separate this API model from future actual-storage or native studies.
