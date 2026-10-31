# Matched artifact transport implementations

Run `20261031T000330.496972Z`; complete; 7 randomized blocks per case.

All variants retain the trusted JSON manifest, object digests, selected sets, cache seeds, planning, hashing, atomic publication and receipt. The buffered binary variant uses the same versioned frames and wire lengths as the original. No planning or integrity work moves outside the clock.

Complete fetch timing includes connection setup/closure, metadata acquisition/local verification, cached-content verification, transfer, requested-blob verification and publication. Process/server startup, initial source admission, fixture/cache preparation and parent validation are excluded. Injected response delay is an application sleep, not a WAN/TLS/loss/HTTP2 model.

## small; injected response delay 0 ms

| Scenario / mode | http ms | binary ms | binary-buffered ms |
| --- | ---: | ---: | ---: |
| metadata-only / pack-coalesced | 1.10 | 0.90 | 1.02 |
| metadata-only / pack-full | 1.11 | 0.98 | 0.93 |
| metadata-only / selected-batch | 1.07 | 1.02 | 1.09 |
| cold-all / pack-coalesced | 8.34 | 7.75 | 8.02 |
| cold-all / pack-full | 8.09 | 8.50 | 7.81 |
| cold-all / selected-batch | 8.64 | 8.09 | 7.96 |
| cached-all / pack-coalesced | 2.12 | 2.17 | 2.12 |
| cached-all / pack-full | 2.07 | 2.10 | 2.15 |
| cached-all / selected-batch | 2.31 | 2.18 | 2.22 |
| cached-90 / pack-coalesced | 4.36 | 4.09 | 4.21 |
| cached-90 / pack-full | 3.84 | 3.70 | 3.65 |
| cached-90 / selected-batch | 3.95 | 3.54 | 3.30 |
| sparse-10 / pack-coalesced | 2.97 | 2.71 | 2.42 |
| sparse-10 / pack-full | 2.34 | 2.23 | 2.32 |
| sparse-10 / selected-batch | 2.11 | 1.78 | 1.98 |
| one-missing / pack-coalesced | 3.21 | 3.20 | 3.07 |
| one-missing / pack-full | 3.57 | 3.56 | 3.10 |
| one-missing / selected-batch | 3.08 | 3.00 | 3.02 |

## small; injected response delay 2 ms

| Scenario / mode | http ms | binary ms | binary-buffered ms |
| --- | ---: | ---: | ---: |
| metadata-only / pack-coalesced | 3.33 | 3.56 | 3.22 |
| metadata-only / pack-full | 3.49 | 2.96 | 3.27 |
| metadata-only / selected-batch | 3.22 | 3.22 | 3.14 |
| cold-all / pack-coalesced | 11.91 | 13.84 | 13.84 |
| cold-all / pack-full | 12.84 | 12.40 | 13.58 |
| cold-all / selected-batch | 13.62 | 13.30 | 12.98 |
| cached-all / pack-coalesced | 2.19 | 2.05 | 2.11 |
| cached-all / pack-full | 1.98 | 2.04 | 2.23 |
| cached-all / selected-batch | 2.21 | 2.05 | 2.05 |
| cached-90 / pack-coalesced | 8.70 | 8.15 | 8.22 |
| cached-90 / pack-full | 6.15 | 6.25 | 5.82 |
| cached-90 / selected-batch | 5.87 | 5.62 | 5.86 |
| sparse-10 / pack-coalesced | 12.36 | 11.61 | 11.28 |
| sparse-10 / pack-full | 7.08 | 7.05 | 7.02 |
| sparse-10 / selected-batch | 7.10 | 6.87 | 6.25 |
| one-missing / pack-coalesced | 5.35 | 5.27 | 4.89 |
| one-missing / pack-full | 5.60 | 5.80 | 5.77 |
| one-missing / selected-batch | 5.30 | 5.02 | 4.85 |

## mixed; injected response delay 0 ms

| Scenario / mode | http ms | binary ms | binary-buffered ms |
| --- | ---: | ---: | ---: |
| metadata-only / pack-coalesced | 1.08 | 1.17 | 1.18 |
| metadata-only / pack-full | 1.15 | 0.88 | 1.00 |
| metadata-only / selected-batch | 1.21 | 0.97 | 0.96 |
| cold-all / pack-coalesced | 12.08 | 12.19 | 11.61 |
| cold-all / pack-full | 13.22 | 13.51 | 13.49 |
| cold-all / selected-batch | 13.46 | 12.79 | 11.95 |
| cached-all / pack-coalesced | 4.09 | 4.12 | 4.23 |
| cached-all / pack-full | 4.23 | 4.07 | 4.08 |
| cached-all / selected-batch | 4.12 | 4.08 | 4.24 |
| cached-90 / pack-coalesced | 9.55 | 8.36 | 8.07 |
| cached-90 / pack-full | 8.80 | 8.48 | 7.95 |
| cached-90 / selected-batch | 6.03 | 6.20 | 6.25 |
| sparse-10 / pack-coalesced | 6.02 | 4.44 | 4.11 |
| sparse-10 / pack-full | 5.49 | 4.81 | 5.29 |
| sparse-10 / selected-batch | 2.71 | 2.28 | 2.63 |
| one-missing / pack-coalesced | 5.51 | 5.19 | 4.91 |
| one-missing / pack-full | 8.00 | 7.97 | 7.89 |
| one-missing / selected-batch | 5.48 | 5.29 | 4.96 |

## mixed; injected response delay 2 ms

| Scenario / mode | http ms | binary ms | binary-buffered ms |
| --- | ---: | ---: | ---: |
| metadata-only / pack-coalesced | 3.27 | 3.42 | 3.25 |
| metadata-only / pack-full | 3.40 | 3.19 | 3.04 |
| metadata-only / selected-batch | 3.14 | 3.04 | 2.96 |
| cold-all / pack-coalesced | 16.70 | 16.99 | 16.95 |
| cold-all / pack-full | 18.45 | 18.75 | 18.06 |
| cold-all / selected-batch | 17.46 | 17.79 | 16.81 |
| cached-all / pack-coalesced | 4.32 | 4.53 | 4.11 |
| cached-all / pack-full | 4.10 | 4.40 | 4.06 |
| cached-all / selected-batch | 4.12 | 4.05 | 4.17 |
| cached-90 / pack-coalesced | 36.65 | 34.89 | 35.24 |
| cached-90 / pack-full | 10.44 | 11.32 | 11.10 |
| cached-90 / selected-batch | 8.43 | 7.84 | 8.38 |
| sparse-10 / pack-coalesced | 30.99 | 29.49 | 28.87 |
| sparse-10 / pack-full | 9.51 | 10.21 | 9.36 |
| sparse-10 / selected-batch | 7.03 | 7.40 | 7.27 |
| one-missing / pack-coalesced | 7.35 | 7.41 | 7.20 |
| one-missing / pack-full | 9.58 | 9.99 | 9.88 |
| one-missing / selected-batch | 7.68 | 7.19 | 7.03 |

[Summary](summary.json) retains phase clocks, counters and paired comparisons; [validation](validation.json) binds ignored raw observations.

## Concrete waste removed

The original binary reader allocated a bytearray for each body, filled it with `recv_into`, then copied the entire result into a new bytes object. It also performed separate exact reads for the 24-byte header and 50-byte response descriptor. The server sent that prefix and the payload in separate calls.

`binary-buffered` keeps the same GAF1 version, opcodes, descriptors, request IDs and frame/body bounds. A 64 KiB buffered socket reader returns owned bytes directly, avoiding the full-body bytearray-to-bytes copy and allowing small header/descriptor reads to share buffered input. Returned bytes remain valid after subsequent reads. The server sends bounded prefix/payload vectors, with a loop handling partial writes and zero progress; platforms without vectored writes retain the sequential fallback. No payload concatenation is added to create the vector.

This changes implementation only. Request planning, batching, metadata/content bytes, SHA-256 work, cache checks, atomic publication, receipts and full-operation clock boundaries remain matched. Original and buffered binary variants must also have identical request/response framing byte counts. HTTP and the original binary implementation remain controls.

## Allocation and socket-call evidence

A [separate diagnostic](allocation-profile.json) performs one cold mixed fetch per case under tracemalloc, cProfile and client socket wrappers. Its timings are intrusive observations, not the randomized performance medians below.

| Mixed cold mode | HTTP traced peak | Original binary peak | Buffered binary peak | Original/buffered client receive calls |
| --- | ---: | ---: | ---: | ---: |
| Coalesced pack | 4.44 MiB | 7.60 MiB | 4.16 MiB | 31 / 25 |
| Full pack | 4.12 MiB | 7.58 MiB | 4.16 MiB | 50 / 9 |
| Selected batch | 4.03 MiB | 7.60 MiB | 4.06 MiB | 46 / 17 |

Removing the copy reduces the traced receiver peak by about 45–47%, to approximately the HTTP receiver's level. Receive-call counts also fall in these particular observations. Those counts depend on scheduling/arrival shape and tracing overhead; they are not fixed packet counts or a guarantee of one syscall per frame. The server's vectored send path combines prefix and payload without a large concatenation, and partial-send tests verify byte preservation. No server syscall-rate or packet-level throughput conclusion is inferred from the client counters.

The 64 KiB reader budget is per active connection; payload responses are still bounded whole-body buffers. These bounds are not a process RSS quota. The diagnostic tracks parent Python allocations, not child-server/native allocations or total resident memory.

## Complete-operation latency

The complete matched matrix remeasures all controls together. Key cases:

| Operation | HTTP | Original binary | Buffered binary | Buffered wins vs HTTP / original |
| --- | ---: | ---: | ---: | --- |
| Mixed cold coalesced, loopback | 12.08 ms | 12.19 ms | 11.61 ms | 5/7 / 3/7 |
| Mixed cold full pack, loopback | 13.22 ms | 13.51 ms | 13.49 ms | 4/7 / 4/7 |
| Mixed cold full pack, 2 ms response sleep | 18.45 ms | 18.75 ms | 18.06 ms | 4/7 / 6/7 |
| Mixed 90%-cached coalesced, loopback | 9.55 ms | 8.36 ms | 8.07 ms | 7/7 / 6/7 |
| Mixed sparse-10 coalesced, loopback | 6.02 ms | 4.44 ms | 4.11 ms | 7/7 / 6/7 |
| Small cold coalesced, loopback | 8.34 ms | 7.75 ms | 8.02 ms | 4/7 / 2/7 |
| Small cold coalesced, 2 ms response sleep | 11.91 ms | 13.84 ms | 13.84 ms | 1/7 / 4/7 |

The allocation improvement does not become a universal bulk latency win. Mixed cold coalesced medians improve, but the buffered path wins only three paired blocks against the original; the median paired delta is +0.08 ms. Mixed cold full-pack loopback is similarly inconclusive. Independent medians and paired differences are different statistics; the full [summary](summary.json) retains both, rather than selecting favorable median ratios.

Some partial mixed cases show a clearer modest improvement: 90%-cached coalesced fetch saves 0.23 ms paired versus original and 1.72 ms versus HTTP; sparse-10 coalesced saves 0.33 ms versus original and 1.88 ms versus HTTP. Both beat HTTP 7/7 blocks and the original 6/7. Other cases regress or remain variable, including small cold coalesced transfers under the injected delay. This experiment does not support claiming that buffering now beats batched HTTP in every case.

Fully cached requests perform no network operations. Their small differences therefore supply a useful noise/control scale, not evidence for a framing optimization. The injected 2 ms sleep remains an application-response delay model, not WAN, bandwidth, packet-loss, TLS or HTTP/2 evidence.

## Shared publication is prominent

Each cold complete fetch makes 130 atomic publications: one manifest, 128 per-object files and one receipt. That work is identical across all transports. The intrusive diagnostic attributes about 16–18 ms cumulative function time to those writes, compared with roughly 2–4 ms in digest functions. Those profiler times are not uninstrumented latency contributions and must not be added to benchmark medians; the call count and relative concentration identify repeated shared work.

The common metadata, cache-validation, payload-plus-verification/publication and receipt subclocks remain in every sample and compact summary. They intentionally retain verification and publication rather than treating the receiving socket as the completed operation. Removing the receiver copy reduces memory traffic but cannot remove those per-blob filesystem operations.

A single verified local pack/index publication could be a useful next experiment, but it is not implemented here. It would be a shared storage/admission optimization available to HTTP and binary and must be compared on both, with the same logical blob identities, integrity/recovery rules and materialization/access contract. It should not be credited to binary framing or used to move publication outside the clock.

## Separate the three findings

The earlier [framing comparison](../framing/REPORT.md) establishes a repeated-operation envelope/adapter gain on chatty plans. Selected-object batching establishes a separate planning gain available over either envelope. This bounded-buffer experiment establishes lower receiver allocation/copy cost, with only selective, modest complete-fetch latency gains. The three results should not be multiplied or pooled across runs.

No native implementation or lower floor is established. A competent native Odin transport and native HTTP control, or a shared local admission representation, can test remaining overhead without sacrificing the semantic guarantees. The present result is a reason to preserve the useful bounded implementation and honest controls, not to force a universal win from noisy bulk differences.

## Verification and limits

All 1,512 timed fetches and 132,048 independent requested-object checks pass. Every matched three-way group has identical plan IDs, operations, payload/manifest/batch bytes, hash work, reuse and publication. Original/buffered binary wire lengths also match. All 39 [correctness tests](correctness-tests.txt) pass, including existing corruption/truncation/unsupported-frame/recovery contracts, short reads, owned-buffer lifetime, partial vectored writes, zero-progress rejection and sequential fallback. Expected rejected-peer disconnects can produce HTTP server stderr during negative tests; the suite result and artifact checks remain authoritative.

The experiment uses generated small/mixed immutable corpora, warm loopback, resident Python client/server processes, bounded whole-body buffering and a common per-blob file cache. Source/server admission, process startup, cache seeding and parent verification are excluded equally. Full fetches include connection setup/closure, metadata/cache validation, transfer, hashing, atomic local publication and receipts. Atomic visibility is measured without fsync/power-loss durability. Uploads, cancellation, byte-level retry, TLS/authorization, global memory/byte quotas and production interoperability remain open.

[Validation](validation.json) binds ignored raw `results.json`; [allocation diagnostic](allocation-profile.json) retains compact allocation/call evidence and its source pins. [Reproduction](../../README.md#bounded-buffer-and-vectored-write-comparison), [binary wire format](../../../../components/artifact-host/binary-framing.md), [human findings](../../../../research/artifacts/findings.md).
