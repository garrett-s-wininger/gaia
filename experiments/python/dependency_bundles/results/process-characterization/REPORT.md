# Whole-process lifecycle characterization

Run: `20261029T133339.555478Z`. Status: **complete**.

15 randomized fresh processes per workload/mode after correctness warmups; warm filesystem cache. Same retained compact artifacts and native binary as the parent run. Baseline has no observer, observed has lifecycle timestamps, and fast-exit is a diagnostic control that completes all application validation and explicit provider/SQLite closes before bypassing interpreter finalization with os._exit. Fast-exit is not a production optimization or equivalent lifetime contract. Batch disables automatic GC during construction, restores its original enabled state and explicitly runs a full collection before exit; deferred collection cost is included. Native admission/integrity and payload checks stay enabled.

| Workload | Mode | Process wall ms | Child CPU ms | Parent CPU ms | Worker peak RSS MiB | Output bytes |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| empty | baseline | 7.167 | 6.613 | 0.548 | — | 32 |
| empty | observed | 10.571 | 10.354 | 0.426 | — | 32 |
| empty | batch | 10.709 | 10.449 | 0.444 | — | 32 |
| empty | fast | 9.349 | 8.999 | 0.401 | — | 32 |
| harness | baseline | 47.456 | 46.892 | 0.623 | — | 34 |
| harness | observed | 49.042 | 48.558 | 0.603 | — | 34 |
| harness | batch | 48.713 | 48.275 | 0.578 | — | 34 |
| harness | fast | 43.808 | 43.359 | 0.482 | — | 34 |
| 1024 | baseline | 49.974 | 49.702 | 0.560 | 21.65 | 781 |
| 1024 | observed | 51.171 | 50.798 | 0.638 | 21.81 | 781 |
| 1024 | batch | 51.345 | 51.069 | 0.556 | 21.87 | 780 |
| 1024 | fast | 45.467 | 45.256 | 0.466 | 21.81 | 780 |
| 131072 | baseline | 57.485 | 57.098 | 0.591 | 30.53 | 776 |
| 131072 | observed | 58.188 | 57.965 | 0.559 | 30.74 | 784 |
| 131072 | batch | 58.721 | 58.284 | 0.623 | 30.80 | 796 |
| 131072 | fast | 52.549 | 52.322 | 0.473 | 30.74 | 785 |
| django | baseline | 238.189 | 237.883 | 0.720 | 66.18 | 62810 |
| django | observed | 242.143 | 241.654 | 0.673 | 66.09 | 62811 |
| django | batch | 245.063 | 244.609 | 0.711 | 66.41 | 62828 |
| django | fast | 185.592 | 185.098 | 0.678 | 66.08 | 62819 |

## Observed lifecycle wall intervals

| Workload | Launch → worker entry | Observer setup | Common imports | CLI/input prep | Workload | Validation/output/close → main return | Return → telemetry write | Telemetry/finalization/wait tail |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| empty | 5.798 | 2.580 | 0.006 | 0.002 | 0.001 | 0.036 | 0.011 | 2.074 |
| harness | 5.830 | 2.629 | 33.257 | 0.003 | 0.001 | 0.040 | 0.019 | 6.993 |
| 1024 | 6.414 | 2.512 | 28.757 | 4.706 | 0.729 | 0.506 | 0.028 | 7.506 |
| 131072 | 6.290 | 2.487 | 28.707 | 4.704 | 6.983 | 0.950 | 0.039 | 8.018 |
| django | 8.029 | 2.340 | 31.234 | 4.818 | 130.792 | 2.954 | 0.084 | 61.093 |

Each individual process is partitioned exactly using Linux monotonic timestamps shared between parent/child. Independent medians do not add. CPU comes from per-child rusage deltas plus child process-time checkpoints; a tail CPU residual can have small accounting noise. Parent spawn/pipe/wait CPU is separate. Launch→entry includes spawn/exec, interpreter initialization and time/sys imports. The last tail includes telemetry writing, remaining interpreter finalization and parent pipe/wait completion; it is not all proven shutdown time. Compare normal/fast controls for evidence. Observer mode explicitly flushes stdout and writes a small repr sidecar at exit. Baseline controls measure that observer tax.

Minimal control does no application work. Harness control imports the common Django worker and its general loader dependencies without running main. Shared harness preparation is experimental overhead rather than an intrinsic cost of the dependency format.

## GC observed before finalization

| Workload | Mode | Collections (median) | GC wall ms | Collected objects (median) |
| --- | --- | ---: | ---: | ---: |
| empty | observed | 0 | 0.000 | 0 |
| empty | batch | 1 | 0.262 | 0 |
| harness | observed | 8 | 1.081 | 89 |
| harness | batch | 1 | 2.249 | 129 |
| 1024 | observed | 8 | 1.058 | 124 |
| 1024 | batch | 1 | 2.406 | 129 |
| 131072 | observed | 8 | 1.033 | 124 |
| 131072 | batch | 1 | 2.878 | 129 |
| django | observed | 52 | 13.023 | 916 |
| django | batch | 1 | 22.124 | 1067 |

GC callbacks are removed before final telemetry writing; finalization GC after that point is not captured. Recorded GC durations are nested within the lifecycle intervals and must not be added to them. The batch control changes GC/finalizer timing and is a workload-specific experiment, not a production recommendation. Worker VmHWM is sampled before deferred batch collection; any later finalizer allocations are outside that RSS sample. Absolute times can differ substantially from earlier runs; no speedup from characterization instrumentation is claimed.

## Separate execution profiles

One normal-exit profile process per workload, split at lifecycle boundaries. Profiled times are diagnostic self-time/call counts, never unprofiled benchmark observations. cProfile initialization precedes common imports and changes bootstrap import state; application dependency outputs/execution sets still validate. Interpreter startup before worker entry and finalization after the atexit callback are outside profiling. No cumulative-time summation is used. Raw per-function records and disjoint buckets are retained in profiles.json; profile phases include observer bookkeeping.

empty: 

harness: 
- 00-observer_ready--common_prepared: other stdlib/runtime 24.3 ms, import machinery 10.2 ms, bytecode decoding 4.8 ms, filesystem primitives 3.5 ms

1024: 
- 00-observer_ready--common_prepared: other stdlib/runtime 19.1 ms, import machinery 7.5 ms, bytecode decoding 4.8 ms, filesystem primitives 3.7 ms
- 01-common_prepared--main_entered: other stdlib/runtime 5.3 ms, import machinery 3.1 ms, bytecode decoding 0.7 ms, filesystem primitives 0.3 ms

131072: 
- 00-observer_ready--common_prepared: other stdlib/runtime 19.0 ms, import machinery 7.7 ms, bytecode decoding 4.7 ms, filesystem primitives 3.7 ms
- 01-common_prepared--main_entered: other stdlib/runtime 4.8 ms, import machinery 2.5 ms, bytecode decoding 0.7 ms, filesystem primitives 0.3 ms
- 03-workload_begin--catalog_opened: bundle/provider 6.6 ms, other stdlib/runtime 0.2 ms, import machinery 0.0 ms, worker/harness 0.0 ms

django: 
- 00-observer_ready--common_prepared: other stdlib/runtime 21.9 ms, import machinery 9.9 ms, bytecode decoding 5.1 ms, filesystem primitives 3.8 ms
- 01-common_prepared--main_entered: other stdlib/runtime 5.3 ms, bytecode decoding 0.7 ms, import machinery 0.4 ms, filesystem primitives 0.2 ms
- 03-workload_begin--framework_initialized: other stdlib/runtime 54.8 ms, bytecode decoding 28.8 ms, import machinery 19.6 ms, Django 18.4 ms
- 04-framework_initialized--checks_finished: other stdlib/runtime 6.9 ms, Django 4.9 ms, bytecode decoding 4.2 ms, import machinery 3.3 ms
- 07-api_finished--workload_finished: Django 12.8 ms, other stdlib/runtime 9.1 ms, bundle/provider 1.1 ms, import machinery 0.6 ms

## Bootstrap source compilation audit

A separate untimed compile audit preserves application outputs/execution sets and records **9 consumer/harness source modules** compiled on startup, plus the worker script and fixture/dynamic code. No source text is retained. This is additional to the admitted dependency bytecode; the experimental harness itself has no generated caches under -B. Precompiled consumer bootstrap and narrower imports are concrete follow-up tests. Compilation events, sizes and a separate import-time graph are retained in diagnostics.json; import-time cumulative intervals overlap and are not summed into benchmark clocks.

## Interpretation

Common consumer bootstrap and late finalization are substantial components of these commands. The common harness imports comparison adapters beyond the selected backend. Bootstrap source compilation and narrower imports are concrete follow-up tests, distinct from dependency-format costs. Profiled code/class construction suggests initialized-state reuse as a further experiment with explicit isolation, memory, invalidation and lifetime requirements. GC batching must be judged by full process time, including its deferred collection, rather than readiness alone. See ../../FINDINGS.md#whole-process-lifecycle-characterization for interpretation of the retained run. No bootstrap or reuse speedup is claimed here.
