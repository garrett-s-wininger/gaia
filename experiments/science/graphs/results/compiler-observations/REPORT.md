# Actual compiler observations

A three-TU C/C++ trace tests whether actual compiler observations can avoid full recompilation without retaining stale dependency facts. Across three randomized-order blocks, the eleven-operation sequence takes a median **261.03 ms** with full native recompilation and **116.22 ms** with validation and selective recompilation. Initial admission and three seed compiles are separate: 57.14 and 55.58 ms respectively. Unchanged three-TU operations take 23.56 versus 2.12 ms. These small-fixture results are not a large-project speedup claim.

| Operation | Full native, ms | Observed, ms |
| --- | ---: | ---: |
| Unchanged | 23.56 | 2.12 |
| Unrelated file | 24.33 | 2.46 |
| Include A becomes identical B | 22.38 | 6.24 |
| Old A changes | 22.54 | 12.11 |
| Current B changes | 25.17 | 10.44 |
| Earlier include shadows later file | 23.24 | 10.42 |
| Optional header appears | 24.28 | 20.08 |
| Optional header disappears | 23.70 | 15.75 |
| Compiler configuration changes | 21.41 | 21.79 |
| Invalid source | 21.69 | 5.18 |
| Recovery | 28.69 | 5.72 |

Each measured operation admits its edits and requests all three targets. Output and dependency-file restoration are inside both clocks. The independent physical Clang oracle runs outside both clocks, using the same source path and flags within each case. All 192 successful objects and dependency files match byte for byte; six invalid-source compilations fail as expected. Six stale-generation requests are rejected. The controller checks source and executable identities before and after the run.

The native Clang VFS adapter records positive source content, negative existence queries, real-path results and directory membership descriptors. The A-to-B transition deliberately produces identical IR: an object hit still refreshes observations and the depfile. A later edit of A stops invalidating that target, while an edit of B invalidates it. Optional appearance, deletion and earlier include shadowing exercise negative observations. Directory membership has a separate native interface test; this small compiler trace does not establish complete module-discovery coverage.

Seven regression tests additionally exercise deleted output restoration, stale generations, current dependency replacement, warning preservation, disabled-warning volatile date macros, directory descriptors and rejection of explicit sources outside the admitted root. A preliminary directory probe exposed a borrowed filename lifetime bug; the corrected owned-string implementation passed the tests before the measured source was frozen.

The observation cache accepts clean diagnostics only. Warnings and volatile date/time macros force the frontend to run. SDK, toolchain and environment outside the admitted source root are externally fixed by the caller's context. This is a bounded regular UTF-8 source namespace, not a claim of physical filesystem equivalence or complete hermeticity. Arbitrary side products, external effects, symlink identity and untracked environment changes are not supported. Cache entries have count and individual artifact limits, not a process RSS guarantee.

The full-native control uses the same host and VFS observation machinery while always running the frontend. It isolates avoided compilation work rather than comparing with a production build tool. Actual automatic integration is three TUs; the separate 33-TU Ninja study captures historical dependency relations only.

[Raw summary](summary.json), [validation](validation.json), [source and tool pins](provenance.json), [raw identity](raw-identity.json), [reproduction](../../README.md).
