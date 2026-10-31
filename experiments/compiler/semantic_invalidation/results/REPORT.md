# Semantic invalidation: skip object generation when compiler meaning survives an edit

The useful result is a backend-aware reuse boundary: appending an unused typedef to the heavier Zstandard translation unit changes preprocessed bytes and the AST, but preserves exact pre-optimization IR and the independently compiled object. IR-only reuse takes **74.58 ms**, versus **2265.93 ms for ccache**, with all three matched blocks improving. For comments and unused macros, ccache already reuses preprocessing results in about 40 ms and beats the IR check. The opportunity is deeper-than-preprocessing reuse, not a blanket replacement for existing caches.

The normalized diagnostic AST is not an object identity. Eight boundary probes produce four false hits: changed structure packing, function target attributes, inline assembly and debug line locations. Both exact-IR modes reject every one of those incorrect reuses across the JSON and direct-ODR runs (64 mode/case checks total). Source-level tree equality alone is insufficient.

The initial diagnostic-JSON matrix compares against text-invalidated recompilation. The direct-frontend follow-up adds a matched ccache 4.14.1 control. Ccache falls back to hashing preprocessor output and normally discards comments; its observed counter deltas confirm those existing wins. [Ccache manual](https://ccache.dev/manual/latest.html#_the_preprocessor_mode).

This is a translation-unit/object experiment under a fixed compiler, SDK, command and environment. It keeps the text fast path, compares every result with an independently compiled CLI object, and starts every operation from the same baseline candidate. It is not a production cache soundness proof or a per-function incremental compiler. [Implementation and reproduction](../README.md).

## Direct frontend and a competent cache control

A Clang `ASTFrontendAction` removes JSON dumping/parsing completely. It hashes ordered declaration kinds/names and Clang ODR summaries, with function bodies and dedicated record/enum handling. The heavy comment case spends about 58.7 ms in the complete frontend helper, including about 1.9 ms in the ODR walk; a second compiler invocation generates the exact IR guard in about 73.9 ms. This establishes that the earlier JSON bridge cost is avoidable. It does not establish a native frontend floor.

ODR summaries are only 32 bits and omit some code-generation details. SHA-256 over a list of them does not restore missing information. They are only candidate screens; exact current IR is still mandatory. The direct-ODR boundary run reproduces all four AST-only false hits, and both IR modes match all current compiler objects, including the C++ template case.

The follow-up uses three randomized blocks, four modes and five scenarios on both sources: **120 measured objects**, all correct. The ccache binary, configuration, version and direct/preprocessed/miss counter deltas are retained. Each source primes one baseline cache; every measured ccache operation restores that exact seed outside the timer, preventing repeated-edit hits. Compiler commands/output path are identical, compiler checks hash content, compression stays enabled, and the library-loader environment is the same for every mode.

| Heavy source operation | Text cache | Direct AST + IR | IR only | ccache |
|---|---:|---:|---:|---:|
| Unchanged | 0.61 ms | 0.61 ms | 0.60 ms | 5.51 ms |
| Comment | 2188.87 ms | 133.56 ms | 71.40 ms | **39.59 ms** |
| Unused macro | 2157.64 ms | 126.18 ms | 73.27 ms | **39.91 ms** |
| Unused typedef | 2176.09 ms | 2264.99 ms | **74.58 ms** | 2265.93 ms |
| Emitted semantic change | **2208.74 ms** | 2267.05 ms | 2337.56 ms | 2244.77 ms |

Ccache reports three direct hits for unchanged, three preprocessor hits each for comments/unused macros, and three misses each for the typedef and emitted semantic change. The unused typedef's `-E` output differs from baseline, while its independently compiled object remains identical. IR-only hits in all three blocks and improves against ccache in all three, with roughly a 30× difference between medians on this case. The AST filter rejects the extra declaration and unnecessarily recompiles: an AST change does not imply an object change.

The light source has too little backend work and too much timing variability for a comparable win. Its unused-typedef medians are 73 ms for recompilation, 208 ms for IR and 193 ms for ccache; the IR run ranges from about 90 to 279 ms. Do not generalize the heavy-unit gain to every translation unit. The heavy guard also has outliers on real misses, including a 5.87 s typedef fallback; every sample remains in the raw data.

The direct seed costs for heavy source are 2985 ms for the original object, 65 ms for its AST candidate and 78 ms for IR. Ccache primes its baseline in 2295 ms. On a mode-specific comparison, the original object is common cache preparation; IR adds about 78 ms here. A repeated typedef-like edit saves about 2.19 s relative to the seeded ccache control, so one such hit would amortize that extra IR seed under the measured model. This excludes tool compilation, project/SDK admission, eviction and retention costs. Oracle compilation costs a further 11.6 s for research validation and is excluded from request timings. There is no predicted workload mix or universal break-even claim.

The direct run additionally rejects private-project membership changes, checks all existing pins and symlink bindings again, and pins ccache before/after. Fast text hits assume that admitted fixed context; ccache independently performs its own filesystem checks. The unchanged row therefore does not establish a general validation advantage over ccache in a mutable workspace.

[Direct summary](direct-ast/summary.json), [object/context validation](direct-ast/validation.json), [raw observations](direct-ast/results.json), and [direct boundary checks](direct-boundaries/results.json) preserve the comparison.

## Initial native diagnostic-JSON attempt

The C++ helper uses LLVM's JSON parser, sorts object keys, normalizes selected declaration IDs, omits locations/ranges, then hashes versioned structural tokens with OpenSSL. It avoids Python object construction but retains the entire external AST dump/read/parse bridge. That bridge is expensive here: the light unit's dump is about 37 MB; native read/parse takes approximately a second, while walking/hashing takes tens of milliseconds. Its Python predecessor was also expensive, but these separate runs do not establish an inherent language or frontend floor.

Three randomized blocks measure four modes and five scenarios on each unchanged upstream source. The archive and source bytes match Zstandard 1.5.7. Both source files are privately cloned; edits are clearly appended probes or leading blank lines.

| Source / edit | Text recompilation | AST candidate | AST + exact IR | Exact IR only |
|---|---:|---:|---:|---:|
| Light / comment | 50.34 ms | 1372.87 ms | 1371.11 ms | 46.35 ms |
| Light / unused macro | 55.00 ms | 1272.06 ms | 1425.01 ms | 47.14 ms |
| Light / emitted semantic change | 85.20 ms | 1318.85 ms | 1454.21 ms | 99.34 ms |
| Heavy / comment | 2599.24 ms | 4188.56 ms | 4241.80 ms | 74.44 ms |
| Heavy / unused macro | 2250.78 ms | 4246.84 ms | 4264.27 ms | 71.58 ms |
| Heavy / leading blank lines | 2180.27 ms | 5006.81 ms | 4233.85 ms | 2299.22 ms |
| Heavy / emitted semantic change | 2176.64 ms | 4535.73 ms | 4429.73 ms | 2267.57 ms |

Unchanged requests use the text hash in every mode; median times are around 0.1–1 ms. The JSON candidate misses the heavy unit's benign edits and falls back, so it is an ineffective filter in this form. The exact IR check succeeds without it for comments and unused macros.

Leading blank lines demonstrate a conservative miss: heavy IR changes even though the independently compiled objects are identical. Exact comparison deliberately preserves all IR text, source filenames, module flags, attributes, inline assembly and debug metadata. No fields are erased to manufacture a hit. The real semantic-change probe adds an emitted `used` constant; every stronger mode compiles it and matches the current CLI object.

There are substantial outliers: a heavy semantic IR miss reaches 10.44 s in one block, and a heavy comment IR hit reaches 713 ms. All observations remain preserved. Large backend savings for the benign heavy cases are apparent across the matched samples; small light-unit differences are not a dependable optimization claim.

[Native JSON summary](native-json/summary.json) separates compiler/dump time, normalization, helper read/parse and walk/hash time. [Raw observations](native-json/results.json) preserve all 120 measured outputs and the initial seed/oracle costs.

## Boundary evidence and contracts

The probes cover comments, `__LINE__`, packing, target attributes, inline assembly, debug locations, macro stringification and a C++ template instantiation. The native JSON run checks 32 mode/case combinations: AST-only incorrectly reuses four objects; text, guarded-AST and IR-only match every current compiler object. [Boundary observations](boundaries/results.json).

Initial object creation, candidate preparation and exact IR preparation are separate. The measured light seed takes about 166 ms to compile, 485 ms to dump its AST plus 3773 ms to normalize it, and 105 ms to generate IR. Heavy seed takes about 2295 ms to compile, 227 ms to dump plus 1793 ms to normalize, and 69 ms to generate IR. These are observed first preparations, not cache-cleared cold-start floors. A chosen mode would prepare only its necessary representations; the experiment prepares all once to share the same baseline object. Oracle compilation is research validation, outside request timings.

Before and after each source's run, the harness rereads hashes for all other private-project files, the initial compiler dependency closure, compiler binary and linked libraries, checks symlink targets and the inherited environment digest, and pins the helper binary. The initial run checks 197/213 files for light/heavy sources. This admission work is outside request timings; its elapsed cost is not measured in the initial matrix. The private clone has no concurrent writers. Before/after equality is not an atomic immutable-generation proof and does not capture every possible SDK discovery rule.

The cache returns only `.o` bytes. It does not reproduce changed-source diagnostics or other compiler side products on a hit; that contract must be supplied before product use. On misses this CLI prototype invokes a second full compiler after generating a candidate/IR, repeating frontend work. A compiler-native integration should retain the current frontend/IR and continue directly into optimization/code generation.

The next useful integration point is the existing native compiler host: fingerprint the current IR at the frontend/backend boundary, reuse the object on a hit, and continue with the same live IR on a miss. Preserve admitted inputs, all code-generation identities, diagnostics/side products and the independent object oracle. Per-function dirtiness and C++ production graphs remain separate research.
