# Producer-preindexed bundles and stored ZIP

The [matched comparison](../../experiments/artifacts/results/preindexed-bundle/REPORT.md) moves logical/offset-index construction to artifact production. Both flat binary payload and stored ZIP arrive as **two content-addressed artifacts: payload plus portable index**, described by the same generic binary resolved-lock core. This removes the earlier file-level lock/index construction tax from both receiver paths; it does not select a new public protocol.

## Producer versus receiver ownership

The producer receives the same pinned logical bytecode/resources and builds its representation. Flat payload uses the existing bounded `GAPK0001` immutable pack: one header and deduplicated contents. ZIP uses uncompressed regular entries. Both producers compute content/offset/digest/CRC and module/directory/child tables using the prior compact-index machinery, fully validate logical content and publish a pointer-free portable index.

`GAPORT01` retains the [compact fixed-width tables](compact-python-research.md) with version 1, but its metadata contains only expected logical-lock hash, representation kind and content-addressed container descriptors (`algorithm`, `digest`, `size`). It contains **no local filename, device/inode or timestamps**. Table offsets and logical names remain portable; interpreter-compatible bytecode is still a Python-specific payload requirement.

The generic lock references payload/index hashes and sizes, associates packages with those artifacts and marks the index as opaque Python consumer metadata. Names/versions and dependency interpretation retain their separate ecosystem contract. One request sends the complete missing artifact list; it never requests the server collection manifest or a 4,018-file lock.

The receiver:

1. Verifies its trusted generic lock and both selected CAS artifacts; cached artifacts are rehashed.
2. Checks that the portable index explicitly binds the expected payload digest/size.
3. Validates complete index table order/geometry/references once, without rebuilding its tables.
4. Publishes a small local binding recording the admitted payload path/stat identity and exact index/logical pins, then a separate installed receipt.
5. Opens the index/payload for a fresh normal consumer, verifies the index pin, header and local stat binding, and SHA-256 plus CRC32 checks every requested logical read.

The CAS-ready receipt means that requested artifact bytes are verified; the installed receipt additionally requires successful portable-index admission. They are distinct boundaries. The per-artifact cold hashes and per-read checks match between flat and ZIP. Compared with the previous file-level plan, hashing/publication granularity changes explicitly: clients authenticate whole payload/index artifacts instead of transferring/admitting every logical file separately. Requested runtime files still receive independent per-read SHA-256/CRC checks.

## Local binding, ownership and recovery

The local binding is separate from the portable index and is re-created after moving inputs between machines/directories. Its trusted local pin is passed to the reader. A metadata hash records identity rather than establishing authority; hostile writers able to replace both trusted admission pins and content are outside the shared immutable-cache assumption.

The reader maps the same portable tables and source payload once for its lifetime and returns owned read bytes through the existing indexed Python provider. Both containers use exactly the same lookup/access/verification code; ZIP is not reparsed by its consumer. No loose dependency code/template/resource paths are exported. Normal provider/database shutdown remains included.

Corrupt cached artifacts are reacquired by digest. Replacing a payload changes its stat identity and requires receiver rebinding; the harness re-admits after network repairs. An already open reader rejects incorrect requested bytes with SHA-256/CRC checks. Copying to a new directory also requires a fresh small binding, rather than rewriting producer tables. Tests cover partial caches, cross-directory relocation, offline reuse, corrupt payload detection/repair/rebinding, malformed headers and index/payload cross-binding failures.

The existing 64 MiB aggregate admission bound and bounded index/table limits remain. The receiver stores two immutable artifact files and small receipts/bindings. Atomic rename without fsync is not power-loss durability. This is not a crash-recoverable production package manager, eviction policy, mutable developer environment or hostile-writer protocol.

## Measurement and granularity

Producer representation/index construction is timed separately for each format and includes reading/validating payload bytes, building indexes and creating generic locks. It is not hidden in setup while claiming a free custom index. These are single producer observations; the receiver comparison uses five randomized paired blocks after one correctness warmup.

Receiver cold timing includes generic-lock parsing, all artifact transfer/hashes/publications, full portable-index admission and binding/installed receipt. A fresh isolated Python process then runs the unchanged 455-module Django REST workload, validates versions, module/code sets, API/admin output and resources, closes its provider/database and exits normally. Cached reuse rehashes the same artifacts against an unavailable endpoint, opens the admitted index and starts another complete child. Setup/read/hash clocks and paired totals are retained.

This is a package-level representation plan. Needing one small missing logical file can now require fetching a whole 28–29 MB payload. That is different from prior per-file hash selection. The partial-cache test covers an already cached payload requiring only its index; it is not a sparse-file/network-bandwidth benchmark. Logical-content subsetting and byte-range proofs would need their own index/trust/measurement contract.

The first matched result is near parity: flat transfers about 2.7% fewer bytes, but cold/reuse complete totals win only three of five pairs. The separate intrusive lookup profile identifies common lazy-table work that could be improved for both formats. It does not demonstrate a general binary-container win over a competent producer-preindexed ZIP.
