# Independent requests and progressive known-list responses

This is a private, versioned GAF2 loopback experiment. It retains the [existing framing](binary-framing.md), [logical cache contract](local-cache-research.md), SHA-256 descriptors and HTTP controls. It does not select a production public protocol. The [report](../../experiments/artifacts/results/pipeline/REPORT.md) separates request scheduling, missing-list batching and progressive consumption.

## Begin with the availability index

The trusted manifest already describes available logical hashes and sizes separately from payload. A client validates its pinned root, checks its local cache and sends only missing hashes. This is independent of the physical pack layout. The existing selected-batch exchange already sends the entire missing hash list once; streaming changes delivery and bounded parsing rather than removing another request.

The four paths use one GAF2 server and connection implementation:

| Path | Application requests | Response behavior |
| --- | --- | --- |
| Serial | One per missing object, wait before next | Complete object response |
| Windowed | Up to eight independent outstanding requests | Correlated complete-object responses may finish out of order |
| Buffered list | One entire missing hash list | Build/read the complete bounded batch body |
| Streamed list | One entire missing hash list | Emit complete object records progressively, then END |

A known index permits one application request/response flight for either list path. A fresh TCP connection and cold index discovery are separate. Fully cached pinned content needs neither. The benchmark reports established and newly connected pinned profiles separately and includes a cold-index/offline boundary.

## Wire layout and limits

The 24-byte big-endian header retains the earlier shape: magic `GAF2`, version byte `2`, operation byte, 16-bit flags, 64-bit request ID and 64-bit body length. The server requires strictly increasing IDs beginning at one per connection. IDs cannot wrap or be reused. The client accepts only currently pending IDs with matching operations and bounded lengths. Unsupported versions/types/flags and malformed/truncated records fail.

Operations 1/2 retain manifest/object descriptors; 4 is the existing complete buffered batch and 5 is progressive list streaming. Request bodies use the existing algorithm-tagged SHA-256 descriptor or bounded shared missing-list schema. Control operations 240/241 are research counter reset/read and do not belong in a public protocol. Unknown algorithms are rejected; GAF2 does not introduce a shared digest choice beyond this tagged SHA-256 baseline.

For operation 5, flag `3` means DATA. The body begins with the existing 50-byte descriptor (status, algorithm, digest, total size, offset) followed by exactly that object's bytes. The client matches the expected ordered identity and size, then common transfer code independently hashes the bytes before admitting them. Flag `5` means END: 8-byte `GASEND01`, 32-bit object count and 64-bit raw byte count. END must match the complete requested set. Flag `9` means ERROR: 8-byte `GASERR01` and a 16-bit code. A missing object produces code 1. An incomplete stream never yields a successful requested-set receipt.

The windowed client limits outstanding requests to eight and requested in-flight bytes to 4 MiB. One oversized object is permitted alone, up to the pre-existing 64 MiB object/representation cap. This is a logical in-flight limit, not a process RSS guarantee. The collection remains bounded to 16,384 objects; metadata to 4 MiB; batch bodies retain the existing 64 MiB payload plus bounded descriptor overhead. The server caps connections at 33, has eight workers globally and eight submitted requests per connection. These explicit experimental bounds do not constitute production resource fairness or global queue-byte admission.

Responses are serialized under a write lock **per complete frame**. Independent requests can complete out of order, but object bodies are not interleaved in smaller chunks. A large or blocked object frame still causes connection head-of-line blocking. Streamed-list objects retain requested order. General chunk scheduling, priorities, cancellation negotiation and fairness are deferred.

## Ownership, errors and recovery

The client reads through the owned buffered reader into owned object bytes. A verified callback receives a read-only view whose lifetime is independent of the socket buffer. The first-new-verified timestamp is taken after the common digest check and before storage admission: it measures usable in-memory bytes, not durability or visibility to another cache reader. Packed cache transactions publish their new index later. The full operation still waits for all verification, atomic cache publication, completion receipt and fresh verified consumer reopen.

On malformed responses, unsupported versions, wrong identities, truncation, ERROR or an abandoned streaming/windowed iterator, the client disposes the connection with all pending work. It cannot silently reuse that connection and interpret old pending frames as a new response. Recovery starts a new client, validates the pinned manifest/cache and reuses already admitted verified objects. The loose-layout recovery test retains two complete verified objects after a third record truncates; packed transactions follow their existing abort rules. No partial unverified object is published. Atomic publication still uses rename without fsync; power-loss durability is unproven.

## Experiment model

One separately spawned server holds admitted immutable bytes in memory. Workers are prestarted before timing. The nonzero-delay condition schedules an independent 2 ms readiness sleep once per logical request. Eight pipelined object requests can overlap those waits; an entire list stream waits once. The model neither sleeps sequentially in the connection reader nor charges every streamed object another delay. It is an application-readiness sensitivity model, not a WAN RTT, packet-loss or bandwidth model.

The complete operation includes manifest acquisition/verification when cold, cached-content validation, all selected transfers/digests, representation work, cache publication, receipt and a fresh verified logical consumer access. Optional ordinary-file materialization is timed separately and in a combined endpoint. Corpus construction, server admission, restored cache seeds and established connection setup are excluded and identified. Newly connected pinned-index profiles include the TCP connection in their operation; established setup/primer samples are recorded separately. Python/server startup is outside the request endpoint.

The [56-test suite](../../experiments/artifacts/results/pipeline/correctness-tests.txt) includes out-of-order completion, bounded pending requests, error/truncation, connection disposal, callback ownership, reuse and fully offline cache access. The first measured matrix is one mixed-size generated corpus, both cache layouts, three cache/connection profiles, two readiness delays and three paired randomized blocks. Its purpose is to choose the next experiment, not establish production latency guarantees.
