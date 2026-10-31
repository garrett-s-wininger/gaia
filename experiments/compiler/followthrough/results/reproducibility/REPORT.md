# Inputs beyond source bytes

Six small compiler/archive probes exercise concrete request-identity requirements. They are deterministic counterexamples and controls, not a production-project reproducibility survey.

| Perturbation | Object/archive comparison |
| --- | --- |
| absolute-path-and-debug | Different |
| declared-path-mapping | Equal |
| CPATH-is-an-input | Different |
| SOURCE_DATE_EPOCH-is-an-input | Different |
| locale-C-vs-C.UTF-8 | Equal |
| archive-input-order | Order changes bytes; sorted order matches |

Absolute source paths affect `__FILE__` and debug information; explicit file-prefix and debug-compilation-directory mappings restore equality in the tested pair. `CPATH` selects different header contents. `SOURCE_DATE_EPOCH` changes the tested expanded date/time strings. C and C.UTF-8 locales preserve the selected object's bytes here, which is not proof that every tool or diagnostic is locale independent. Reversing ordered archive inputs changes archive bytes; sorting the same inputs restores the reference archive.

The native source-provider tests separately expose `__TIMESTAMP__`: normalized in-memory mtimes differ from physical source metadata. Supported logical-graph commands reject date/time builtins with `-Werror=date-time`. A general source collection needs explicit metadata/environment/clock semantics or declared restrictions, not merely a source-content digest.

All six probes pass their expected equal/different assertions. The measured archive tool is GNU ar 2.47; an initial attempt using an unavailable llvm-ar path was retried with the installed archiver. [Reproduce](../../README.md).
