# Batching beats the first adaptive window in the matched delivery test

Actual TCP loopback servers expose persistent HTTP/1.1 POST batches and persistent binary frames. Both accept the same bounded binary hash-list request and return the same object records; every requested body is SHA-256 verified. HTTP server TCP_NODELAY is enabled before the frozen primary matrix, avoiding the weak Nagle/delayed-ACK smoke baseline. There are 48 real package blobs, 298,609 payload bytes in total. Endpoint data/manifest preparation and listener lifetime are separate from client-operation timing.

Three shuffled blocks compare five policies across two transports and four application-service profiles, giving 120 complete operations/5,760 verified blobs. The latency/bandwidth profiles delay server application service and share one modeled byte-service bottleneck. They are not packet-level WAN, RTT or physical-device emulation. HTTP/2, TLS, authorization and native endpoint implementations are not measured.

| Mode under modeled 5 ms request service latency | HTTP complete | Binary complete |
| --- | ---: | ---: |
| Sequential single objects | 355.56 ms | 305.13 ms |
| Four concurrent single objects | 109.17 ms | 86.78 ms |
| Four concurrent batches of four | 37.39 ms | 29.78 ms |
| Eight concurrent batches of four | 40.95 ms | 34.36 ms |
| Damped feedback, batches of four | 67.01 ms | 60.38 ms |

The feedback controller begins at one request and adjusts by one every four completions using a latency EMA. It does not beat the competent fixed batch policy. More width is not automatically better. These matched prototype observations do not establish intrinsic superiority of binary framing; per-request Python/HTTP parsing and application scheduling remain part of the operation.

First useful verified batch and complete readiness are separate: latency-profile HTTP batch first-use is 13.53 ms versus 9.93 ms sequentially. The generic consumer aggregates verified blobs and does not execute Django during delivery. Batches are buffered until complete, so this is not single-connection multiplexing or demonstrated application/transfer overlap.

Client connection setup, verification, executor shutdown and normal close are charged. The 4 MiB in-flight payload gate has zero overshoots, but the total selected payload is only 0.3 MB, so this matrix does not stress that admission limit or establish process-memory bounds. Received outputs remain retained for correctness; server queue waits and body-byte counts are recorded separately. First-use and throughput objectives can disagree.

All operations return identical content aggregates. Framing, truncation/corruption and impossible-batch-before-network rejection are covered by unit tests. [Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), [reproduce](../../README.md).
