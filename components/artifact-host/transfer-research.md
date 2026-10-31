# Artifact transfer: research design

This is an initial research design, not an agreed public protocol or a production artifact service. It explores delivering immutable dependency inputs, toolchains and build outputs without requiring every tool to recreate package downloads and caches. The existing [platform direction](../../docs/platform.md) still applies: native implementations use Odin, solo/offline use must work, and logical identities remain separate from physical layout.

The first runnable baseline uses ordinary HTTP/1.1 and Python's standard library to expose request/byte amplification before choosing a native transport. [Measurements and reproduction](../../experiments/artifacts/README.md) are separate from this design.

## Scope and ownership

The artifact layer moves and admits bytes. Dependency adapters interpret package metadata and choose versions; compiler adapters describe executable requests/results; source control owns snapshots and review records. A transfer must not require importing ecosystem semantics or fetching review/attestation metadata that the consumer did not request.

| Layer | Research contract |
| --- | --- |
| Logical descriptor | Algorithm-tagged content digest and expected byte length; optional media/schema type lives in caller metadata. |
| Artifact metadata | A separately identifiable immutable record describing the required blob set and, when relevant, logical names and relationships. |
| Physical representation | Optional pack, codec or chunk layout with its own identity, geometry and resource bounds. Repacking does not change the logical blob identities. |
| Locator | Where an object/representation can currently be obtained; not part of its logical content identity. |
| Transfer plan | Which missing blobs/regions to fetch, in what order, with bounded requests, bytes, concurrency and memory. |
| Admission | Verify requested lengths/digests, publish verified bytes, then expose a receipt for the completed requested set. |

Keep these contracts usable through in-process access, local IPC and remote implementations. An optional pack layout should not force every consumer to materialize individual files; the first experiment deliberately uses the same per-blob local cache layout for every transport mode to isolate transfer shape.

## Trust and identity

A caller begins with a previously trusted metadata descriptor: digest algorithm, digest and size. That descriptor may come from a lockfile, source snapshot or an authenticated higher-level registry. A digest downloaded alongside untrusted bytes does not establish who published them. Publisher authentication, authorization and artifact attestations need their own contracts.

SHA-256 is the initial experimental provider. The fixture manifest, URL namespace, cache namespace and completion receipt explicitly tag it. Unsupported algorithms are rejected. This does not select a universal Gaia digest or silently reinterpret a future BLAKE3 value. Any new provider needs an explicit tag, byte semantics, compatibility tests and version/capability handling.

Logical blob verification remains valid after repacking. A pack descriptor identifies exact representation bytes, including compression if any. If the client fetches the whole pack, it can validate that representation digest. A range plus an ETag is not a cryptographic proof of the whole pack: requested blobs must independently validate against their trusted logical descriptors. Unrequested bytes pulled across a gap are not admitted merely because they travelled in the same response.

## Initial read path

1. Obtain the immutable metadata record independently. A cached record is usable offline after checking it against the caller's trusted descriptor. Parse version, digest algorithm and bounded lengths/counts before following payload references.
2. Select the blobs needed for this operation. An empty selection loads metadata only. Do not force full artifact materialization just to inspect it.
3. Validate reusable local content under the cache's ownership contract. The first experiment rehashes existing bytes, rather than trusting filenames or timestamps.
4. Choose among individual blob fetches, bounded concurrent fetches, pack ranges and a full pack. Charge metadata, negotiation, verification, overfetch and publication to the operation.
5. Admit each successfully verified blob. Incomplete/unverified bodies remain unusable. A failed operation may retain earlier verified blobs for a later attempt.
6. Publish the requested-set receipt only after every requested blob is available and verified. Atomic rename supplies visibility in the experiment; crash/power-loss durability is not measured.

A local-only caller should complete step 3 without contacting a service. A remote-capable CLI may manage a lightweight local process, but trying the research does not require an account or external server administration. The harness starts and stops its own loopback server.

## Existing transport baseline

HTTP supplies the first interoperable transport substrate. The experiment uses content-addressed resource URLs, persistent connections, ordinary GET, identity encoding, byte ranges, strong ETags and `If-Match`. It validates returned status, size, ETag and `Content-Range`; if a server ignores Range and sends a bounded full representation, it validates the whole pack before using it. RFC 9110 permits range requests to be ignored and defines partial-response/validator rules. The harness intentionally avoids multipart ranges. [HTTP semantics and ranges](https://www.rfc-editor.org/rfc/rfc9110.html#section-14), [206 and combining parts](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.3.7).

The unencrypted loopback baseline does not establish remote authentication, TLS cost, HTTP/2/3 behavior, proxy/CDN interoperability or WAN performance. A delay before each server response is an application-delay model, not an emulated network RTT or loss model.

Existing systems provide useful compatibility targets, rather than a reason to adopt every schema. OCI descriptors already separate digest, size and media type; an adapter could preserve those logical descriptors while using a Gaia-specific local representation. Bazel's remote APIs separate batched small-blob reads from streamed large-blob transfer. Neither observation means this prototype implements OCI distribution, REAPI or remote execution. [OCI descriptors v1.1.1](https://github.com/opencontainers/image-spec/blob/v1.1.1/descriptor.md), [REAPI content-addressable storage interface](https://github.com/bazelbuild/remote-apis/blob/main/build/bazel/remote/execution/v2/remote_execution.proto).

A [matched binary framing experiment](binary-framing.md) now compares the same object/range/full-pack plans over a versioned TCP envelope. It retains JSON metadata and all admission checks. Selected-object batching uses the same body over HTTP and binary so envelope savings and operation-count savings remain separate. The comparison is research, not a replacement of HTTP interoperability or a selected public protocol.

## Recovery and bounds

The first implementation resumes at verified-object boundaries. It does not retain unverified partial bodies or retry automatically. Later byte-level recovery must bind saved fragments to a stable representation, and still validate the completed logical blob or a trusted chunk-proof structure before admission. A content-addressed URL alone does not make an incomplete file usable.

The fixture limits metadata to 4 MiB, packs/blobs to 64 MiB, collections to 16,384 unique objects and concurrent object requests to 32 (eight measured). Coalescing has independent gap/span limits. These are research resource bounds, not proposed universal limits. A single large object is not split by the coalescer; its maximum size remains separately bounded. Responses use identity encoding so byte offsets refer to the selected representation.

Cancellation should stop speculative work and preserve verified admissions. Server storage pressure must produce explicit availability/quota errors; it must not require users to run maintenance rituals to recover normal operation. Cache eviction, ownership, concurrency, quotas and durable recovery remain separate experiments.

## Write path to investigate next

Uploading should use the same identities and admission rules: describe the intended content, find missing identities in bulk when worthwhile, stage bounded transfers, verify on the receiver, then publish immutable metadata/root records atomically. Uploading execution logs or review records must not be a prerequisite for uploading source/toolchain bytes.

The first experiment implements reads only. Authorization, resumable upload sessions, concurrent writers, mutable discovery aliases, repository retention policy and remote commit/publication are unanswered. An initial interoperable read baseline should constrain these questions without turning the artifact host into a compiler scheduler or CI executor.

## Decisions this work does not make

The research does not select a universal hash, chunk size, compression codec, pack format, native HTTP library, RPC framework, object-store provider or production service architecture. The measured request/byte tradeoffs should guide the next experiment. Small-object batching, sparse retrieval and verified offline reuse need first-class semantics even if their physical mechanisms differ.
