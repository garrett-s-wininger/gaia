# Refined workspace handoff and reuse

Fresh matched medians across three blocks; these values must not be compared as paired samples with earlier research runs. The Ninja + ccache path uses the same refined standalone index.

| Operation | Original shared complete | Refined complete | Ninja + ccache/index | Original editor | Refined editor | Ninja editor |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| noop | 10.22 ms | 4.91 ms | 8.04 ms | 10.20 ms | 4.88 ms | 6.78 ms |
| source | 291.69 ms | 279.38 ms | 505.86 ms | 291.68 ms | 125.94 ms | 197.01 ms |
| rewire | 294.09 ms | 276.24 ms | 511.16 ms | 294.07 ms | 125.25 ms | 151.49 ms |
| old header | 10.07 ms | 5.39 ms | 7.15 ms | 10.05 ms | 5.35 ms | 6.82 ms |
| new header | 290.16 ms | 277.32 ms | 398.52 ms | 290.14 ms | 125.63 ms | 141.11 ms |
| optional appear | 289.41 ms | 281.22 ms | 341.71 ms | 289.38 ms | 126.33 ms | 129.72 ms |
| optional remove | 294.98 ms | 129.67 ms | 182.31 ms | 294.96 ms | 5.70 ms | 5.27 ms |
| shadow | 289.38 ms | 275.57 ms | 352.13 ms | 289.36 ms | 124.11 ms | 127.29 ms |
| unrelated | 11.55 ms | 4.79 ms | 6.21 ms | 11.53 ms | 4.77 ms | 5.95 ms |
| header | 3114.32 ms | 2880.63 ms | 3210.62 ms | 3114.30 ms | 2725.95 ms | 1320.04 ms |
| configuration | 14360.02 ms | 272.33 ms | 2414.01 ms | 14360.00 ms | 124.67 ms | 118.26 ms |
| burst | 274.20 ms | 271.59 ms | 345.67 ms | 274.19 ms | 122.72 ms | 117.53 ms |

The configuration case changes one numeric command-line macro. Conservative lexical/macro checks reuse 32 of 33 targets and compile the target that reads it; other option classes retain exact contexts. Returning to the earlier optional-header state restores its old object/depfile and links without a frontend. All 108 operations match full physical object, depfile, executable and declaration-index references.

Refined editor timestamps are actual receipt of all current facts, emitted before the last backend/link. They are not build success and are not backfilled from compiler phase estimates. A multi-TU header edit still delays the project-wide query behind preceding serial backends; the independently running index remains faster there.

Summed timed operations have medians 20.28 s (original), 4.96 s (refined), 8.67 s (ninja-ccache). These exclude preparation, reference work and between-operation validation; they are not continuous complete sessions. Refined trace sums win all three pairs against Ninja/index.

Median current persistent-worker PSS is 189.3 MiB (original), 208.3 MiB (refined), 129.4 MiB (ninja-ccache). Lexical footprints and retained versions cost memory. Samples exclude controller/transient compiler/linker peaks, and counted history payload is not a total-memory quota.

The full matrix precedes framing/output-failure and configuration-guard hardening. Historical source/binary hashes remain intact; [measured-source.patch](measured-source.patch) reconstructs those scripts. The current implementation passes 16 refinement and four compatibility methods. The [supplemental handoff check](../handoff/REPORT.md) measures the hardened actual-TU path; this is not a full-matrix rerun.

[Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), [implementation/reproduction](../../README.md).
