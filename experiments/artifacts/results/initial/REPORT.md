# Artifact-transfer amplification: first baseline

Run `20261030T231703.682942Z`; complete; 7 randomized blocks per case.

Generated immutable bytes, separate manifest acquisition, a resident Python HTTP/1.1 server in another process, new client connections per fetch. Both sides disable Nagle. Complete request timing includes manifest lookup/verification, existing-cache verification, payload retrieval, requested-blob hashing, atomic cache publication, receipt publication and connection closure. Fixture generation, cache seeding and independent validation occur outside timing. Atomic publication does not include fsync or power-loss durability.

The delay field is an injected sleep before each server response. It is an application-delay model, not WAN RTT, packet loss, congestion, TLS, HTTP/2 or HTTP/3 evidence. A zero-delay run still uses loopback sockets and the Python implementation.

## small; injected response delay 0 ms

| Scenario | objects-serial | objects-parallel | pack-exact | pack-coalesced | pack-full |
| --- | ---: | ---: | ---: | ---: | ---: |
| metadata-only | 1.12 ms | 1.19 ms | 1.13 ms | 1.14 ms | 1.38 ms |
| cold-all | 53.96 ms | 102.22 ms | 55.48 ms | 9.60 ms | 10.78 ms |
| cached-all | 2.32 ms | 2.85 ms | 2.53 ms | 2.54 ms | 2.60 ms |
| cached-90 | 8.00 ms | 17.07 ms | 8.18 ms | 4.18 ms | 4.95 ms |
| sparse-10 | 5.90 ms | 14.82 ms | 6.43 ms | 3.00 ms | 2.77 ms |
| one-missing | 3.26 ms | 3.98 ms | 3.74 ms | 3.51 ms | 3.81 ms |

## small; injected response delay 2 ms

| Scenario | objects-serial | objects-parallel | pack-exact | pack-coalesced | pack-full |
| --- | ---: | ---: | ---: | ---: | ---: |
| metadata-only | 3.48 ms | 3.45 ms | 3.89 ms | 3.76 ms | 3.60 ms |
| cold-all | 351.92 ms | 107.02 ms | 365.41 ms | 14.79 ms | 15.30 ms |
| cached-all | 2.60 ms | 2.91 ms | 2.40 ms | 2.72 ms | 2.46 ms |
| cached-90 | 37.59 ms | 17.24 ms | 37.55 ms | 9.23 ms | 7.61 ms |
| sparse-10 | 35.55 ms | 17.30 ms | 36.45 ms | 13.55 ms | 8.04 ms |
| one-missing | 5.79 ms | 6.56 ms | 5.86 ms | 5.80 ms | 6.60 ms |

## mixed; injected response delay 0 ms

| Scenario | objects-serial | objects-parallel | pack-exact | pack-coalesced | pack-full |
| --- | ---: | ---: | ---: | ---: | ---: |
| metadata-only | 1.13 ms | 1.04 ms | 1.29 ms | 1.12 ms | 1.38 ms |
| cold-all | 50.80 ms | 92.98 ms | 53.27 ms | 13.14 ms | 15.21 ms |
| cached-all | 4.16 ms | 4.39 ms | 4.11 ms | 4.28 ms | 4.24 ms |
| cached-90 | 9.82 ms | 17.25 ms | 9.97 ms | 9.96 ms | 8.39 ms |
| sparse-10 | 5.99 ms | 14.33 ms | 6.29 ms | 6.52 ms | 5.41 ms |
| one-missing | 5.48 ms | 6.20 ms | 5.49 ms | 5.26 ms | 7.66 ms |

## mixed; injected response delay 2 ms

| Scenario | objects-serial | objects-parallel | pack-exact | pack-coalesced | pack-full |
| --- | ---: | ---: | ---: | ---: | ---: |
| metadata-only | 3.43 ms | 3.80 ms | 3.33 ms | 3.53 ms | 3.42 ms |
| cold-all | 373.79 ms | 97.33 ms | 367.87 ms | 19.58 ms | 20.16 ms |
| cached-all | 4.62 ms | 4.63 ms | 4.64 ms | 4.53 ms | 4.84 ms |
| cached-90 | 41.44 ms | 18.74 ms | 40.79 ms | 38.56 ms | 11.13 ms |
| sparse-10 | 35.68 ms | 17.42 ms | 35.38 ms | 31.56 ms | 12.04 ms |
| one-missing | 7.73 ms | 8.29 ms | 8.48 ms | 8.28 ms | 11.32 ms |

Full raw samples remain ignored in `results.json`. Compact counters/paired comparisons are in [summary.json](summary.json); independent validation and raw identity are in [validation.json](validation.json).

## Interpretation

The useful first result is request amplification. Fetching all 128 blobs takes 129 requests when metadata is cold: one manifest plus 128 object GETs. Merely placing those blobs in a pack but still sending one exact range request per blob retains all 129 operations and similar latency. Coalescing cold contiguous regions reduces that to two requests with identical required payload bytes.

| Cold complete fetch | Serial blobs | Exact pack ranges | Coalesced pack | Full pack |
| --- | ---: | ---: | ---: | ---: |
| 512 KiB small corpus, loopback | 53.96 ms | 55.48 ms | 9.60 ms | 10.78 ms |
| 3.75 MiB mixed corpus, loopback | 50.80 ms | 53.27 ms | 13.14 ms | 15.21 ms |
| Small, 2 ms injected response delay | 351.92 ms | 365.41 ms | 14.79 ms | 15.30 ms |
| Mixed, 2 ms injected response delay | 373.79 ms | 367.87 ms | 19.58 ms | 20.16 ms |

Coalesced fetch wins all seven paired cold-fetch blocks against both serial objects and exact ranges in each corpus/delay case. The loopback improvement is about 5.6× for small blobs and 3.9× for the mixed corpus. These are complete fetches, including manifest verification, object verification and local cache publication, not socket-only throughput. The small/coalesced loopback median includes roughly 1.06 ms for metadata, 1.52 ms checking local cache membership and 6.77 ms transferring/verifying/publishing 128 blobs. Local publication and Python machinery remain significant.

Parallel object GETs illustrate an implementation limit, not a transport law. Eight-way requests reduce the delayed cold cases to about 97–107 ms but take about 93–102 ms on plain loopback, slower than serial. The measured baseline includes Python client/server thread management, executor setup, filesystem publication and fresh per-operation connections. This is not evidence that native concurrency or HTTP/2 multiplexing is intrinsically slow.

## Sparse reuse changes the choice

A fixed coalescing heuristic is not a universal policy. For the small corpus with 90% of objects cached, it reduces 13 requests to two but fetches 385,024 bytes for only 53,248 missing bytes: 7.2× payload amplification. In the mixed corpus it reduces 13 requests to only 12 and transfers the same 450,560 missing bytes, because the gaps exceed the 64 KiB merge budget. With the 2 ms response delay, that coalesced mixed case takes 38.56 ms versus parallel objects at 18.74 ms and a full pack at 11.13 ms. The full pack wins time here by transferring 3,932,160 bytes, 8.7× the missing payload. No bandwidth limit is modeled, so this does not show that full-pack transfer would win on a constrained link.

When only one 4 KiB object is missing, object and range modes transfer 4 KiB; full pack transfers 512 KiB or 3.75 MiB. In the mixed loopback case, a coalesced one-object fetch takes 5.26 ms versus full pack's 7.66 ms, with all seven paired wins against full pack. In the small corpus the times are close and variable. The planning interface must expose request count, missing bytes and overfetch budgets instead of assuming that the fewest requests or smallest byte count always wins.

## Metadata and offline behavior

Metadata-only requests fetch the separate 13.7–13.9 kB manifest and no pack/blob payload: about 1.0–1.4 ms on loopback, or 3.3–3.9 ms under the 2 ms application delay. The caller supplies the manifest's previously trusted SHA-256 descriptor and size. Fully cached requests revalidate both that manifest and every requested cached blob, publish a receipt and make zero HTTP requests in every mode: roughly 2–3 ms for the small corpus and 4–5 ms for mixed. A correctness test makes connection creation fail if attempted, proving the pinned offline path does not rely on a live server.

SHA-256 is an explicitly tagged baseline provider. This experiment does not select the global Gaia digest or conflate a future BLAKE3 identifier with SHA-256. The private fixture format rejects unsupported algorithms.

## Verification and boundaries

All 840 timed fetches match independently compared requested bytes and completion receipts: 73,360 object checks. Independent server request/payload counters match the client for every observation, as do expected cache reuse and publication counts. All 11 [correctness tests](correctness-tests.txt) pass. They exercise schema/version/algorithm bounds, empty/deduplicated bodies, coalescing, atomic-write failure, all modes, offline cache reuse, corrupt-cache repair, corrupt/truncated transfers, wrong ETag/Content-Range/encoding, ignored-Range bounded full-pack fallback and reuse of earlier verified objects after an interrupted operation.

Every requested object is checked against its own descriptor. Partial/coalesced ranges do not authenticate unrequested pack bytes or establish whole-pack integrity. Full-pack mode additionally hashes the pack. A failed operation never publishes a new completion receipt, while already verified objects can survive and be reused. Recovery is at object boundaries; byte-level resumption, uploads and automatic retry are not implemented.

The server is a resident Python process serving admitted immutable memory, not a production object-store benchmark. Dataset generation, source-file discovery, immutable server admission, cache seeding and parent verification are excluded. The client interpreter is resident too; command startup, DNS, TLS, remote identity/authentication, disk-cache coldness, durability/fsync, packet loss, bandwidth limits, HTTP/2/3, large-object streaming, eviction and concurrent cache writers are not measured. Experimental hard limits are 4 MiB manifests, 64 MiB packs/blobs and 16,384 objects. Payload responses are bounded whole-body buffers.

Native implementations remain Odin work. The next useful tests are a bounded selected-blob batch over an existing transport, an explicit request-versus-overfetch planner, real dependency/compiler artifact sets and interruption/cancellation with byte-level staging. A native port should retain these semantic/correctness controls rather than being justified by the loopback numbers alone.

[Research design](../../../../components/artifact-host/transfer-research.md), [reproduction](../../README.md), [human findings](../../../../research/artifacts/findings.md), [next questions](../../../../research/artifacts/prospects.md).
