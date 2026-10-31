# Binary framing experiment

This private versioned transport tests whether a simpler message envelope improves complete artifact fetches. It does not replace the [HTTP baseline](../../experiments/artifacts/README.md) or choose a production public protocol. Native implementation language remains Odin; both measured transport adapters are Python so language changes do not explain the comparison.

## Controlled comparison

HTTP and binary use the same trusted, separately fetched JSON manifest bytes, SHA-256 identities, requested sets, cache seeds, object/range/full-pack plans, digest checks, local publication and completion receipt. The binary envelope does not make the manifest binary. It also does not change content identity or treat a range as proof of unrequested bytes.

The selected-object batch is a second, independent experiment. Its request and response bodies are identical over HTTP POST and binary TCP. It carries only missing selected blobs instead of forcing a whole pack or gap overfetch. Comparisons within one transfer mode isolate the envelope/adapter implementation; comparisons between modes include a planning/batching change and must be labeled accordingly.

Both servers are separate resident processes over loopback TCP, with Nagle disabled. Every fetch creates its own client connections and closes them inside the operation clock. There is one outstanding request per connection, with bounded parallel blob requests using separate connections. TLS, authentication, multiplexing, cancellation, compression and WAN behavior are unmeasured.

## Frame header

All integers are unsigned big-endian wire values, never native structs or process pointers. The 24-byte header precedes each request/response body:

| Offset | Bytes | Meaning |
| ---: | ---: | --- |
| 0 | 4 | Magic `GAF1`. |
| 4 | 1 | Version, currently `1`. Unsupported values close the connection. |
| 5 | 1 | Opcode. |
| 6 | 2 | Flags: `0` request, `1` response; other bits are rejected. |
| 8 | 8 | Request ID. Starts at one and increases per connection. Responses echo it. |
| 16 | 8 | Body length, checked against opcode/request and caller response bounds before body allocation. |

Response IDs and opcodes must match the outstanding request. IDs are correlation fields, not authentication or cross-connection replay protection. Unknown types, nonzero reserved flags, impossible lengths and truncated frames fail; this prototype closes the connection rather than negotiating another version or retrying automatically.

TCP supplies an ordered byte stream, so the reader explicitly accumulates complete bounded headers/bodies and rejects EOF in the middle. Short reads are tested independently. The implementation uses `recv_into`/`sendall`; no assumption about packet boundaries enters the codec. [TCP concepts](https://www.rfc-editor.org/rfc/rfc9293.html#section-2.2), [Python socket receive/send behavior](https://docs.python.org/3.14/library/socket.html#socket.socket.recv_into).

## Operations

| Opcode | Request body |
| ---: | --- |
| 1: manifest | Algorithm byte `1` (SHA-256), followed by 32 digest bytes. |
| 2: blob | The same algorithm/digest fields. |
| 3: range | Algorithm/digest fields plus 64-bit inclusive start/end offsets. |
| 4: selected batch | Shared versioned batch request described below. |
| 240/241 | Empty body for harness-only metric reset/read; excluded from fetch timing/counts. |

Range requests bind the selected immutable representation digest. A server can return a complete representation instead; the client checks the bounded full-pack response before extracting requested objects. Range responses remain independently verified against each requested blob's descriptor. No HTTP URI text, header names or ASCII digest encoding is transmitted in binary resource requests.

Each response body starts with a 50-byte descriptor: status byte, algorithm byte, 32 digest bytes, 64-bit complete-representation size and 64-bit start offset. Status values are `0` complete, `1` partial, `2` missing, `3` precondition failure, `4` unsatisfied range and `5` bad request. The adapter maps those into the existing fetch validator internally; HTTP status text is not on the binary wire. Resource responses require algorithm `1`; harness controls use `0` and a zero digest. Batch envelopes use algorithm `1` with zero aggregate digest because their individual records carry the logical identities.

The payload length follows from the enclosing frame length. Geometry, caller limits, algorithm and complete/partial status are checked before accepting payload bytes. A complete response must have offset zero and match its declared representation size. A successful resource response's digest still needs to match the caller's trusted descriptor; the frame does not replace content verification.

## Shared selected-object batch

The 16-byte batch header contains eight magic/version bytes (`GABREQ01` or `GABRES01`), algorithm byte `1`, zero flags, two zero reserved bytes and a 32-bit record count. This body works unchanged over HTTP and the binary opcode.

A request appends 32-byte object digests in caller order. Duplicate IDs, zero/oversized request counts, unsupported algorithms/versions and trailing bytes are rejected. A response appends each requested digest, a 64-bit byte length and the corresponding bytes in that same order. The client checks every record against the requested digest and expected size; unrequested, duplicate, reordered, truncated or oversized records fail. Every payload is independently hashed before local publication.

There is one batch response for the selected set, with at most 16,384 objects and 64 MiB of raw payload. This is whole-body buffering, not progressive streaming or per-record retry. A malformed response can fail after earlier records have been individually verified/published, but no completed-set receipt is published until the entire requested set succeeds. Existing complete verified objects can be reused on the next attempt.

## Bounds and recovery

Resource requests are exactly 33 bytes, or 49 for ranges, and harness controls are empty. Batch requests are at most 524,304 bytes. A response frame body is at most 67,764,290 bytes, including batch record overhead and its 50-byte descriptor; caller-specific limits can reject it much earlier. Manifests retain the 4 MiB limit, blobs/packs 64 MiB. These are research limits, not public protocol requirements.

The binary server admits at most 33 concurrent connections: up to 32 configured payload workers plus one metadata connection. Sockets have a ten-second timeout. Buffers can be copied, and per-frame/connection limits are not a strict process RSS quota. Global in-flight byte budgets, fairness, idle eviction and longer-running memory behavior remain open.

Corrupt/truncated payloads, wrong response identity/version/type/geometry, unsupported algorithms and oversized lengths are correctness tests. A failed operation removes its previous ready marker and publishes no new one; earlier verified blobs remain usable. Byte-level resume, automatic reconnect/retry, uploads and concurrent cache writers are not implemented. No credentials, trust roots or publisher identity are added by binary framing.

The [framing report](../../experiments/artifacts/results/framing/REPORT.md) records the measured comparisons; [artifact prospects](../../research/artifacts/prospects.md) retain unanswered production questions.


## Bounded-buffer implementation control

The optional `binary-buffered` implementation retains the exact GAF1 version and wire layout. It uses a 64 KiB buffered reader per connection and returns owned result bytes, avoiding the original full-body bytearray-to-bytes copy. Frame/caller bounds are validated before requesting a body-sized result; the fixed 64 KiB reader can read ahead across field boundaries. A vectored prefix/payload send handles partial writes; platforms without vectored sends keep the sequential fallback. Partial-write, zero-progress and owned-result-lifetime tests accompany the existing error/recovery suite.

The [bounded-buffer report](../../experiments/artifacts/results/buffered/REPORT.md) separates its allocation/call-count effects from complete latency. The traced cold mixed receiver peak falls from roughly 7.6 to 4.1 MiB, but bulk latency remains variable against batched HTTP. Local publication is shared work: a complete cold fetch still publishes metadata, 128 individual object files and a receipt. No shared pack/index storage optimization is implemented or credited to framing.
