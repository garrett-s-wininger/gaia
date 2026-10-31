# RuboCop startup: hash-provider work matters, warmed Bootsnap still leads

The initial packed-bytecode prototype loses to warmed Bootsnap. Profiling finds a large generic cost in its SHA-256 implementation. Switching the **implementation, preserving the exact algorithm, complete bytes and pin**, saves about **48 ms** in a fresh matched comparison. The refined pack still does not beat Bootsnap: **437.63 versus 428.23 ms**, with only one paired win in seven blocks.

This is a useful hash-provider result and a bounded negative container result. It does not establish that one archive improves a complete tool, or that this is Ruby's startup floor.

## Real operation and controls

Ruby **3.4.10 +PRISM**, RuboCop **1.92.2**, Bootsnap **1.26.1**, Linux x64. Each fresh Ruby process runs the actual upstream RuboCop executable, inspecting changing Ruby source with normal JSON offense reporting and normal exit. The server and **lint-result cache are disabled in every control** so all variants really inspect the source. Bootsnap's loader/ISeq/YAML caches remain enabled and warm.

All controls use the same local gem inventory, target Ruby version, config, executable and input. Offenses, exit status, request identity, cwd and the complete set of loaded RuboCop source features agree. The unused-argument offense changes with each request. Native extensions and config/resources retain their ordinary loaders. Full raw observations and [gem archive pins](gem-provenance.json) record the versions; the page cache is warm, not storage cold.

The pack holds **2,792 available compiled Ruby files** and a precomputed feature catalog in **26,540,787 bytes**. It restores compiled instructions, not initialized cops, class state or lint results. A typical Digest-pack process loads 996 ISeq entries and resolves 102 requests through the catalog. Unknown earlier load-path directories fall back to normal Ruby resolution. Load-path changes invalidate its small positive lookup cache.

## Matched full-process results

The final run has seven randomized blocks and **28 operations**:

| Loader | Median ms | Peak RSS median MiB | Wins against Bootsnap |
| --- | ---: | ---: | ---: |
| Normal require | 538.41 | 63.35 | 0/7 |
| Warmed Bootsnap | **428.23** | 65.08 | — |
| Pack, Ruby Digest SHA-256 | 486.03 | 91.83 | 0/7 |
| Pack, OpenSSL SHA-256 | **437.63** | 93.32 | **1/7** |

The clock includes fresh interpreter startup, common observation bootstrap, loader/native-library initialization, pack reading and verification, actual lint work, output and normal exit/wait. Parent JSON/offense/feature comparisons happen afterward. **OpenSSL require/init is inside the child clock**; it is not hidden in a resident process or untimed preload.

The provider change wins all seven blocks against the Digest-pack control and reduces its complete-operation median about 10%. It closes much of that control's gap to Bootsnap, while remaining roughly 2.2% slower by medians and losing six paired blocks. The higher RSS also remains a cost. See [summary](summary.json) and [validation](validation.json).

The earlier [three-control run](initial-control/summary.json) measured normal 537.26 ms, warmed Bootsnap 430.73 ms and packed 473.46 ms, with zero pack wins against Bootsnap. Its [validation](initial-control/validation.json), frozen sources and raw identities remain separate. Absolute times are not pooled across the two runs.

## What the diagnostic found

A separate [intrusive stage/call profile](loader-profile.json) preserves the same offenses and features. Its original Digest-pack run spends approximately:

| Component | Observed time |
| --- | ---: |
| Read the complete pack | 15.93 ms |
| Complete SHA-256 verification | **60.66 ms** |
| Decode the Marshal index | 9.76 ms |
| Total pack setup, including these stages | 87.82 ms |
| Bootsnap loader setup | 16.47 ms |
| Pack ISeq fetch/decode total | 90.44 ms |
| Bootsnap ISeq fetch/decode total | 84.80 ms |
| Pack resolver total | 1.32 ms |

These are one instrumented observation per mode, not distributions or an exact additive explanation of the main median gap. ISeq costs are nested within later CLI work. The implementation requests only **6.68 MB** of compiled payload from a 26.54 MB pack, so unused bytes and eager metadata remain relevant. The diagnostic changes call timing and is not mixed with the whole-process observations.

The [isolated hash sanity check](hash-provider-sanity.json) finds Ruby Digest taking 65.33 ms versus OpenSSL 12.23 ms for the exact same complete pack, after separately loading both providers. Both also pass the known SHA-256 `abc` vector. That isolated result excludes provider initialization; the matched full-process result above charges it.

All modes preserve the exact pack identity **`c72113faf91b2552ce53fa778660a5bf70efd65a8fce215813d28de34b6e4865`**. Ruby's OpenSSL extension is 3.3.3, linked at runtime to **OpenSSL 3.6.5**; its compile-time header constant reports 3.6.3. Native extension and crypto-library hashes are recorded in the final summary. This is an implementation-provider improvement, not BLAKE3, a weaker check or a wire-format change.

## Compiler equivalence, trust and costs

The [bytecode equivalence check](bytecode-equivalence.json) compares direct compilation, warmed Bootsnap output and the packed bytes for RuboCop's version, cop base and runner files. Their complete instruction trees and binary SHA-256 values are **identical**, using the same complete RubyVM compile options. The original loss is not explained by changing compiler flags or silently dropping functionality.

Pack production takes about **1.6 s** and keeps the available code plus metadata, not just what this command uses. First Bootsnap cache creation is separately recorded at about **1 s** for one complete inspection; warmed Bootsnap cache payload is about **6.85 MB**. These are single setup observations, not isolated producer-cost distributions. Source/config/native files remain present, so the pack is additional cache/storage, not a demonstrated source-replacing deployment format.

The pack assumes admitted **immutable package/runtime inputs** and requires rebuilding on source/runtime/options changes. Every process verifies the entire externally pinned artifact before interpreting its trusted Marshal index or private ISeq bytes. Warmed Bootsnap has its own local-cache metadata/revalidation contract. These integrity/editability models differ; their latency is not evidence that the contracts are interchangeable. The provider comparison holds the pack contract exactly fixed.

Size, index, entry bounds and runtime/options checks reject malformed or incompatible artifacts. Unknown directories preserve normal resolution; native extensions fall back. Active coverage, arbitrary plugins/require tricks and cross-build bytecode portability are outside this bounded CLI experiment. The serialized-size limits are not a process-RSS bound, and trusted interpreter bytecode is not an untrusted interchange format.

## Verification and reproduction

All **49 measured operations across the two runs**, validated warmups and first-cache observations agree. All [three guard/provider tests](correctness-tests.txt) pass, covering checksum/runtime-option/header rejection, unknown-directory fallback, repeated require behavior and SHA-256 vectors. Main operations additionally compare actual offenses and source-feature identity under changing input.

Use [acquisition](../../fetch_gems.py), [reproduction](../../README.md), [pack producer](../../build_pack.rb), [loader](../../packed_loader.rb), [diagnostic tool](../../profile_loader.py) and [bytecode checker](../../check_bytecode.rb). The raw `results.json` and `initial-control/results.json` are ignored local artifacts registered in the [repository evidence manifest](../../../../research/evidence.json). Frozen main/profile sources, inputs, gem archives and cache data remain in ignored `_work`; compact source pins use logical runtime/gem paths.

The remaining opportunity is to avoid eager unused metadata/payload costs while retaining complete admission and Ruby semantics. This run establishes no further optimization or general-purpose archive protocol.
