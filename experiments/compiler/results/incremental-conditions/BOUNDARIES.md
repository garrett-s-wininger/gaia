# Incremental producer compile-heavy checks

One block per case verifies semantics and fragment-reuse counts. These are correctness regressions, not latency conclusions. All object/library identities and runtime probes match independent CLI references.

| Scenario | Producer | Compilers | Links | Fragment hits | Fragment misses |
| --- | --- | ---: | ---: | ---: | ---: |
| high-fanout-header | gaia-selective | 26 | 1 | — | — |
| high-fanout-header | gaia-batched | 26 | 1 | 0 | 31 |
| high-fanout-header | gaia-incremental | 26 | 1 | 5 | 26 |
| flags | gaia-selective | 31 | 1 | — | — |
| flags | gaia-batched | 31 | 1 | 0 | 31 |
| flags | gaia-incremental | 31 | 1 | 0 | 31 |
| clean | gaia-selective | 31 | 1 | — | — |
| clean | gaia-batched | 31 | 1 | 0 | 31 |
| clean | gaia-incremental | 31 | 1 | 0 | 31 |

The real high-fanout header rebuilds 26 readers; incremental parsing reuses five fragments and decodes 26. Flags and clean builds compile/decode all 31. Nine libraries and 279 object identities pass. See [validation](boundary-validation.json) and [compact results](boundary-summary.json). Raw samples in ignored `boundary-raw/results.json` are local-only.
