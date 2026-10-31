# Binary framing versus HTTP with matched transfer plans

Run `20261030T234421.715464Z`; complete; 7 randomized blocks per case.

Both transports use the exact same trusted JSON manifest, object digests, selected sets, cache seeds, planning, hashing, atomic cache publication and receipt. Only the envelope differs within a matched mode. Selected-batch has the same request/response body over HTTP POST and binary TCP; it is a separate batching experiment, not a benefit attributed to binary framing.

Complete fetch clocks include metadata acquisition/local verification, connection setup/closure, cache verification, transfer, requested-blob verification and publication. Python client/server process startup, source admission, fixture/cache preparation and parent validation are excluded. Injected response delay is an application sleep, not a WAN/TLS/loss/HTTP2 model.

## small; injected response delay 0 ms

| Scenario / mode | HTTP ms | Binary ms | Binary paired wins |
| --- | ---: | ---: | --- |
| metadata-only / objects-serial | 1.14 | 1.01 | 5/7 |
| metadata-only / objects-parallel | 1.25 | 1.00 | 5/7 |
| metadata-only / pack-exact | 1.18 | 1.03 | 5/7 |
| metadata-only / pack-coalesced | 1.23 | 1.01 | 6/7 |
| metadata-only / pack-full | 1.14 | 0.95 | 6/7 |
| metadata-only / selected-batch | 1.13 | 0.94 | 7/7 |
| cold-all / objects-serial | 53.56 | 36.53 | 7/7 |
| cold-all / objects-parallel | 103.96 | 111.69 | 0/7 |
| cold-all / pack-exact | 58.04 | 40.41 | 7/7 |
| cold-all / pack-coalesced | 9.49 | 8.91 | 6/7 |
| cold-all / pack-full | 9.38 | 9.08 | 7/7 |
| cold-all / selected-batch | 9.55 | 9.30 | 5/7 |
| cached-all / objects-serial | 2.41 | 2.42 | 3/7 |
| cached-all / objects-parallel | 2.46 | 2.41 | 5/7 |
| cached-all / pack-exact | 2.39 | 2.26 | 5/7 |
| cached-all / pack-coalesced | 2.37 | 2.38 | 4/7 |
| cached-all / pack-full | 2.31 | 2.46 | 1/7 |
| cached-all / selected-batch | 2.36 | 2.36 | 3/7 |
| cached-90 / objects-serial | 8.01 | 6.29 | 7/7 |
| cached-90 / objects-parallel | 16.78 | 17.14 | 0/7 |
| cached-90 / pack-exact | 8.21 | 6.48 | 7/7 |
| cached-90 / pack-coalesced | 4.24 | 4.32 | 2/7 |
| cached-90 / pack-full | 4.21 | 4.07 | 6/7 |
| cached-90 / selected-batch | 4.32 | 3.57 | 6/7 |
| sparse-10 / objects-serial | 6.12 | 4.36 | 7/7 |
| sparse-10 / objects-parallel | 15.52 | 16.09 | 1/7 |
| sparse-10 / pack-exact | 6.31 | 4.62 | 7/7 |
| sparse-10 / pack-coalesced | 2.96 | 2.58 | 6/7 |
| sparse-10 / pack-full | 2.69 | 2.30 | 6/7 |
| sparse-10 / selected-batch | 2.30 | 2.05 | 5/7 |
| one-missing / objects-serial | 3.21 | 3.17 | 3/7 |
| one-missing / objects-parallel | 3.92 | 3.66 | 4/7 |
| one-missing / pack-exact | 3.23 | 2.97 | 6/7 |
| one-missing / pack-coalesced | 3.35 | 3.13 | 4/7 |
| one-missing / pack-full | 3.86 | 3.90 | 5/7 |
| one-missing / selected-batch | 3.68 | 3.03 | 6/7 |

## small; injected response delay 2 ms

| Scenario / mode | HTTP ms | Binary ms | Binary paired wins |
| --- | ---: | ---: | --- |
| metadata-only / objects-serial | 3.97 | 3.34 | 6/7 |
| metadata-only / objects-parallel | 3.22 | 3.12 | 4/7 |
| metadata-only / pack-exact | 3.58 | 3.17 | 6/7 |
| metadata-only / pack-coalesced | 3.28 | 3.22 | 5/7 |
| metadata-only / pack-full | 3.68 | 3.32 | 5/7 |
| metadata-only / selected-batch | 3.67 | 3.53 | 4/7 |
| cold-all / objects-serial | 351.70 | 329.30 | 7/7 |
| cold-all / objects-parallel | 106.52 | 117.11 | 0/7 |
| cold-all / pack-exact | 357.96 | 330.73 | 7/7 |
| cold-all / pack-coalesced | 14.13 | 13.37 | 6/7 |
| cold-all / pack-full | 13.90 | 14.29 | 3/7 |
| cold-all / selected-batch | 13.86 | 14.06 | 3/7 |
| cached-all / objects-serial | 2.56 | 2.58 | 4/7 |
| cached-all / objects-parallel | 2.32 | 2.53 | 3/7 |
| cached-all / pack-exact | 2.39 | 2.51 | 3/7 |
| cached-all / pack-coalesced | 2.39 | 2.51 | 2/7 |
| cached-all / pack-full | 2.42 | 2.42 | 2/7 |
| cached-all / selected-batch | 2.38 | 2.43 | 3/7 |
| cached-90 / objects-serial | 37.90 | 35.60 | 6/7 |
| cached-90 / objects-parallel | 16.85 | 16.59 | 4/7 |
| cached-90 / pack-exact | 38.06 | 35.60 | 6/7 |
| cached-90 / pack-coalesced | 9.28 | 9.40 | 2/7 |
| cached-90 / pack-full | 6.79 | 7.17 | 2/7 |
| cached-90 / selected-batch | 6.78 | 6.60 | 5/7 |
| sparse-10 / objects-serial | 35.76 | 33.46 | 7/7 |
| sparse-10 / objects-parallel | 17.76 | 17.79 | 3/7 |
| sparse-10 / pack-exact | 36.49 | 34.27 | 7/7 |
| sparse-10 / pack-coalesced | 12.44 | 12.00 | 4/7 |
| sparse-10 / pack-full | 8.04 | 6.87 | 6/7 |
| sparse-10 / selected-batch | 7.27 | 7.06 | 5/7 |
| one-missing / objects-serial | 5.54 | 5.34 | 4/7 |
| one-missing / objects-parallel | 6.22 | 6.23 | 3/7 |
| one-missing / pack-exact | 5.61 | 5.29 | 7/7 |
| one-missing / pack-coalesced | 5.66 | 5.73 | 3/7 |
| one-missing / pack-full | 6.38 | 6.09 | 6/7 |
| one-missing / selected-batch | 5.81 | 5.25 | 4/7 |

## mixed; injected response delay 0 ms

| Scenario / mode | HTTP ms | Binary ms | Binary paired wins |
| --- | ---: | ---: | --- |
| metadata-only / objects-serial | 1.23 | 0.95 | 4/7 |
| metadata-only / objects-parallel | 1.16 | 1.05 | 6/7 |
| metadata-only / pack-exact | 1.08 | 1.13 | 3/7 |
| metadata-only / pack-coalesced | 1.10 | 0.93 | 5/7 |
| metadata-only / pack-full | 1.24 | 1.06 | 6/7 |
| metadata-only / selected-batch | 1.34 | 0.96 | 5/7 |
| cold-all / objects-serial | 52.38 | 37.90 | 7/7 |
| cold-all / objects-parallel | 96.10 | 104.63 | 1/7 |
| cold-all / pack-exact | 56.30 | 40.23 | 7/7 |
| cold-all / pack-coalesced | 12.64 | 13.30 | 3/7 |
| cold-all / pack-full | 14.33 | 14.16 | 4/7 |
| cold-all / selected-batch | 13.55 | 13.24 | 5/7 |
| cached-all / objects-serial | 4.58 | 4.14 | 6/7 |
| cached-all / objects-parallel | 4.18 | 4.30 | 3/7 |
| cached-all / pack-exact | 4.23 | 4.24 | 3/7 |
| cached-all / pack-coalesced | 4.04 | 4.09 | 2/7 |
| cached-all / pack-full | 4.29 | 4.31 | 5/7 |
| cached-all / selected-batch | 4.55 | 4.14 | 5/7 |
| cached-90 / objects-serial | 9.58 | 8.19 | 7/7 |
| cached-90 / objects-parallel | 17.74 | 18.90 | 1/7 |
| cached-90 / pack-exact | 10.11 | 8.73 | 7/7 |
| cached-90 / pack-coalesced | 9.62 | 8.17 | 6/7 |
| cached-90 / pack-full | 8.80 | 9.05 | 4/7 |
| cached-90 / selected-batch | 6.41 | 6.15 | 6/7 |
| sparse-10 / objects-serial | 7.22 | 4.52 | 7/7 |
| sparse-10 / objects-parallel | 14.82 | 14.76 | 2/7 |
| sparse-10 / pack-exact | 6.60 | 4.73 | 7/7 |
| sparse-10 / pack-coalesced | 6.36 | 4.50 | 7/7 |
| sparse-10 / pack-full | 5.36 | 5.68 | 2/7 |
| sparse-10 / selected-batch | 3.03 | 2.53 | 7/7 |
| one-missing / objects-serial | 5.36 | 5.27 | 4/7 |
| one-missing / objects-parallel | 5.91 | 5.87 | 4/7 |
| one-missing / pack-exact | 5.54 | 5.14 | 4/7 |
| one-missing / pack-coalesced | 5.50 | 4.95 | 4/7 |
| one-missing / pack-full | 8.09 | 8.26 | 3/7 |
| one-missing / selected-batch | 5.70 | 5.15 | 4/7 |

## mixed; injected response delay 2 ms

| Scenario / mode | HTTP ms | Binary ms | Binary paired wins |
| --- | ---: | ---: | --- |
| metadata-only / objects-serial | 3.32 | 3.80 | 2/7 |
| metadata-only / objects-parallel | 3.66 | 3.42 | 4/7 |
| metadata-only / pack-exact | 3.61 | 3.40 | 6/7 |
| metadata-only / pack-coalesced | 3.71 | 3.25 | 5/7 |
| metadata-only / pack-full | 3.56 | 3.20 | 5/7 |
| metadata-only / selected-batch | 3.69 | 3.18 | 5/7 |
| cold-all / objects-serial | 359.34 | 332.29 | 7/7 |
| cold-all / objects-parallel | 110.28 | 118.10 | 0/7 |
| cold-all / pack-exact | 369.58 | 339.41 | 7/7 |
| cold-all / pack-coalesced | 18.02 | 18.09 | 2/7 |
| cold-all / pack-full | 19.55 | 20.58 | 1/7 |
| cold-all / selected-batch | 19.71 | 19.00 | 5/7 |
| cached-all / objects-serial | 4.62 | 4.62 | 3/7 |
| cached-all / objects-parallel | 4.52 | 4.63 | 3/7 |
| cached-all / pack-exact | 4.75 | 4.54 | 6/7 |
| cached-all / pack-coalesced | 4.61 | 4.62 | 3/7 |
| cached-all / pack-full | 4.56 | 4.71 | 2/7 |
| cached-all / selected-batch | 4.62 | 4.61 | 3/7 |
| cached-90 / objects-serial | 39.97 | 37.93 | 7/7 |
| cached-90 / objects-parallel | 19.68 | 19.35 | 5/7 |
| cached-90 / pack-exact | 41.52 | 38.66 | 7/7 |
| cached-90 / pack-coalesced | 39.22 | 36.95 | 7/7 |
| cached-90 / pack-full | 12.37 | 11.89 | 4/7 |
| cached-90 / selected-batch | 8.78 | 8.78 | 5/7 |
| sparse-10 / objects-serial | 36.65 | 34.33 | 7/7 |
| sparse-10 / objects-parallel | 17.81 | 17.34 | 4/7 |
| sparse-10 / pack-exact | 36.76 | 34.87 | 7/7 |
| sparse-10 / pack-coalesced | 31.80 | 29.89 | 5/7 |
| sparse-10 / pack-full | 10.85 | 10.32 | 4/7 |
| sparse-10 / selected-batch | 7.94 | 7.27 | 5/7 |
| one-missing / objects-serial | 8.16 | 7.63 | 7/7 |
| one-missing / objects-parallel | 8.61 | 8.28 | 6/7 |
| one-missing / pack-exact | 8.04 | 7.87 | 3/7 |
| one-missing / pack-coalesced | 7.64 | 7.76 | 3/7 |
| one-missing / pack-full | 11.25 | 11.20 | 4/7 |
| one-missing / selected-batch | 7.88 | 7.61 | 5/7 |

[Summary](summary.json) retains counters and paired comparisons; [validation](validation.json) binds ignored raw observations.

## What binary framing changes

The binary envelope reduces repeated per-operation work in the chatty cases, while the benefit becomes small or inconsistent once HTTP already transfers useful batches. All comparisons below use controls remeasured in this run; earlier absolute timings are not substituted.

| Matched loopback operation | HTTP | Binary | Binary paired wins |
| --- | ---: | ---: | ---: |
| Cold small, serial blobs (129 operations) | 53.56 ms | 36.53 ms | 7/7 |
| Cold mixed, serial blobs (129 operations) | 52.38 ms | 37.90 ms | 7/7 |
| Cold small, coalesced pack (2 operations) | 9.49 ms | 8.91 ms | 6/7 |
| Cold mixed, coalesced pack (2 operations) | 12.64 ms | 13.30 ms | 3/7 |
| Cold small, full pack (2 operations) | 9.38 ms | 9.08 ms | 7/7 |
| Cold mixed, full pack (2 operations) | 14.33 ms | 14.16 ms | 4/7 |
| Sparse mixed, selected batch (2 operations) | 3.03 ms | 2.53 ms | 7/7 |

Cold serial retrieval improves by about 32% for the small corpus and 28% for mixed, retaining exactly the same 129 operations and required content bytes. Its paired savings are 14.49 and 13.94 ms respectively. This is evidence for lower repeated envelope/adapter overhead in these implementations, not a request-count reduction. With two-operation bulk transfer the gain is usually a fraction of a millisecond and sometimes reverses. Under the 2 ms injected response delay, mixed cold full-pack HTTP takes 19.55 ms versus binary's 20.58 ms, with only one binary paired win. There is no general binary-over-optimized-HTTP win here.

Both sides run Python, but they use different frontend code paths: standard-library HTTP parsing/headers versus the explicit bounded codec. This is not a pure CPU profile of textual versus binary encoding, and it does not establish the result for a native HTTP implementation. Local file publication, cache reads and hashing are common costs. Fully cached requests have zero network bytes and similar variable timings; sub-millisecond differences on that path are noise, not framing gains.

## Envelope bytes and payload bytes

For cold small serial retrieval, application-level request/envelope/payload bytes fall from 589,840 to 554,876: 34,964 fewer bytes with identical 524,288 payload bytes and 13,689 manifest bytes. Common content is unchanged; repeated envelope bytes account for the difference. With coalesced cold-small retrieval, the total falls only from 538,947 to 538,255 bytes, a 692-byte difference across two operations. The much smaller envelope saving matches the smaller opportunity after batching.

The binary frame header is 24 bytes, followed by a 50-byte response descriptor. A resource request body is 33 bytes, or 49 for a range. Shared selected-batch record overhead is counted separately and identical over both transports. Reported application bytes exclude TCP/IP headers, acknowledgements, retransmissions and TLS. HTTP request envelope counts reconstruct the canonical ASCII headers emitted by this client; response header counts come from the exact generated header buffer. These are application-envelope measurements, not packet captures.

The benchmark asserts equal matched plan IDs and equal operation counts, response body bytes, content bytes, manifest bytes, batch record overhead, digest work, cache reuse and publication for every HTTP/binary pair. Different actual connection/thread scheduling is allowed within the same configured eight-worker budget. Each cold parallel-object fetch may also retain its separate metadata connection until closure.

## Batching selected objects is a separate improvement

Selected-batch sends just the missing requested blobs in one response. Its request and response body format is identical over HTTP POST and binary TCP. It does not rely on pack adjacency or fetch gap bytes, and the complete batch framing is bounded and checked before per-object admission.

| Mixed corpus, 90% cached, 2 ms response delay | Operations | Content transferred | Median |
| --- | ---: | ---: | ---: |
| HTTP coalesced ranges | 12 | 450,560 bytes | 39.22 ms |
| Binary coalesced ranges | 12 | 450,560 bytes | 36.95 ms |
| HTTP selected batch | 1 | 450,560 bytes | 8.78 ms |
| Binary selected batch | 1 | 450,560 bytes | 8.78 ms |
| HTTP full pack | 1 | 3,932,160 bytes | 12.36 ms |
| Binary full pack | 1 | 3,932,160 bytes | 11.89 ms |

The selected-batch gain over coalesced ranges is primarily a planning/operation-count gain available on either envelope. Full pack sends 8.7 times the missing bytes; selected-batch avoids that amplification. Its framing overhead is explicit: 16 response header bytes plus 40 bytes per returned object, and 16 request header bytes plus 32 bytes per requested identity. The 13-object case carries 536 response-record bytes and 432 request-body bytes, beyond the raw content. That overhead is identical over HTTP and binary.

For mixed sparse-10 loopback retrieval, HTTP coalesced ranges take 6.36 ms across 11 operations and transfer 610,304 bytes, versus HTTP selected-batch at 3.03 ms across two operations and 544,768 content bytes. Binary selected-batch is 2.53 ms. Both the batching improvement and the smaller matched-envelope improvement are visible; crediting the entire change to binary framing would conflate them.

One-missing-4-KiB cases need one payload operation in every mode. Framing differences are small and variable, while full-pack mode still transfers 512 KiB or 3.75 MiB. Metadata-only remains a separate verified manifest fetch, and fully pinned cached operation remains offline on both transports.

## Protocol and correctness boundaries

All 2,016 timed fetches pass independent local byte/receipt validation, comprising 176,064 requested-object checks. Server counters agree with client counts, and every matched HTTP/binary pair has identical plan/work fields. All 25 [correctness tests](correctness-tests.txt) pass, including the inherited HTTP/transfer contracts on binary, short reads, a fixed independent header vector, malformed request versions/types/flags/lengths/algorithms, duplicate request IDs, wrong response IDs/opcodes/versions, oversized lengths rejected before body reads, truncation, corrupt payloads, record identity/size mismatch, bounded ignored-range fallback, offline reuse and verified-object recovery after failure.

The experimental [binary format](../../../../components/artifact-host/binary-framing.md) explicitly versions headers and batch bodies, validates request correlation and rejects unsupported algorithms. SHA-256 descriptors, JSON metadata, logical blob identities and publication behavior remain unchanged. A range response proves requested blob digests only, not the whole pack or unrequested gap bytes. Full-pack mode additionally checks the pack digest.

The protocol has one outstanding request per connection and bounded parallel connections, not multiplexed streams. It buffers bounded whole responses and may copy buffers; frame limits are not a global RSS quota. A socket timeout is not a demonstrated whole-operation deadline. Malformed/framing errors close the connection; automatic retry, partial-byte resumption, uploads, flow-control negotiation, cancellation, TLS, remote authorization and production diagnostics are not implemented. Harness-only metric controls are not proposed public service operations.

The server stores admitted immutable memory. Fixture generation, initial content admission, server/client process startup, cache seeding and parent verification are excluded. Complete measured requests include connection setup/closure, manifest acquisition or local verification, local content validation, transfer, digest checks, atomic object/receipt publication and parser/codec work. Atomic rename does not include fsync/power-loss durability. The 2 ms sleep is per application response; it supplies no WAN, packet-loss, bandwidth, TLS or HTTP/2/3 evidence.

## Implication

A simple versioned binary interface remains worth testing natively, particularly for a local tool/service boundary with many small operations. The data also say to preserve batching semantics first: an already-batched HTTP control is close on bulk fetches, while selected-object batching improves sparse cases on either transport. This experiment does not select a public protocol or justify discarding HTTP interoperability. A native Odin comparison should retain identical semantics, full publication timing and the malformed-input/recovery suite, and compare against a competent native HTTP implementation.

[Reproduction](../../README.md#binary-framing-with-matched-plans), [format and bounds](../../../../components/artifact-host/binary-framing.md), [human findings](../../../../research/artifacts/findings.md), [next questions](../../../../research/artifacts/prospects.md).
