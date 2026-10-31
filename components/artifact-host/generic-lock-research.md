# Generic resolved locks: JSON and bounded binary views

The [measured comparison](../../experiments/artifacts/results/generic-lock/REPORT.md) tests a generic resolved-manifest core without selecting a public package protocol. The two encodings describe the same already chosen package/artifact set. Neither performs dependency solving, chooses platforms or interprets version syntax.

## Data model

| Table | Meaning |
| --- | --- |
| Packages, optional | Ecosystem, package name and opaque version strings. Names and versions retain ecosystem interpretation. |
| Artifacts | Algorithm-tagged content digest and unsigned 64-bit byte size. Content is independently addressed. |
| Associations | Optional package row, artifact row, opaque role and opaque label. One package can refer to many artifacts; one artifact can serve many packages/roles. |
| Metadata, optional | Ecosystem, opaque role and artifact row. Graph, target, provenance or consumer-index bytes are independently fetched content. |

There is no one-version/one-blob assumption. A wheel variant, native library, sources, debug symbols or platform metadata can be separate associations. The core represents an already resolved selection; a target matrix or ecosystem adapter determines which associations apply. Per-package metadata can use an ordinary package/artifact association, while the metadata table provides manifest-wide ecosystem/role bindings. Unknown role/label strings are retained without imposing their meaning.

Package identities are optional; unowned/shared artifacts use the `0xffffffff` package sentinel. Versions are opaque UTF-8 strings, not universal semantic versions. The core does not normalize project names, infer transitive edges, resolve markers, order releases, establish repository authority or decide whether two ecosystems' identities are equivalent. Independently addressed opaque metadata can supply those contracts separately.

## Version-1 experimental binary layout

All integers are big-endian. No native pointers, Python objects or platform ABI layout are serialized.

| Region | Layout |
| --- | --- |
| Header | 48 bytes: `GALOCK01`, version, mandatory flags, string/package/artifact/association/metadata counts, string/digest pool sizes and reserved field. |
| String table | 8-byte offset/length pairs into an interned UTF-8 pool. Strings are unique and byte-sorted. |
| Package table | 12-byte rows: ecosystem/name/version string IDs. |
| Artifact table | 20-byte rows: 16-bit algorithm tag, reserved flags, digest offset/length and 64-bit content size. |
| Association table | 16-byte rows: package ID or sentinel, artifact ID, role string ID and label string ID. |
| Metadata table | 12-byte rows: ecosystem string ID, role string ID and artifact ID. |
| Pools | Contiguous UTF-8 strings followed by raw digest bytes. |

Digest bytes have explicit offsets/lengths rather than an assumed universal width. The current implementation registers only algorithm tag 1 (`sha256`, 32 bytes) and rejects unknown algorithms, flags and versions. New algorithm support needs an explicit supported registry/validation rule; this prototype is not a global digest choice. Pool/table extents must exactly cover the body; unused or overlapping/noncanonical pool regions fail.

The research implementation caps the encoded lock at 4 MiB, each principal table at 16,384 rows, interned strings at 65,536 and each string at 4,096 UTF-8 bytes. Core sizes are 64-bit descriptors; the existing local cache separately enforces a 64 MiB aggregate admission quota. These are explicit prototype limits, not evidence for ecosystem-scale performance or a selected long-term standard.

The JSON encoding uses named records for the same model and validates the same package/content/reference semantics. Both verify the supplied trusted whole-lock SHA-256 before parsing/using content. Duplicate package/content identities, conflicting identities, malformed references and unsupported mandatory data fail. A hash identifies an immutable resolved lock; the mechanism that establishes trust in that hash remains outside the core.

## Lazy views and acquisition

`JSONView` decodes ordinary JSON records. `BinaryView` retains the immutable byte body, validates header/pool/UTF-8/identity/reference bounds and exposes table access plus lazy content descriptors. Immutable bytes input keeps its original no-copy body; mutable bytearray input is frozen before lazy access, and public record/string lookups reject negative or out-of-range IDs. It does not reconstruct all Python dictionaries by default. Full validation uses bounded temporary sets, so it is not allocation-free or constant-space. The cache planner subsequently creates the wrappers/state it actually needs, which remain inside complete acquisition timing.

Generic acquisition hashes/parses the actual selected encoding, verifies cached content, sends the same missing-hash stream and retains the same packed data/index. Returned objects have expected size and SHA-256 checked before admission. Cache sealing, publication and complete receipts remain charged. Unknown core algorithms fail before a transport request. Fully valid cached content works against an unavailable endpoint with no connection.

The measured core has five package identities, 3,932 content descriptors, 4,018 file associations and one independently addressed Python context object. Association labels are opaque to the core. The Python adapter interprets `python-file` labels as logical paths, verifies/decodes its referenced context, constructs and validates the prior logical Python lock, then builds the existing compact consumer index. All adapter conversion/JSON decoding and index construction occur **inside cold installation timing**. Reuse uses the previously admitted derived index; no measured JSON lock decode is performed outside acquisition.

The Python context holds the existing version/resource validation data and adds 487 content bytes equally to both encodings. Top-level import-package ownership is known from the fixture; distribution metadata files without an explicit ownership mapping remain unowned associations rather than guessed package identities. An ecosystem-owned graph/metadata schema would make that association authoritative in a full package workflow.

## Measurement boundaries

The common resolved input records come from the existing pinned Django bytecode fixture. Every cold observation includes encoding the selected lock format and hashing its pin, complete acquisition, explicit ecosystem adaptation, compact-index production, a fresh isolated Python application and normal shutdown. Format production is not free. Common fixture discovery/server admission and prior bytecode production are separately stated producer setup. Reuse has no new format production or index construction but retains full cache/lock checks and actual child execution.

Standalone parse CPU/wall measurements include whole-lock hashing and complete structural validation. Allocation tracing runs separately and excludes already provided input bytes; binary views retain that body, so their retained metadata is not total memory/RSS. Both process paths use the same compact mapped loader and SHA-256 plus CRC32 on every imported/resource read, with matching logical file sets, API/admin output and versions. Root-encoded bytes and metadata hash work differ by format; logical content transfer/hash/read work must match.

The first result favors binary parse/storage cost, but complete-operation differences remain noisy because the consumer process is intentionally identical. The [paired report](../../experiments/artifacts/results/generic-lock/summary.json) preserves every block and spread ratios. Prior specialized-JSON and compact-index negative results remain unchanged; they are not relabeled as this generic JSON control.
