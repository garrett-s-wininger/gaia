# Naive baseline and original startup comparison

Run: `20261029T004920.057772Z`. Status: **complete**.

Warm filesystem cache; each observation starts a fresh isolated Python process. Existing artifact snapshots, exact queries and pip source/bytecode/native loader inputs are reused. No network, installation, new admission or native rebuild. The solver controls have identical lexical policy and artifact selection. The uncached reference is our deliberately cache-free provider, not pip behavior.

## Larger graph: uncached reference versus trail

3 randomized trials per case; two fresh solves per process, with session reuse only on the second. No extra untimed solver warmup. Medians, ms. First use is the per-observation sum of source open and first solve. Parsing/library imports precede the solve clock; complete process wall includes both solves, validation, output, shutdown and parent result decoding, so it is not a one-shot startup metric.

| Leaves | Variant | Samples | Open | First solve | Open + first | Second solve |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 250 | wheel-uncached | 3 | 7.941 | 560.060 | 566.989 | 532.246 |
| 250 | catalog-trail | 3 | 12.332 | 35.739 | 49.040 | 8.200 |
| 1000 | wheel-uncached | 3 | 33.730 | 6109.544 | 6144.057 | 5760.525 |
| 1000 | catalog-trail | 3 | 47.827 | 136.629 | 184.632 | 35.381 |
| 4000 | wheel-uncached | 3 | 160.993 | 155592.057 | 155753.050 | 180304.630 |
| 4000 | catalog-trail | 3 | 235.859 | 693.914 | 956.077 | 169.957 |

## Original startup: identical 22-wheel / 12-package case

15 randomized trials per case. Each solver process solves exactly once. Each real pip process executes the original offline dry-run CLI once, using the corrected worker that opens its input provider after the workload timer starts. Pip source and bytecode execute the same implementation. The Odin reader accelerates code-byte access; the interpreter and pip remain Python. Medians, ms.

| Consumer | Code input | Reader / variant | Samples | Complete invocation | Command / open + solve | Harness/library preparation |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Reference solver | host imports | wheel-uncached | 15 | 231.762 | 10.579 | 179.285 |
| Reference solver | host imports | catalog-trail | 15 | 234.275 | 2.828 | 188.970 |
| Real pip dry-run | source | directory | 15 | 912.570 | 730.386 | 49.166 |
| Real pip dry-run | source | python-local | 15 | 874.780 | 696.675 | 50.931 |
| Real pip dry-run | source | odin-local | 15 | 875.143 | 695.846 | 51.727 |
| Real pip dry-run | bytecode | directory | 15 | 447.811 | 275.629 | 47.945 |
| Real pip dry-run | bytecode | python-local | 15 | 429.739 | 256.331 | 50.246 |
| Real pip dry-run | bytecode | odin-local | 15 | 420.000 | 254.176 | 47.425 |

The two last columns have different scopes: the pip command includes importing its implementation, configuration, discovery/preparation, resolution and report generation; solver open + solve starts after importing its smaller dependency set. Complete process wall includes interpreter startup, setup, validation, serialization, cleanup and parent JSON result decoding in both harnesses. Validation/reporting work differs, so ratios compare these specific commands, not equivalent pip replacements. Independent column medians need not add.

The reference worker imports benchmark/fixture helpers as well as packaging/resolvelib. Its preparation time is not pure interpreter startup or a minimal-runtime floor. The earlier approximately 298 ms result was a separate synthetic 2,072-module loading process, not a dependency solve; see the [persistent-loader report](../../../dependency_bundles/results/persistent/REPORT.md). The fresh real-pip rows above revisit the later representative startup experiment.

All consumers must select the same versions on the original case. The two solver controls also match immutable artifact IDs, snapshot and target. The original wheels are hashed outside timing to verify that pip and the solver use identical bytes. Pip checks origins, code/resource reads, report hash, backtracking and zero network events. Solver closures are independently validated outside solve timing but inside complete process wall.

Admission/catalog creation is a producer cost carried forward from prior runs, excluded from all consumer times here. Real pip is measured only on its original small graph. The larger-graph speedups must not be presented as pip speedups or pure startup wins. There is no native solver, installer replacement or cold-cache claim.
