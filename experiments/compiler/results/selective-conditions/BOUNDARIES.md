# Selective-condition compile-heavy checks

Single-block correctness checks, not performance conclusions. All objects, libraries, runtime probes and expected work counts match independent CLI references.

| Scenario | Engine | Compilers | Links |
| --- | --- | ---: | ---: |
| high-fanout-header | gaia-fast | 26 | 1 |
| high-fanout-header | gaia-selective | 26 | 1 |
| flags | gaia-fast | 31 | 1 |
| flags | gaia-selective | 31 | 1 |
| clean | gaia-fast | 31 | 1 |
| clean | gaia-selective | 31 | 1 |

Six libraries and 186 object identities pass. See [validation](boundary-validation.json) and [compact results](boundary-summary.json). Full observations in ignored `boundary-raw/results.json` are local-only.
