# Reuse complete linked results and completion records

Pilot `20261030T233940.087356Z` and main run `20261030T235738.245668Z` are separate seven-block matched comparisons on Zstandard 1.5.7 portable C plus a probe, 31 objects and eight compiler workers. Same flags, logical paths and ordered object-only link inputs; all artifacts match independent CLI references. Warm page cache and already-started native compiler workers remain explicit.

## Latest complete-request results

| Operation | BLAKE3 control ms | Initial retention ms | Completion reuse + resident checker ms | Ninja ms | Ninja + ccache ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| unchanged | 3.46 | 3.45 | 2.51 | 3.17 | 3.37 |
| implementation | 55.43 | 64.24 | 60.94 | 66.56 | 98.18 |
| shared-header | 35.37 | 44.83 | 38.41 | 43.97 | 66.22 |
| generated-header | 35.77 | 43.90 | 38.35 | 42.41 | 64.11 |
| unused-header | 3.49 | 3.56 | 2.53 | 3.04 | 3.11 |
| revert | 30.85 | 14.09 | 9.43 | 66.64 | 24.74 |

The new path wins all seven paired blocks against both plain Ninja and Ninja + ccache in all six tested scenarios. Source edits are about 8% below plain Ninja and 38% below ccache; headers about 10–13% and 40–42% lower respectively. Reverts take 9.43 versus ccache's 24.74 ms (62% lower, 2.6× faster), and no-ops take 2.51 versus 3.17/3.37 ms. This is a result on one admitted C target, not a universal claim about build graphs or a final floor.

Retention still costs something: compared with the unretained BLAKE3 path, changed source/header medians remain roughly 3–5.5 ms higher. The new checker reduces no-op/irrelevant-input decisions by about 1 ms. Keeping prior libraries is valuable for reverts; it is not a free optimization for every miss. The initial retention path remains in the same main run so lookup/storage costs are visible rather than hidden in untimed setup.

## What a whole-result hit proves

The cache is keyed by the exact logical request: compiler argv, ordered link inputs/options, cwd, tool context, output roles and digest contract. Each candidate retains the actual compiler-derived condition index, covering positive contents, negative lookup, visibility, ancestor kinds and directory conditions. A native checker validates those constraints and the retained output receipt. This is stronger than merely finding previous object bytes: it establishes when that complete linked result applies.

On a hit, copied artifacts are always rehashed against the entry descriptor, even when retained metadata matches. Current inputs must remain stable during validation/restoration, and the current receipt is published last after another native condition/stability check. A hit skips snapshot construction/admission, object import, compilation, linking and condition export. Existing no-op/irrelevant-file hits use the current receipt first and never search history.

The main revert cases try two retained candidates and restore 830,575 bytes (library, native result IDs and condition index). All seven skip the entire native build pipeline. Ordinary edit misses try one candidate in these observations; a full three-candidate miss horizon can add more lookup work and is not separately timed here. The test suite exercises eviction after four states and lookup through the bounded catalog.

## Why the first retention attempt was not enough

The [initial pilot](initial-retention/summary.json) reduces reverts from 31.43 to 14.29 ms, beating ccache's 24.71 ms in every block. But its source/header misses pay another 6–10 ms for lookup and retaining the linked outputs. Header edits rise to about 44–45 ms, slightly above Ninja's 42 ms. No-ops remain around 3.5 ms.

Two remaining repetitions were removable:

1. The completed build had already produced a checksummed `GAIASK01` receipt binding exact input-condition identity, request and output hashes. Initial retention launched another checker and rehashed the copied outputs again. Completion-record reuse parses/checks that successful record, hashes each required copied output once against its recorded digest, preserves the same request/input identity, and rebinds only physical cache paths/metadata. A future hit still performs full native condition/receipt validation and copy hashing. This preserves previously established facts instead of claiming a new result without validation.
2. Every gate/history/record call started a fresh lightweight process. A serial checker now accepts bounded framed argv requests and resets all request allocations before acknowledgement. It retains no parsed namespace, conditions or decision result. Request construction, graph/namespace serialization and every validation stay inside the operation clock; nothing is shifted outside timing.

These are trusted local cache records from the completed build driver, not remote signatures or attestations. The fast retention path keeps only outputs covered by that completed record; optional parsed-fragment caches can be reused/recomputed normally later. The original path remains available as the matched control.

## Storage, modes and interruption

At most three committed candidates and 16 MiB of artifact payloads are retained per output directory. One staging candidate can temporarily add up to another payload budget; metadata and filesystem allocation overhead sit outside that accounting bound. Main edited seeds retain two entries totaling about 1.66 MB of payload. No global quota for native object history is established by this cache.

`GAIALC01` catalogs and current `GAIALR02` descriptors are checksummed, bounded JSON. The descriptor includes size, SHA-256, request and regular mode bits restricted to `0777`; modes are restored with bytes. The pilot used the earlier descriptor version in its frozen sources. Older versions miss in the current reader rather than being silently reinterpreted. Known unreferenced private entries are cleaned with a bounded scan; unknown/excess debris disables publication instead of an unbounded sweep. Only serial writers to the output/cache are supported.

Each file replacement is atomic. The output collection has no multi-file transaction or fsync/power-loss guarantee; its completion receipt is the commit marker. Interrupted/failed restores do not create a new valid receipt. Input mutation aborts rather than publishing stale success. Corruption/missing candidates fall back. Failed optional retention publication does not invalidate an already completed build, though the timed harness requires publication to succeed so an accidental disabled cache cannot be reported as an optimized result.

## Checker memory and cold behavior

The checker reserves 64 MiB of virtual arena space, reset before every completion acknowledgement. In the main run it handles 110 requests and uses at most 1,089,930 arena bytes (about 1.04 MiB) per request. Final checker RSS/high-water is 2,960 KiB (2.89 MiB); virtual size is about 71 MiB. Arguments/runtime/OS memory are outside the request arena. Malformed frame/count/argument bounds fail the worker, and tests verify stable repeated usage plus independent restart.

The native compiler is a separate larger resident process: final RSS is 139,376 KiB (136.11 MiB), with a 230,280 KiB (224.88 MiB) process high-water observation in this run. The Python caller has its own footprint. These measurements are not hard whole-workflow memory quotas. Production cancellation, idle eviction, concurrent writers, warning forwarding and automatic recovery remain open.

The first new-path seed includes checker/compiler startup and full compilation, about 2.79 s (one setup observation). Timed operations use those already-running workers. SDK admission, fixture/reference generation, editor writes, graph generation, state restoration and parent artifact/runtime verification are excluded equally. Compiler/request graphs are prepared as before; no new graph work was moved outside the clock. CPU accounting includes live-worker `/proc` ticks and is too coarse for fine CPU claims.

## Evidence and scope

The main run validates 210 libraries/6,510 object identities. The initial pilot adds 168 libraries/5,208 objects. [Compile-heavy checks](BOUNDARIES.md) add nine libraries/279 objects: 387 libraries and 11,997 object checks across this effort. Every artifact, runtime probe, expected compiler/link/fragment count, history bound and hit skip count passes. Ninja+ccache revert samples report direct cache hits; it reuses the object but Ninja still links, whereas this path reuses the already validated linked result.

[All 113 correctness tests](correctness-tests.txt) pass, including both retention paths, native fresh/resident equivalence, copied-payload corruption with preserved timestamps, exact request/tool/negative visibility guards, mutation during restoration, mode preservation, eviction/quota, malformed catalog/input, publication failure, completed-record/artifact disagreement, repeated arena reset, bad framing and process restart. The earlier pilot separately passed [97 tests](initial-correctness-tests.txt). A [default build](default-validation.json) with neither optional digest library passes all 95 ordinary tests ([log](default-correctness-tests.txt)); the 18 optional tests are skipped. The standalone/resident checker links no compiler or crypto libraries. A later [portable permission retest](portable-mode-validation.json) also passes all 11 history tests under `umask 077` ([log](portable-mode-tests.txt)); only the test expectation was made independent of the machine’s default umask after measurement.

The link fixture has explicit ordered objects only. Link scripts, discovered libraries and other implicit linker inputs need complete capture before this proof extends to them. Compiler conditions remain limited to the explicit canonical regular-file/implicit-directory provider with fixed virtual metadata and ordinary stat-visible backing changes. These are warm-cache measurements on a virtual Linux machine, not cold SDK, arbitrary POSIX or broad C++ graph results. No input integrity, negative-lookup or pre/post stability boundary is removed.

[Summary and paired comparisons](summary.json), [validation](validation.json), [initial pilot validation](initial-retention/validation.json), [reproduction](../../README.md#retain-complete-linked-results), [completion reuse/checker details](../../README.md#reuse-completion-records-and-keep-the-checker-resident). Full observations and frozen measured source trees remain ignored local artifacts; portable reports retain their identities.
