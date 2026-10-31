# A production C++ graph from admitted source generations

The upstream Ninja 1.13.2 executable provides 33 production C++ translation units, one static archive, a generated Python browse header and a final link. Both controls use the same flags, paths, SDK and one compiler worker. The candidate retains one initialized Clang host and an authoritative in-memory source namespace; Ninja uses a baseline-only ccache seed restored outside every timed operation. Changed-result history hits are excluded.

**The scheduler is a controlled fixed-dependency edit trace.** It uses baseline depfiles and known generator rules; it does not refresh dependencies or retain negative include queries. Newly introduced includes and optional-header appearance are not soundly covered by this scheduler. The source-provider unit tests establish VFS lookup behavior, not general graph invalidation. This is not the previous stronger logical-condition checker integrated into a production graph.

Three randomized blocks measure complete edit/admission, known dirty-TU compilation and archive/link work. The header probe appends an emitted used static function; the source probe appends an emitted function. The generator changes the embedded browse script, and the configuration probe enables assertions through `-UNDEBUG`. These labelled probes exercise real production code while keeping the change scope explicit. Runtime/byte validation is outside the operation clock for both paths.

| Operation | Shared host, ms | Ninja + seeded ccache, ms | Shared paired wins |
| --- | ---: | ---: | ---: |
| noop | 1.53 | 5.44 | 3/3 |
| source | 448.51 | 597.23 | 3/3 |
| header | 4790.09 | 6124.99 | 2/3 |
| generated | 439.36 | 564.53 | 3/3 |
| configuration | 23708.64 | 24353.15 | 2/3 |

The source and generated-input cases win all three pairs in this trace. Header and configuration changes win two of three, with substantial spread: the shared configuration run ranges from about 23.3 to 30.3 seconds. Three blocks do not establish a reliable general configuration/cold-build advantage. The no-op comparison applies only to this admitted fixed-dependency contract; it is not full physical workspace validation.

Initial CLI/ccache building takes 33.06 s; the subsequent host full build takes 23.44 s. These run sequentially and are preparation observations, not a randomized cold-build speed comparison. Source admission separately costs 34.62 ms for 124 files / 1,030,686 UTF-8 bytes. The complete initial host/tool/SDK acquisition cost is not represented by that admission number.

All 33 initial objects and the executable match the independent CLI. Each of the 30 measured operations verifies every object's identity and runs the built executable's version query. One additional editor interaction inspects an admitted unsaved generation, compiles its bytes, matches a physical CLI oracle, and rejects stale compile/update generations. This is a narrow input-sharing proof, not a complete editor diagnostics loop or multi-client completion-publication protocol.

The source-root filesystem has no fallback to physical source files. An initial integration attempt correctly failed when a third-party `.hpp` was omitted; the final adapter imports actual baseline project dependencies rather than trusting filename suffixes. Fixed baseline positive SDK dependencies and tool linkage are hashed before/after, while actual SDK reads remain physical. Source mtimes are normalized; `-Werror=date-time` rejects time-sensitive builtins. Immutable source generations do not establish a complete POSIX replacement.

The advisory measurement lock excludes other measured research lanes, not unrelated activity. Results establish this bounded single-worker trace; broader parallel scheduling, dynamic dependency discovery, negative conditions, cancellation, long-lived memory bounds and a larger target graph remain open. [Implementation and reproduction](../../README.md).
