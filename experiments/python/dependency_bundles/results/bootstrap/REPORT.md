# Generic bootstrap experiments

Run: `20261029T153136.058419Z`; **complete**.

Warm filesystem cache, fresh isolated Python process, identical compact artifacts/native binary, bytes+slice handoff and normal interpreter exit. No dependency/framework code changes. Build/compilation is separate producer work. All samples validate application results, dependency execution/origins, resources and source inspection. Narrow imports change the preloaded stdlib set; the worker validates every newly loaded snapshot origin.

| Workload | Mode | Process wall ms | Child CPU ms | Bootstrap ms | Workload ms | RSS MiB |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1024 | source | 90.700 | 90.104 | — | 1.381 | 21.64 |
| 1024 | pyc | 79.740 | 79.097 | — | 1.350 | 21.38 |
| 1024 | thin-source | 76.933 | 76.274 | — | 3.567 | 20.44 |
| 1024 | thin-pyc | 77.018 | 76.541 | — | 3.307 | 20.14 |
| 1024 | programmatic | 62.668 | 61.971 | — | 3.373 | 19.15 |
| 1024 | gc4 | 65.622 | 64.969 | — | 3.376 | 19.28 |
| 1024 | gc16 | 63.792 | 63.157 | — | 3.122 | 19.23 |
| 131072 | source | 102.523 | 101.669 | — | 11.546 | 30.59 |
| 131072 | pyc | 92.659 | 91.779 | — | 11.985 | 30.29 |
| 131072 | thin-source | 95.517 | 94.462 | — | 13.294 | 29.39 |
| 131072 | thin-pyc | 84.186 | 83.555 | — | 13.159 | 29.06 |
| 131072 | programmatic | 74.843 | 74.077 | — | 13.521 | 28.08 |
| 131072 | gc4 | 74.914 | 72.898 | — | 13.425 | 28.22 |
| 131072 | gc16 | 76.821 | 73.446 | — | 13.049 | 28.12 |
| django | source | 503.973 | 503.300 | 56.768 | 251.968 | 66.15 |
| django | pyc | 473.240 | 472.641 | 46.927 | 264.942 | 65.32 |
| django | thin-source | 467.248 | 466.530 | 48.439 | 240.875 | 65.71 |
| django | thin-pyc | 456.064 | 454.561 | 37.255 | 247.970 | 64.89 |
| django | programmatic | 454.046 | 453.211 | 24.241 | 276.128 | 64.73 |
| django | gc4 | 459.934 | 459.051 | 26.797 | 271.577 | 64.70 |
| django | gc16 | 448.245 | 447.528 | 23.831 | 256.437 | 64.74 |

## Paired whole-process comparisons

| Workload | Mode vs source control | Median change ms | Wins / trials |
| --- | --- | ---: | ---: |
| 1024 | pyc | -7.001 | 12/15 |
| 1024 | thin-source | -11.948 | 12/15 |
| 1024 | thin-pyc | -14.439 | 13/15 |
| 1024 | programmatic | -26.044 | 15/15 |
| 1024 | gc4 | -25.700 | 14/15 |
| 1024 | gc16 | -25.781 | 15/15 |
| 131072 | pyc | -9.465 | 14/15 |
| 131072 | thin-source | -5.828 | 14/15 |
| 131072 | thin-pyc | -14.441 | 14/15 |
| 131072 | programmatic | -25.490 | 15/15 |
| 131072 | gc4 | -29.025 | 15/15 |
| 131072 | gc16 | -27.649 | 14/15 |
| django | pyc | -25.909 | 11/15 |
| django | thin-source | -1.922 | 8/15 |
| django | thin-pyc | -48.433 | 11/15 |
| django | programmatic | -23.202 | 12/15 |
| django | gc4 | -23.287 | 11/15 |
| django | gc16 | -44.755 | 13/15 |

## Incremental whole-process comparisons

| Workload | Change | Median paired change ms | Wins / trials |
| --- | --- | ---: | ---: |
| 1024 | source → pyc | -7.001 | 12/15 |
| 1024 | pyc → thin-pyc | -3.909 | 11/15 |
| 1024 | source → thin-pyc | -14.439 | 13/15 |
| 1024 | thin-pyc → programmatic | -10.214 | 14/15 |
| 1024 | programmatic → gc4 | +3.874 | 5/15 |
| 1024 | programmatic → gc16 | -1.086 | 8/15 |
| 131072 | source → pyc | -9.465 | 14/15 |
| 131072 | pyc → thin-pyc | -5.122 | 11/15 |
| 131072 | source → thin-pyc | -14.441 | 14/15 |
| 131072 | thin-pyc → programmatic | -13.475 | 12/15 |
| 131072 | programmatic → gc4 | -0.719 | 8/15 |
| 131072 | programmatic → gc16 | -2.039 | 9/15 |
| django | source → pyc | -25.909 | 11/15 |
| django | pyc → thin-pyc | -20.589 | 10/15 |
| django | source → thin-pyc | -48.433 | 11/15 |
| django | thin-pyc → programmatic | +10.428 | 5/15 |
| django | programmatic → gc4 | +10.407 | 7/15 |
| django | programmatic → gc16 | -5.523 | 10/15 |

Modes: source = unchanged consumer snapshot; pyc = same code, producer-compiled; thin-source/thin-pyc = independent resource adapter plus on-demand comparison/ZIP imports; programmatic = thin-pyc with exact CLI arguments admitted once and supplied as typed parameters, avoiding argparse; gc4 = programmatic with the generation-zero GC threshold multiplied by four, other thresholds unchanged; gc16 = programmatic with the generation-zero GC threshold multiplied by sixteen. GC remains enabled and normal shutdown runs in every mode. Programmatic compilation/configuration must be invalidated on argument/code/runtime changes; its producer cost is recorded, not hidden as consumer work. No warm worker or interpreter-state sharing is used.

Uninstrumented samples supply this table. Separate observed runs/profiles are diagnostics only. Source snapshots, exact thin.patch, source/bytecode hashes, commands and launch parameter source remain under the recorded work directory. Process time includes launch, all work/validation/output/close and normal finalization. Bootstrap and workload are worker clocks and exclude portions of CLI/programmatic launch. Do not compare absolute times with previous runs as speedups.
