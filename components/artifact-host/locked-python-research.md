# A trusted hash lock and a direct packed Python consumer

The [end-to-end report](../../experiments/artifacts/results/locked-python/REPORT.md) connects generic hash-set transfer to a real dependency consumer. It reuses the prior pinned Django REST bytecode corpus, the existing streaming transport/local pack store and the indexed Python import/resource provider. It is a private research integration, not a package format or registry standard.

## Three independent responsibilities

1. **Discovery** maps a project name and exact version to a trusted lock descriptor. Mutable catalogs, authority and version solving belong here.
2. **Acquisition** receives a trusted set of algorithm/hash/size descriptors, checks the local cache and sends only missing hashes. No remote collection availability index is necessary when the lock already has those descriptors.
3. **Consumption** maps logical package/module/resource names to verified blob bytes. Python interpretation stays in the Python adapter rather than the transport.

The prototype carries logical file names, versions and resource pins in a local Python-specific lock, in addition to algorithm-tagged SHA-256 and size descriptors. It does not claim hashes alone are sufficient to discover module names. A future generic lock can refer to a separately addressed language index. Metadata remains independently addressable and is not attached to every payload record.

## Lock and acquisition contract

`locked_python.make_lock` builds a version-1 JSON document with `algorithm`, logical `files`, selected `versions` and `resources`. Each file records `name`, `sha256` and `size`. The caller supplies the trusted SHA-256 of the entire lock. Parsing rejects unsafe/colliding logical names, duplicate/conflicting hash sizes, unsupported versions/algorithms and bounds violations. The lock is at most 4 MiB, at most 16,384 logical files and at most 64 MiB of deduplicated content, matching this experiment's existing local cache limits.

`acquire(url, lock_bytes, pin, destination)` verifies that pin, checks all requested cached bytes and streams one list of missing hashes using the [existing GAF2 request](pipeline-research.md). The server responds from its immutable object map; the client needs no remote manifest, pack offset table, advertised size probe or version lookup. Expected sizes are already bounded and pinned locally. Every returned object is matched to the request, length-checked and independently SHA-256-checked before admission. The existing pack/index transaction seals and publishes the local representation, then publishes the logical lock and completion receipt. Fully cached valid requests need no connection. Failed streams emit no successful receipt; later acquisition validates and repairs missing/corrupt content.

The client still parses thousands of descriptors, and progressive records have per-object framing/validation costs. The 4,018-file Django lock is about 599 KiB, versus 770 bytes for a lock describing ZIP plus binary index. A single application flight does not eliminate this local work.

## Minimal discovery prototype

`locked_python.discover_exact(catalog_bytes, catalog_pin, name, version)` implements a separate pinned version-1 catalog. Entries contain exact opaque `name`, `version` and `lock` descriptors (`algorithm`, `digest`, `size`). It returns one matching descriptor and rejects ambiguous duplicate identities or unsupported/malformed entries. This is a small actionable lookup prototype; it has no HTTP registry, normalized Python project-name policy, version-range solver, signing mechanism or freshness/rollback policy.

For a local pinned catalog:

```sh
python3 -B experiments/artifacts/locked_python.py \
  /path/to/catalog.json TRUSTED_CATALOG_SHA256 example 1.0
```

The returned lock digest can authorize fetching that exact lock object using the existing bounded content-addressed retrieval API. The catalog pin must arrive through an independently trusted mechanism: a hash establishes content identity, not who should be trusted. Catalog download and policy are outside the measured lock-to-execution clock and must be timed separately if added. Production mutable name/version roots and immutable lock objects should remain distinct.

## Direct Python reader

`PackedReader` verifies the logical lock and local locator index, opens each immutable pack once, checks magic/size and retains the descriptors through the entire application lifetime. The reader exposes the existing module-table/read/resource interface. Reads use bounded positional access and SHA-256 verification of the requested logical file; owned returned bytes do not borrow a reusable socket buffer. Code goes through the prior interpreter-compatible bytecode loader; resources go through the prior `importlib.resources` adapter. Package discovery/enumeration retains the existing indexed path provider.

`locked_python_worker.py` substitutes that reader behind the unchanged Django application worker. Directory and indexed-ZIP controls use the same wrapper/common adapter imports. Each fresh isolated Python child validates 455 dependency module origins, matching executed-code sets, selected versions, filtered API output, app count, admin form markers and three resource hashes. The child forbids network activity and closes providers/database normally before shutdown. The parent waits for full process exit. No pack consumer exports code/templates/resources to loose dependency files.

This first reader rebuilds Python maps from JSON locks and the local cache index each process and uses positional reads plus SHA-256. The indexed-ZIP control uses a compact mapped index and CRC-checked reads after trusted local admission. Those are different implementation/integrity costs, explicitly retained. A reader-session trust policy or native index could change the cost, but skipping checks cannot be silently credited to a new storage format.

## Install controls and timing

The input is the existing pinned bytecode fixture, not recompiled dependency sources. Producer ZIP and binary index are prebuilt artifacts. The ZIP and directory controls fetch their two pinned hashes in one streaming request. Indexed ZIP retains the archive, rebinds the verified producer index to the newly admitted local stat identity, validates that index and pins its local encoding. Directory installation extracts the exact pinned logical set, validates each file's SHA-256 and creates ordinary paths. The directory consumer does not need the transferred sidecar; that small artifact is retained to hold the ZIP transfer control fixed. Packed acquisition requests deduplicated file hashes directly. Thus payload sizes and framing differ by representation, intentionally.

Complete acquisition/install timing includes lock verification, cache validation, transfer, all selected hashes, representation work, publications and receipts, plus extraction/index admission where applicable. The next clock spans a fresh Python process through normal shutdown and application validation. Reuse includes another complete cache-verified acquisition against an unavailable server and another child process. Input discovery, prebuilt bytecode/ZIP/index production and server admission are excluded producer setup, not claimed free. No transfer-delay model is added in this consumer run.

The immutable store retains 64 MiB/eight-pack bounds and bounded staging/recovery. It uses atomic rename without fsync, has no hostile-writer protection or full eviction policy and does not establish power-loss durability. Directory extraction is an experimental control rather than a production crash-recoverable installer. Native or namespace wheels, editable installs, arbitrary `__file__` consumers, entry points, scripts and extension ABI management remain outside the supported workload.

The integration works, but does not beat the indexed-ZIP control in the first exploratory comparison. Substantial within-run drift limits latency attribution. Profile immutable metadata construction and test equivalent integrity/session policies before attempting another native or format rewrite.
