# One-connection windowing and missing-list streaming

Run `20261031T012507.804972Z`; complete; 3 blocks.

All paths retain selected SHA-256 identities, verified cache admission, a fresh logical consumer reopen and separately timed file materialization. The readiness delay is independently scheduled once per request on eight server workers. Stream records do not each sleep. This is an application-readiness model, not a WAN RTT or bandwidth simulation.

| Corpus / profile / layout / readiness delay | Serial | Windowed | Buffered list | Streamed list |
| --- | ---: | ---: | ---: | ---: |
| mixed / pinned-established-all / files / 0.0 ms | 51.80 ms | 39.09 ms | 18.13 ms | 17.04 ms |
| mixed / pinned-established-all / packed / 0.0 ms | 39.30 ms | 36.48 ms | 15.57 ms | 10.24 ms |
| mixed / pinned-established-partial / files / 0.0 ms | 13.10 ms | 11.90 ms | 10.00 ms | 9.46 ms |
| mixed / pinned-established-partial / packed / 0.0 ms | 10.06 ms | 10.57 ms | 7.74 ms | 7.87 ms |
| mixed / pinned-fresh-all / files / 0.0 ms | 51.38 ms | 42.01 ms | 17.00 ms | 16.97 ms |
| mixed / pinned-fresh-all / packed / 0.0 ms | 38.25 ms | 36.03 ms | 12.84 ms | 11.05 ms |
| mixed / pinned-established-all / files / 2.0 ms | 342.17 ms | 51.85 ms | 21.50 ms | 18.20 ms |
| mixed / pinned-established-all / packed / 2.0 ms | 323.14 ms | 47.03 ms | 14.64 ms | 12.83 ms |
| mixed / pinned-established-partial / files / 2.0 ms | 43.73 ms | 14.66 ms | 12.87 ms | 11.52 ms |
| mixed / pinned-established-partial / packed / 2.0 ms | 39.46 ms | 12.60 ms | 9.72 ms | 9.52 ms |
| mixed / pinned-fresh-all / files / 2.0 ms | 345.38 ms | 51.13 ms | 23.20 ms | 18.80 ms |
| mixed / pinned-fresh-all / packed / 2.0 ms | 324.17 ms | 47.11 ms | 13.93 ms | 14.29 ms |

[Summary](summary.json) retains first-new-verified readiness, complete/materialized endpoints, counters and paired values. [Validation](validation.json) binds ignored raw evidence.

## What changed and what did not

A known manifest already describes every available SHA-256 object and size. The previous selected batch already sends the complete missing hash list in one request. The new streamed list retains that single application request, but sends one complete validated object record at a time and an explicit terminal record. It does not save another application flight over the existing batch. The other new path pipelines up to eight independent object requests on one TCP connection, with request IDs allowing out-of-order whole-object completions.

All four paths run over the same GAF2 server, with the same worker pool, content, requested hashes, cache layouts and verification/publication code. This isolates serial versus windowed versus buffered-list versus streamed-list behavior. This is not another HTTP-versus-binary comparison: earlier HTTP controls remain in the framing/admission reports. Comparisons against their absolute timings would also change the server implementation and run.

## The useful result

With an established connection, empty payload cache and 2 ms independently scheduled readiness, loose-cache completion falls from **342.17 ms serial to 51.85 ms windowed**, then **21.50 ms buffered list and 18.20 ms streamed list**. The packed equivalents are **323.14 / 47.03 / 14.64 / 12.83 ms**. Windowing overlaps independent waits, while the known-list batch avoids 127 application requests. Streaming beats buffered-list completion in all three paired blocks for these two established/cold cases.

First newly verified in-memory bytes arrive at **3.95 versus 7.42 ms** for streamed/buffered loose storage, and **2.95 versus 6.02 ms** packed. This marker follows digest verification and precedes cache publication; a callback could begin consuming owned read-only bytes. It is not a durability or fresh-store visibility claim. The primary completion endpoint still includes the full receipt and a fresh verified consumer reopen.

Gains shrink when little data is missing. At 90% cached under 2 ms readiness, packed buffered/streamed totals are **9.72/9.52 ms**, with streaming winning only two of three blocks. Newly connected pinned-index packed transfers also reverse: **13.93/14.29 ms**, streaming wins one of three. Three blocks are an initial proof, not a statistical or universal winner. At zero injected readiness, the report table shows the same broad request-amplification ordering but some small partial-cache reversals.

Streaming provides earlier useful bytes and avoids constructing one full batch response on each endpoint. It adds per-record frame work. For 128 objects the buffered response has 74 envelope bytes plus 5,136 batch-body overhead bytes; the streamed response has 9,516 total framing bytes including its terminal record. Both transfer exactly the same 3,932,160 content bytes and issue one payload request. No memory profile was collected in this run; logical consumer views still own the complete requested set after reopening.

## Complete operation and connection boundaries

Each randomized sample restores the same seed outside timing. Timing begins before lease/cache/manifest work, includes all requested hashes, publication, receipt and connection close for fresh clients, and ends after a fresh verified logical consumer reopen. Packed representation hashes remain charged. Ordinary-file materialization is separately measured and retained in both separate and combined totals: for established cold/2 ms, streamed loose/packed combined costs are **18.49/19.72 ms**, despite packed logical completion of **12.83 ms**. Packed materialization is not free.

Established profiles exclude connection establishment and one control-response primer. Their separately observed median connect/primer setup is **0.082/0.440 ms**, not an estimate of a remote TCP handshake. Fresh pinned profiles include TCP connection establishment in the full operation; their manifest root is already pinned locally. The [boundary summary](boundary/summary.json) separately records cold index discovery: one manifest request plus one payload batch on one fresh connection. Complete cold-index buffered/streamed totals are 23.71/22.24 ms loose and 18.22/16.36 ms packed in a single boundary block; do not rank performance from that block. Pinned fully cached controls use zero network requests and zero connections, even with an unavailable endpoint.

The server has eight prestarted workers and schedules the readiness sleep independently once per request. A whole missing-list stream sleeps once, not once per object. Multiple pipelined requests can become ready concurrently. This is an **application-readiness delay model**, not propagation RTT, packet loss, bandwidth, TLS or HTTP/2/3 evidence. It demonstrates one application request/response flight with a known index; a new TCP connection and cold manifest discovery remain additional boundaries.

## Bounds, recovery and evidence

See the [experimental protocol](../../../../components/artifact-host/pipeline-research.md). The client has eight outstanding IDs and a 4 MiB logical in-flight window, permitting one larger object alone up to the existing 64 MiB bound. Responses may complete out of order but a whole object frame holds the connection writer; this is not chunk-interleaved multiplexing. A slow/large frame can block other responses. Each streamed record is verified before admission. END must match the requested count and total bytes. Errors, truncation, cancellation by abandoning an iterator or malformed pending frames dispose the connection; reuse requires a new client. Already admitted verified blobs survive and can be reused during recovery; no successful receipt is emitted for an incomplete request.

All **56 correctness tests**, **144 main operations / 18,432 object checks** and **eight boundary operations / 1,024 checks** pass. The [test log](correctness-tests.txt), [main validation](validation.json), [boundary validation](boundary/validation.json) and [summary](summary.json) retain evidence. Raw observations are ignored local artifacts identified in the evidence manifest; no bulk download is published. The scope is one synthetic mixed-size corpus, one client at a time, Python implementations and loopback. Production cancellation, authentication/TLS, bandwidth fairness, chunk multiplexing, upload, fsync durability and remote scheduling remain unimplemented.
