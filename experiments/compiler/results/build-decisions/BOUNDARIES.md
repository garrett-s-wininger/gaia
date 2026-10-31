# Compile-heavy regression checks

One block per case validates correctness after adding the receipt gate and bounded candidates. These are not latency conclusions. All object/library identities and runtime probes match independent CLI references.

| Scenario | Mode | Compilers | Links |
| --- | --- | ---: | ---: |
| high-fanout-header | gaia-journal | 26 | 1 |
| high-fanout-header | gaia-history | 26 | 1 |
| high-fanout-header | gaia-fast | 26 | 1 |
| flags | gaia-journal | 31 | 1 |
| flags | gaia-history | 31 | 1 |
| flags | gaia-fast | 31 | 1 |
| clean | gaia-journal | 31 | 1 |
| clean | gaia-history | 31 | 1 |
| clean | gaia-fast | 31 | 1 |

Nine libraries and 279 object identities pass. See [validation](boundary-validation.json) and [compact results](boundary-summary.json). Raw observations in ignored `boundary-raw/results.json` are local-only; no download is published.
