# Sparse set differences save metadata, not cold local CPU

This prototype reconciles equal-cardinality sets of 256-bit content IDs. The real corpus contributes 3,931 distinct actual package hashes; generated 1,000/10,000-ID cases broaden size. Each rate replaces 0.1%, 1% or 10% of one inventory, giving a symmetric difference twice that replacement count. Three randomized blocks compare full sorted two-way inventories, a simple prefix-hash hierarchy with 32-ID leaves, and an IBLT-style table with three distinct positions and 64-bit cell checksums.

| Real 3,931-ID case, three removed/three added | Complete cold request | Encoded metadata | Logical rounds |
| --- | ---: | ---: | ---: |
| Full sorted inventories | 3.92 ms | 251,632 B | 1 |
| Prefix-hash hierarchy | 16.63 ms | 9,030 B | 3 |
| IBLT-style summary | 31.83 ms | 608 B | 1 |
| Underestimated IBLT plus fallback | 31.79 ms | 251,824 B | 2 |

The timing charges construction of both summaries and reconstruction/authentication of the target set using an exact SHA-256 commitment. Independent full-set and summary-update-rebuild oracles run outside request clocks. This is a cold algorithm comparison in Python, not network time or a native performance floor. A wire-accounting format counts signed 64/key 256/checksum 64 cells, explicit prefix/hash exchanges and complete-list fallback. It is a prototype encoding, not an optimized universal protocol.

All 108 operations match exact differences. Underestimated tables fall back in 27/27 cases. Decoding cannot silently hide required content; the reconstructed target set must match its exact commitment. The table has bounded peeling steps and reports a separate two-update maintenance diagnostic checked against full reconstruction. The hierarchy here rebuilds whole summaries; persistent optimized Merkle updates and warm maintained-summary request latency are not measured.

More disagreement weakens the wire advantage: at 10% replacements the hierarchy sends 220,154 B and IBLT 68,000 B versus full 251,632 B. Tiny sketches with bad estimates can exceed the full-list bytes after fallback. Construction, verification and retries must remain visible before claiming useful remote synchronization gains.

[Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json). Full results.json remains ignored local data. The [IBLT paper](https://arxiv.org/abs/1101.2245) supplies the scientific reference; the implementation/results are this bounded experiment. [Reproduce](../../README.md).
