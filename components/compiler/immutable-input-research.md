# Shared immutable compiler inputs: research contract

The [measured prototype](../../experiments/compiler/results/shared-inputs/REPORT.md) shares sealed input bytes and BLAKE3 file identities across compiler and dependency replay requests. This is a Linux local-process experiment, not a selected public storage/protocol standard. It preserves the external mutable-file receipt checks.

## Source of truth and lifecycle

A trusted caller already owns an admitted logical file map. First publication creates a sealed base; subsequent explicit edits create smaller immutable segments. Membership deletion is represented by final tombstones. The receiver independently authenticates every new segment and retains its own mapping/FD; payloads cannot be overwritten, resized or unsealed. Cache references are by content pin. A locator is needed only on a miss.

The current view applies segments in order, removes final tombstones and validates the resulting sorted namespace. Compilation and dependency replay borrow this exact view and cached file digests. Compiler workers retain private VFS cwd/observation state. A pool leases all backing segments until workers and dependent views have been released, so eviction or closing the publisher's FD cannot invalidate live bytes. Only the serial request owner mutates cache state.

The caller still binds visibility masks, command plans, cwd and tool context through the existing admitted request interface. Payload sealing does not replace those semantics. The current benchmark also scans the same known physical namespace for edits and retains all positive backing-file hashing during condition export. A future collection-authoritative workspace must explicitly define update discovery and logical validation before removing that compatibility path.

## Experimental encoding

All integers are little-endian. Bounds are checked before consumers use offsets or strings.

| `GAIACIN4` field | Encoding |
| --- | --- |
| Magic | Eight bytes `GAIACIN4`. |
| Final file count | u64, at most 100,000. The compiler adapter requires at least one. |
| Segment count | u64, 1–8. |
| Each segment | u32 locator length, UTF-8 absolute locator bytes, u64 serialized size, 32 raw BLAKE3 digest bytes. Duplicate pins are rejected. |
| Final tombstone count | u64, at most 100,000. |
| Each tombstone | u32 length and canonical absolute UTF-8 name bytes; unique. |

The complete manifest is at most 4 MiB and is pinned by `blake3:<hex>`. Each segment contains the existing `GAIACIN3` absolute-file encoding, independently authenticated with its own BLAKE3 pin. Paths are canonical, at most 4,096 bytes, with no NUL/backslash/dot traversal. The final namespace rejects file/directory collisions and unexpected membership/counts. Masks are a separate sorted `GAIACV1` input, unchanged from the prior provider.

Locators currently use `/proc/<publisher-pid>/fd/<fd>` and the receiver requires kernel seals `SEAL`, `SHRINK`, `GROW` and `WRITE` before read-only mapping. These are process-local Linux locators, not durable content identity or a portable lock format. A transport using inherited descriptors, SCM_RIGHTS or immutable artifact-store objects could implement the same ownership boundary later. Neither a regular filename nor a timestamp alone establishes this proof.

## Bounds, reset and recovery

Referenced serialized bytes are at most 64 MiB per collection. The receiver retains at most eight segments/64 MiB in its cache and evicts the least recently used cache ownership when admitting more. Active leases can temporarily retain data outside that cache budget. The publisher compacts its current chain when it would exceed count/byte limits, with compaction charged to publication. Repeating a previous segment reuses and moves it to the last position rather than duplicating a pin. Caller snapshots can independently keep older source FDs alive.

Two internal controls support deterministic research: reset retains only an explicit bounded pin set; prime authenticates a seed manifest without compilation. The benchmark uses them outside timing to restore previously admitted base state, while the actual edit segment is created/verified inside timing. Clean requests reset both producer and receiver and charge full reconstruction. These are testing controls, not user maintenance operations.

Malformed manifests or new segment failures produce no admitted pool. Already verified cached segments may remain useful after a failed larger request. Independent restart requires admission again. Failed compile/receipt behavior remains the existing fail-closed protocol. No multiwriter cache, persistent GC, crash durability, total RSS bound or cross-platform implementation is established.

## Verification and implementation

The [publisher](../../experiments/compiler/shared_inputs.py), [receiver](../../experiments/compiler/shared_inputs.h), [real-parser tests](../../experiments/compiler/test_shared_native_inputs.py) and [real compiler tests](../../experiments/compiler/test_shared_history.py) provide the review boundary. The main report records initial creation versus warm update costs, reference artifacts/conditions, cache ownership, RSS observations and reproduction. No AST or application-result preparation is hidden in this representation.

## Authoritative logical workspace experiment

The optional [logical provider](../../experiments/compiler/logical_workspace.py) makes admitted API changes authoritative. A generation retains immutable file bodies, visibility masks, per-body SHA-256 digests and derived namespace nodes. Updates copy mutable caller buffers, validate bounds and publish atomically under a workspace lock. An optional expected generation supports compare-and-exchange; an unrelated update can coexist with a completed build. The current prototype copies the map on update, so it does not establish large-repository update complexity.

A compiler operation captures one generation and consumes only its admitted bodies/masks. Its completion conditions must hold both in that captured generation and in the current generation. Publication holds the update lock while checking and writing the completion receipt. Positive file bodies, missing paths, directories, visibility and observed directory listings retain their meanings. A relevant concurrent change prevents declaring the result current; an unrelated change can remain selective. A later update can invalidate a receipt, so readiness is always relative to an observed generation, not a promise against future edits.

The separately versioned `GAIALQ01` condition index retains the existing bounded/checksummed row layout but reserves physical timestamps/mode fields as zero. Positive rows retain exact size and SHA-256. Validation uses admitted digests rather than reading a physical source mirror. The in-process reference checker still pins the complete tool set and request identity, hashes all copied outputs, and checks the condition-index output against the validated bytes. Linked-result history remains bounded to three candidates. This prototype is a contract experiment; the physical checker remains available and the native compiler backend is unchanged.

Unreported changes to physical files do not alter this logical authority. A caller using a mutable filesystem must import changes through a separate adapter. The supplied strict known-namespace importer reads all known files between global before/after metadata checks and atomically admits the resulting packet only if both the physical observations and expected logical generation remain stable. It charges those reads and checks explicitly. It does not discover new directory members, provide a watcher, make a hostile mutable filesystem transactional, or eliminate initial SDK discovery. A production filesystem bridge needs its own discovery and concurrency contract.
