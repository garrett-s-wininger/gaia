# Digest implementation and algorithm costs in complete builds

Two separate seven-block randomized comparisons use the same Zstandard 1.5.7 C fixture plus a probe, 31 objects and eight compiler workers. Every control within each run uses the same instrumented binary and flags. Each resident engine has its own serial worker; requests release compiler/input/dependency state before acknowledgement. Both runs keep complete request timing and independent CLI object/library references.

## First: SHA-256 implementation was a substantial cost

Pilot run `20261030T231144.046017Z` compares LLVM and OpenSSL SHA-256 without changing identities or wire formats:

| Operation | LLVM SHA-256 ms | OpenSSL SHA-256 ms | Ninja ms | Ninja + ccache ms |
| --- | ---: | ---: | ---: | ---: |
| unchanged | 3.46 | 3.44 | 3.04 | 3.25 |
| implementation | 70.42 | 59.59 | 66.08 | 97.36 |
| shared-header | 48.35 | 39.20 | 41.91 | 64.77 |
| generated-header | 48.06 | 38.14 | 42.65 | 64.27 |
| unused-header | 3.35 | 3.52 | 3.04 | 3.05 |
| revert | 43.21 | 33.11 | 65.92 | 24.75 |

The digest provider alone removes roughly 9–11 ms from changed requests. Source edits fall from 70.42 to 59.59 ms against Ninja's 66.08 ms. Source/header/revert comparisons win all seven paired blocks against the prior provider and plain Ninja. Ccache remains faster on reverts. This identifies implementation cost rather than a source-control/build-engine floor; it does not establish a universal OpenSSL or instruction-set result.

Native setup attribution for a source edit:

| Stage | LLVM SHA-256 ms | OpenSSL SHA-256 ms |
| --- | ---: | ---: |
| Input admission | 6.371 | 2.158 |
| Action/mask preparation | 0.073 | 0.067 |
| Dependency state/per-file hashing | 5.447 | 1.461 |
| Candidate validation/import | 2.381 | 2.305 |
| Total native setup | 14.180 | 6.464 |

Input admission includes mapping, target setup, snapshot authentication/framing and temporary VFS validation. Content hashing includes dependency-state allocation and per-file identities. Candidate load includes checksums, replay, object import and final pre-worker setup. These stages are inside setup and must not be added again to the full request. Most removed cost is in the two bulk-hashing stages. Odin cache/action/report hashing and the Python producer/exporter are unchanged.

## Then: BLAKE3-256 reduces the expensive stages further

Main run `20261030T232026.999455Z` remeasures optimized SHA-256 and BLAKE3 with new independent controls:

| Operation | OpenSSL SHA-256 ms | BLAKE3 path ms | Ninja ms | Ninja + ccache ms |
| --- | ---: | ---: | ---: | ---: |
| unchanged | 3.48 | 3.45 | 3.09 | 3.13 |
| implementation | 59.13 | 57.27 | 65.52 | 97.87 |
| shared-header | 39.53 | 36.24 | 42.20 | 63.12 |
| generated-header | 37.32 | 36.32 | 42.01 | 63.75 |
| unused-header | 3.53 | 3.58 | 3.56 | 3.05 |
| revert | 33.94 | 31.15 | 64.91 | 24.49 |

BLAKE3 source edits improve another 3.1% against optimized SHA-256, shared headers 8.3%, generated headers 2.7% and reverts 8.2%. It wins all seven paired blocks for source/shared-header/revert and six of seven for generated headers. Against Ninja it wins every source/header/revert block: source median is 12.6% lower; header medians roughly 14% lower. Ccache still wins every revert comparison. No-op/unused-header lookups use the unchanged gate and show no claimed algorithm gain.

| Source-edit stage | OpenSSL SHA-256 ms | BLAKE3 path ms |
| --- | ---: | ---: |
| Input admission | 2.121 | 1.126 |
| Action/mask preparation | 0.073 | 0.066 |
| Dependency state/per-file hashing | 1.437 | 0.851 |
| Candidate validation/import | 2.306 | 2.251 |
| Total native setup | 5.989 | 4.301 |

The complete 3.34 MB snapshot and every admitted file still get hashed. BLAKE3 reduces source input admission from about 2.12 to 1.13 ms and content hashing from 1.44 to 0.85 ms; setup falls from 5.99 to 4.30 ms. Remaining request time includes preflight/snapshot encoding/publication, exact candidate checks, compilation/linking, report generation, condition export and receipt publication. Independent stage medians are not an exact additive partition. These are measured framework-level changes over arbitrary admitted byte collections, not project-specific compiler shortcuts.

## Contracts and verification stay explicit

BLAKE3 uses unkeyed 32-byte digests. The caller's C helper uses the installed BLAKE3 1.8.7 library; native admission/replay uses LLVM's BLAKE3 wrapper. Admission of real snapshots checks agreement between those builds. The Python ABI borrows caller-owned encoded bytearrays and exposes no private hash-state structs or payload copies. The official empty-input vector also passes. See the [official C API](https://github.com/BLAKE3-team/BLAKE3/blob/master/c/README.md).

This is a staged algorithm experiment, not a silent replacement of SHA-256:

- `GAIACIN2` retains SHA-256 pins; `GAIACIN3` requires `blake3:` pins and a matching request selection. Tags/header mismatches fail admission.
- `GAIAJR01` contains SHA-256 file/query fingerprints; `GAIAJR02` contains BLAKE3-256 fingerprints. Native replay checks the journal version. BLAKE3 actions also use a distinct key domain.
- Cache envelope checksums, selected-journal identities, reported object hashes, condition indices/backing verification, parsed-fragment caches and receipts remain SHA-256. Thus object hashes compare directly to independent CLI SHA-256 references. The exporter reads opaque validated fingerprints from either journal version and retains its original SHA-256 conditions.

All original framing, integrity, visibility, negative-lookup and pre/post input-stability checks remain. The optional libraries/helper are pinned into the execution context and checked with the other tools. Ordinary builds do not need the optional providers; accelerated requests fail explicitly when unavailable. This is not a selection of Gaia's global digest or a production dependency policy.

## Measurement scope and memory

Each main engine's worker handles 30 native requests (two seeds plus 28 timed changes). Full initial builds and worker startup are recorded as excluded setup; randomized operations use already-running workers. Parent runtime/initial SDK admission, editor writes, state restoration, graph generation and independent validation are excluded equally. The operation clock includes request/namespace creation, fresh lightweight checkers, observed edit discovery, snapshot encoding/hashing/atomic publication/admission, native work through cleanup, condition export and receipt publication. Gate hits send no native request. Tool versions, environment and frozen measured sources are retained with ignored raw evidence.

The main SHA-256 worker peaks at 237,953,024 bytes (226.93 MiB); BLAKE3 rises from 233,705,472 to 235,401,216 bytes (224.50 MiB) by the second request, then has the same cumulative high-water value. These are native-process high-water observations, not current idle RSS, whole-workflow memory or a hard quota. The caller/helper has its own footprint. Do not infer a memory advantage between algorithms from these samples. The native worker remains experimental: no production cancellation, idle eviction, automatic retry or arbitrary warning forwarding.

This remains one portable C target, canonical regular files/implicit directories, fixed virtual metadata, stat-visible changes and a warm-cache virtual Linux machine. CPU dispatch, small-input overhead and hash implementation affect results. More demanding C++ graphs, cold-cache transfers, longer worker lifetimes and other machines remain open. A measured win here does not establish broad dominance over Ninja or a final floor.

## Evidence

The two matched runs validate 336 libraries and 10,416 object identities. Nine [compile-heavy checks](BOUNDARIES.md) add 279 objects, for 345 libraries and 10,695 object checks across this effort. Every library/object and runtime probe matches, and exact compiler/link/fragment/tree/launch counts pass. The real shared header rebuilds 26 readers; changed flags and clean builds compile all 31.

[All 92 tests](correctness-tests.txt) pass. They cover ordinary and optional providers, alternating SHA-256 implementations with identical keys/journals/objects, alternating algorithms with isolated action/journal identities, wrong tags/versions, corrupt input/cache, eviction, negative lookups, cwd/visibility, repeated requests, output-directory recreation and failed-worker restart. The initial SHA-only comparison separately passed [82 tests](sha256-correctness-tests.txt). A [default build check](default-validation.json) links neither optional crypto nor BLAKE3 library, rejects unavailable accelerated requests, and passes all 74 ordinary tests ([log](default-correctness-tests.txt)); its 18 optional tests are skipped.

[Main summary](summary.json), [validation](validation.json), [SHA-only control](sha256-control/summary.json), [provider/contracts](providers.json), and [reproduction](../../README.md#blake3-with-explicit-algorithm-contracts). Full raw observations remain ignored/local; portable summaries retain hashes and paired comparisons. Compare values within each run rather than pooling absolute timings from different binaries/contexts.
