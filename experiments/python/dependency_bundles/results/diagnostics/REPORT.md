# Loader cost and interpreter-floor diagnostics

Run: `20261028T210243.905409Z`. Original run: `20261028T205055.233700Z`. Same retained fixture inputs; new diagnostic processes.

## The original 298 ms sample

These phases come from the SAME observation at the median process wall time, so they add exactly. They differ from independently computed phase medians. Its remainder was not originally subdivided.

| Phase | ms |
| --- | ---: |
| Import | 175.51 |
| Resources | 5.44 |
| Application loop | 8.66 |
| Other process/harness work | 108.62 |
| Process total | 298.23 |

## Additional unprofiled phase observations

15 fresh-process trials per case, warm/reused filesystem cache. Means are used below so additive phases equal mean process wall. They diagnose new observations, not a retroactive partition of the original run. Common setup starts after importing the clock module. Outside-child time combines process launch, earlier interpreter bootstrap, output, shutdown and parent overhead.

| Phase (ms, means) | Source directory | Source persistent | Bytecode directory | Bytecode persistent |
| --- | ---: | ---: | ---: | ---: |
| Common harness imports/definitions | 48.78 | 44.89 | 45.98 | 47.87 |
| Arguments, manifest, provider registration | 10.00 | 10.09 | 10.76 | 11.60 |
| Fixture imports | 247.36 | 183.75 | 111.28 | 84.70 |
| Resources | 2.34 | 6.04 | 2.45 | 6.22 |
| Application loop | 10.81 | 10.04 | 10.71 | 8.79 |
| Correctness checks | 2.28 | 12.08 | 2.63 | 11.87 |
| Close/metrics | 0.21 | 0.26 | 0.21 | 0.25 |
| Outside observed child body | 36.47 | 39.88 | 35.12 | 37.98 |
| Process total | 358.24 | 307.02 | 219.14 | 209.28 |

## Startup probes

These are complete parent-observed process lifetimes, not a theoretical interpreter lower bound. The setup-only probe imports/defines the same harness but does not parse fixture arguments or load dependencies.

- `isolated_noop` median: **11.93 ms**.
- `worker_common_setup_only` median: **68.64 ms**.

## Import-only cProfile diagnostics

Separate instrumented runs: timing overhead is material. Self-time buckets are disjoint and sum to the profiled import interval; they must NOT be substituted directly into unprofiled timings. Detailed per-function self/cumulative data is in diagnostics.json; cumulative times overlap.

| Self-time bucket | Source ms | Bytecode ms |
| --- | ---: | ---: |
| Python import machinery | 98.56 | 71.84 |
| ZIP implementation | 52.04 | 46.93 |
| bytecode decoding | 0.00 | 6.67 |
| fixture module initialization | 6.01 | 3.80 |
| other builtins/runtime | 62.96 | 46.73 |
| provider callbacks | 14.15 | 13.37 |
| source compilation | 104.23 | 0.00 |

## Scope

This fixture eagerly imports 2,072 deliberately tiny modules. Installed module count is not the same as modules actually imported by a real startup. Real-package/application import traces are still required before treating this count or per-module workload as representative.

Precompiled inputs reduce source compilation work but require separate construction/version handling. Persistent sessions, lazy imports, native access implementations and alternative formats remain unmeasured optimizations. Fewer calls or faster probes do not establish their benefit automatically.
