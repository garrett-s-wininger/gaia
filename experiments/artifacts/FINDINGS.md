# Artifact transfer experiment notes

For current conclusions and practical limits, start with the [research review](../../research/artifacts/findings.md). These notes retain the detailed experiment comparisons; measured reports remain under `results/`.

The first [HTTP baseline](results/initial/REPORT.md) compares complete immutable fetches, including metadata verification and local publication. Coalescing cold retrieval changes 129 requests into two and improves medians from 53.96 to 9.60 ms for 128 small blobs, or 50.80 to 13.14 ms for a 3.75 MiB mixed set. Keeping one exact range request per packed object retains the request amplification and provides no comparable win.

Sparse reuse prevents a universal pack policy. The fixed coalescer can overfetch 7.2× missing bytes on the small set and barely reduce request count on mixed data. Full pack can win time under injected response delay by transferring 8.7× missing bytes; no bandwidth limit is modeled. A one-missing-4-KiB-object case favors precise access. Metadata-only requests fetch no payload, and pinned fully cached requests issue zero HTTP operations.

All 840 timed fetches pass independent byte/receipt checks (73,360 requested-object checks), client/server counter checks and expected cache reuse/publication counts. Eleven correctness tests include integrity failures, validators, geometry, ignored-Range fallback, cache repair, offline reuse and interrupted-object recovery. The [summary](results/initial/summary.json) retains paired comparisons and counters; [validation](results/initial/validation.json) binds ignored raw observations.

This is a Python standard-library HTTP/1.1 loopback baseline with a resident memory-backed server and a common per-blob local file cache. The 2 ms delay is an application-response sleep, not WAN/TLS/HTTP2 evidence. It does not choose a public wire standard, universal digest, production storage layout or native transport. See [human findings](../../research/artifacts/findings.md), [prospects](../../research/artifacts/prospects.md) and [research design](../../components/artifact-host/transfer-research.md).


## Matched binary framing

The [framing comparison](results/framing/REPORT.md) holds plans, operation counts, manifest/content bytes, hash work and local publication constant. Cold serial small fetches improve from HTTP 53.56 to binary 36.53 ms across 129 operations; mixed improves 52.38 to 37.90 ms, both 7/7 paired wins. Already-batched coalesced/full-pack differences are small or inconsistent (mixed coalesced 12.64 versus 13.30 ms). Both transports retain JSON metadata and explicit SHA-256 identities.

Selected-object batching is a separate gain: mixed 90%-cached data with injected delay takes 8.78 ms over either HTTP or binary batch, versus coalesced HTTP at 39.22 ms, transferring the exact 450,560 missing content bytes. Its body format and record overhead are identical across envelopes. All 2,016 fetches/176,064 object checks and 25 tests pass, including malformed frames, wrong response IDs, allocation bounds, truncation and the inherited transfer/cache/recovery contracts. This is a private Python TCP framing experiment, not a production protocol or a native HTTP comparison.


## Bounded binary buffering

The [buffering comparison](results/buffered/REPORT.md) retains plans, wire lengths, digest work and publication while removing a full-body receiver copy through a bounded 64 KiB buffered reader and vectored sends. Traced cold-mixed receiver peaks fall from about 7.6 to 4.1 MiB. Complete cold coalesced/full-pack latency remains noisy against batched HTTP; some mixed partial coalesced cases win 7/7 against HTTP and 6/7 against original binary. This is an allocation win with selective latency gains, not a universal framing win.

All 1,512 fetches/132,048 object checks and 39 correctness tests pass. The separate intrusive profile records 130 atomic publications in every cold complete fetch, with that common function work prominent versus hashing. A local pack/index store would be a shared storage/admission control, not an improvement to credit to the binary envelope. [Compact diagnostics](results/buffered/allocation-profile.json) retain receiver peaks and socket-call observations; traced timings are not benchmark medians.


## Verified local pack/index admission

The [local-cache comparison](results/admission/REPORT.md) includes acquisition and a fresh verified logical-view reopen on both HTTP and buffered binary. Small cold coalesced files/packed medians are HTTP 9.90/4.22 ms and binary 10.44/3.67 ms; mixed is about 16/11 ms. These cases win 7/7 paired blocks. Cold publications fall 130→5; cached successful data opens 256→2, with identical logical verification and explicit extra pack/index hashes. Valid fully cached requests remain offline.

Ordinary-file materialization is separate and combined: mixed HTTP cold files/packed totals become 15.94/16.99 ms, and cached 8.06/11.88 ms. The result favors direct logical-byte consumers and is not a universal legacy-CLI or framing gain. All 1,344 operations/117,376 requested-object checks and 49 tests pass, including corruption, future-version preservation, owned views, partial admission, publication rollback, bounded compaction/quota behavior and leases. The [format/access design](../../components/artifact-host/local-cache-research.md) records transaction and durability limits.
