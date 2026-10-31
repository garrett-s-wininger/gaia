# Retained binary logical metadata for packed and ZIP Python inputs

The [five-block report](../../experiments/artifacts/results/compact-python/REPORT.md) follows the [preserved direct-pack negative result](../../experiments/artifacts/results/locked-python/REPORT.md). It isolates process setup from complete acquisition/install cost, and makes per-read integrity equivalent before comparing containers. No production transport or package format is selected.

## Admission and consumer contracts

A trusted logical lock still provides names, SHA-256 hashes and sizes. Acquisition remains the existing missing-hash stream and verified local store: all requested content checks, representation seals, publications and completion receipts remain in the complete operation clock. The new consumer index is built only after admission, **inside cold install timing**, from the trusted lock and admitted representation.

Index construction binds each logical name to its expected hash, size, source container and offset. Each distinct content hash is independently checked against representation bytes and its CRC32 is computed. Duplicate logical names with the same content hash share that validation/CRC result; every eventual consumer read is checked independently. Complete derived-table geometry/order/bounds are validated before its trusted local pin receipt is published. The small generic representation supports either existing local packs or payload spans inside the prior admitted stored ZIP.

A subsequent process verifies the entire retained index hash and expected lock binding, validates header/region bounds and checks every source container's size and local stat identity before mapping. Individual table/string/data accesses remain bounded. This reuses producer-validated immutable metadata; it does not reparse the original JSON lock or reconstruct all Python maps. Both variants enforce **SHA-256 and CRC32 on every requested file read**. There is no alternate session mode that skips content verification.

The expected index pin comes from the trusted local derived-index admission receipt. The lock hash embedded in the index records that derivation; it is not independently a proof that arbitrary supplied index rows follow from a lock. Hostile writers able to replace both local data and trusted admission pins are outside this experiment's threat model, consistently for ZIP and pack. Hashes identify bytes, not their authority.

## Experimental layout

`compact_python.py` defines a version-1 local consumer index. Its big-endian integer fields and offsets contain no process pointers or serialized Python objects.

| Region | Layout |
| --- | --- |
| Header | 36 bytes: `GAPYIDX1`, version, metadata length, file/module/directory/child counts and string-pool length. |
| Binding metadata | Bounded JSON: expected lock hash, representation kind and at most eight source-container descriptors. |
| File table | 68-byte rows: name offset/length, container ID, reserved flags, 64-bit payload offset/size, 32-byte SHA-256 and CRC32. Sorted by UTF-8 logical name. |
| Module table | 16-byte rows: module-name offset/length, file row ID and package flag. Sorted by module name. |
| Directory table | 20-byte rows: relative-name offset/length, package flag, child start/count. Sorted by relative name. |
| Child table | 32-bit module row IDs for each directory's direct children. |
| String pool | UTF-8 bytes addressed by bounded offsets/lengths. |

The index is at most 4 MiB, uses the existing bounded logical-file set and references containers no larger than the existing 64 MiB representation limit. Source descriptors record relative local paths, representation hashes/sizes and five stat identity values. Those local identities must be rebound by admission on another machine: this is a **local derived consumer index**, not a portable remote artifact catalog or selected public schema. The underlying tables are pointer-free; external metadata/provenance and platform-local identity policy would need separate standardization.

Lazy mappings use binary search for entries/modules/directories. Precomputed package/child tables feed the existing indexed path finder through lazy rooted adapters. Resource access uses the prior common resource API. Data is mapped once and each read returns owned bytes; no consumer retains a view into a reusable network buffer. The index and container mappings close with the provider after the real workload finishes.

## Matched and historical controls

Four readers run the exact existing 455-module Django REST workload:

- Old indexed ZIP: its original admitted binary sidecar, mapped payload access and CRC checks.
- Old direct pack: its original JSON locks/locators, reconstructed Python maps, positional reads and SHA-256 checks.
- Compact ZIP: new retained index, shared mapped reader and SHA-256 plus CRC32 on every read.
- Compact pack: the same new index/reader/policy over retained local pack payloads.

The **last two are the matched integrity/access-policy pair**. Comparisons with the first two establish effects on earlier implementations but change metadata/provider code or integrity checks and must be labeled accordingly. In particular, compact ZIP adds SHA-256 over old ZIP's CRC policy; any overhead is not attributable solely to digest work because lookup/provider code also differs.

All processes share a wrapper and common adapter imports, use `python -I -S -B`, forbid application network activity, validate matching dependency origins/code-execution sets, versions, API/admin behavior and resource pins, close providers/database and exit normally. The parent waits for full shutdown. Packed cases never create loose dependency files. Setup, read/copy and digest subclocks are retained in the existing worker's `native_timings` compatibility field; no native implementation is implied.

## Complete operation and recovery limits

Cold operations restore independent empty destinations and include complete acquisition, local index production/validation/publication, child startup, workload checks and shutdown. Reuse revalidates the acquisition cache, opens the retained consumer index and starts another normal process with an unavailable server; no network request is allowed. Package artifacts and bytecode are prebuilt producer inputs, whereas new local consumer-index creation is explicitly charged. Logical file hashes and prebuilt ZIP/index hashes describe different physical transfer representations; those byte/count differences remain reported.

The index can become stale if local compaction or repair replaces a source representation. Its stat identity/open check fails rather than accepting changed bytes; callers must rebuild the local derived index from the repaired trusted acquisition state. This first harness covers initial installation and unchanged offline reuse, not a production installer with automatic stale-index repair, eviction or crash recovery. Atomic writes use rename without fsync. An interrupted index admission must not be treated as complete without its matching trusted pin receipt.

Tests cover index pins/expected-lock binding, unsupported versions/truncation, lookup/module/package/resource behavior, closed lifetimes, changed container identities and corrupted bytes during an open session. Independent tests alter only SHA-256 or only CRC32 expectations to prove both checks execute. Matched pack/ZIP tests compare all selected bytes and policies.

The retained index removes most old reader setup work and improves reuse, but its cold construction must be amortized. Once access/check policies match, Python process times are close between ZIP and pack, while complete packed acquisition still loses on thousands of descriptor/cache records. The next meaningful boundary is acquisition metadata, not another container-only startup claim.
