# Generic bootstrap experiments

Run: `20261029T153402.608893Z`; **complete**.

Warm filesystem cache, fresh isolated Python process, identical compact artifacts/native binary, bytes+slice handoff and normal interpreter exit. No dependency/framework code changes. Build/compilation is separate producer work. All samples validate application results, dependency execution/origins, resources and source inspection. Narrow imports change the preloaded stdlib set; the worker validates every newly loaded snapshot origin.

| Workload | Mode | Process wall ms | Child CPU ms | Bootstrap ms | Workload ms | RSS MiB |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| django | source | 470.638 | 469.966 | 56.835 | 243.236 | 66.17 |
| django | thin-pyc | 453.907 | 453.256 | 43.449 | 247.398 | 64.90 |
| django | programmatic | 452.965 | 450.970 | 26.522 | 258.318 | 64.72 |

## Paired whole-process comparisons

| Workload | Mode vs source control | Median change ms | Wins / trials |
| --- | --- | ---: | ---: |
| django | thin-pyc | -16.715 | 23/30 |
| django | programmatic | -22.942 | 22/30 |

## Incremental whole-process comparisons

| Workload | Change | Median paired change ms | Wins / trials |
| --- | --- | ---: | ---: |
| django | source → thin-pyc | -16.715 | 23/30 |
| django | thin-pyc → programmatic | -8.216 | 19/30 |

Modes: source = unchanged consumer snapshot; pyc = same code, producer-compiled; thin-source/thin-pyc = independent resource adapter plus on-demand comparison/ZIP imports; programmatic = thin-pyc with exact CLI arguments admitted once and supplied as typed parameters, avoiding argparse; gc4 = programmatic with the generation-zero GC threshold multiplied by four, other thresholds unchanged; gc16 = programmatic with the generation-zero GC threshold multiplied by sixteen. GC remains enabled and normal shutdown runs in every mode. Programmatic compilation/configuration must be invalidated on argument/code/runtime changes; its producer cost is recorded, not hidden as consumer work. No warm worker or interpreter-state sharing is used.

Uninstrumented samples supply this table. Separate observed runs/profiles are diagnostics only. Source snapshots, exact thin.patch, source/bytecode hashes, commands and launch parameter source remain under the recorded work directory. Process time includes launch, all work/validation/output/close and normal finalization. Bootstrap and workload are worker clocks and exclude portions of CLI/programmatic launch. Do not compare absolute times with previous runs as speedups.
