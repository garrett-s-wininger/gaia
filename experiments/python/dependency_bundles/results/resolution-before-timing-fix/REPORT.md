> Superseded CLI phase diagnostic: provider setup occurred before the workload timer. Discovery samples remain valid. See [corrected diagnostic](../resolution/REPORT.md). Original observations are retained.

# Resolution diagnostics

Run: `20261028T230335.555660Z`.

Two distinct questions: import discovery binds module names to code locations; dependency resolution selects compatible package versions. The prior pip CLI already exercised version selection/backtracking, but did not isolate its duration. These diagnostics do not replace the original end-to-end observations.

## Import discovery with no code execution

15 randomized fresh processes per case, warm filesystem cache. Requests use the 312 code files actually executed by pip. Each process does four successful discovery scans and four same-parent missing-name scans, with exactly one miss per hit. This is a controlled hit/miss stress mix, not a measured miss rate from the CLI. Parent search paths are provided explicitly, so discovery never imports parent packages. Every result's origin/package flag is validated. No pip module imports or per-module code fetches occur. Hash-policy setup still scans bundle bytes for integrity verification.

Directory discovery uses PathFinder/FileFinder, including normal per-directory importer caches. Bundle discovery opens/verifies/builds the module table during setup, then uses the existing Python meta-path provider for every indexed backend. Odin supplies bytes/index data, but the current module-name resolution map and spec creation still execute in Python. Request-list decoding/path construction is common untimed setup. Hit/miss scans include spec allocation; correctness validation and releasing result lists occur outside scans. Medians, ms; first use is computed per sample as setup + first successful scan.

| Input | Reader | Setup | First hits | Reused hits | First misses | Reused misses | Setup + first hits |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| source | directory | 0.002 | 6.119 | 4.118 | 2.026 | 2.127 | 6.120 |
| source | mmap | 8.479 | 0.453 | 0.267 | 0.033 | 0.027 | 8.909 |
| source | python-hash | 6.053 | 0.509 | 0.266 | 0.034 | 0.028 | 6.640 |
| source | python-local | 1.084 | 0.529 | 0.268 | 0.034 | 0.028 | 1.568 |
| source | odin-hash | 5.143 | 0.554 | 0.264 | 0.034 | 0.027 | 5.637 |
| source | odin-local | 0.719 | 0.465 | 0.260 | 0.033 | 0.028 | 1.188 |
| bytecode | directory | 0.001 | 6.814 | 4.714 | 2.112 | 2.179 | 6.815 |
| bytecode | mmap | 8.809 | 0.417 | 0.257 | 0.033 | 0.028 | 9.298 |
| bytecode | python-hash | 6.909 | 0.504 | 0.257 | 0.034 | 0.028 | 7.531 |
| bytecode | python-local | 1.081 | 0.446 | 0.263 | 0.033 | 0.028 | 1.611 |
| bytecode | odin-hash | 6.583 | 0.565 | 0.268 | 0.034 | 0.029 | 7.314 |
| bytecode | odin-local | 0.729 | 0.442 | 0.262 | 0.033 | 0.028 | 1.178 |

## Separately profiled full CLI

One whole-command cProfile run per selected case. Instrumentation adds overhead; these times must not be substituted into unprofiled timings. The profiler is imported before registering the input provider so it cannot accidentally prime the bundle index. Profiler imports can still change host-stdlib import state. Self-time buckets are disjoint and sum to profiled self time. Module-body self time does not include child functions called during initialization. The import bucket includes discovery/spec construction plus other import bookkeeping; it is not solely filesystem path resolution.

| Input | Reader | Profiled workload ms | Compilation ms | Bytecode decode ms | Import machinery ms | Solver/core integration self ms | Bundle provider self ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| source | directory | 933.071 | 489.978 | 13.313 | 67.378 | 6.245 | 0.000 |
| source | python-local | 856.739 | 449.577 | 12.528 | 48.090 | 5.764 | 2.047 |
| source | odin-local | 892.012 | 466.919 | 14.110 | 51.346 | 5.604 | 3.576 |
| bytecode | directory | 497.644 | 2.500 | 47.977 | 76.101 | 5.998 | 0.000 |
| bytecode | python-local | 475.129 | 2.109 | 46.722 | 56.867 | 5.264 | 1.746 |
| bytecode | odin-local | 445.052 | 1.558 | 43.020 | 54.441 | 6.411 | 3.868 |

### Inclusive phase observations

Each row includes nested calls and overlaps other rows. In particular, solver resolve phases include candidate/provider callbacks, wheel metadata work and imports triggered inside solving. They are not measurements of pure solver-algorithm CPU time. Import finder time includes lazy provider opening/index construction. Do not add these rows.

| Input | Reader | Phase | Calls | Inclusive ms |
| --- | --- | --- | ---: | ---: |
| source | directory | All import finders (_find_spec) | 580 | 40.273 |
| source | directory | Vendored resolver (includes provider callbacks/metadata) | 1 | 66.953 |
| source | directory | Pip resolve phase (includes lazy imports/candidates/metadata) | 1 | 67.307 |
| source | directory | Vendored resolver (includes provider callbacks/metadata) | 1 | 67.124 |
| source | python-local | All import finders (_find_spec) | 577 | 27.371 |
| source | python-local | Provider open/catalog/module table (all calls) | 890 | 0.174 |
| source | python-local | Pip resolve phase (includes lazy imports/candidates/metadata) | 1 | 69.070 |
| source | python-local | Vendored resolver (includes provider callbacks/metadata) | 1 | 68.307 |
| source | python-local | Vendored resolver (includes provider callbacks/metadata) | 1 | 68.477 |
| source | odin-local | All import finders (_find_spec) | 577 | 35.312 |
| source | odin-local | Provider open/catalog/module table (all calls) | 890 | 0.165 |
| source | odin-local | Vendored resolver (includes provider callbacks/metadata) | 1 | 71.206 |
| source | odin-local | Pip resolve phase (includes lazy imports/candidates/metadata) | 1 | 71.567 |
| source | odin-local | Vendored resolver (includes provider callbacks/metadata) | 1 | 71.369 |
| bytecode | directory | All import finders (_find_spec) | 580 | 39.324 |
| bytecode | directory | Vendored resolver (includes provider callbacks/metadata) | 1 | 83.441 |
| bytecode | directory | Pip resolve phase (includes lazy imports/candidates/metadata) | 1 | 83.827 |
| bytecode | directory | Vendored resolver (includes provider callbacks/metadata) | 1 | 83.626 |
| bytecode | python-local | All import finders (_find_spec) | 577 | 32.992 |
| bytecode | python-local | Provider open/catalog/module table (all calls) | 890 | 0.160 |
| bytecode | python-local | Pip resolve phase (includes lazy imports/candidates/metadata) | 1 | 68.538 |
| bytecode | python-local | Vendored resolver (includes provider callbacks/metadata) | 1 | 68.123 |
| bytecode | python-local | Vendored resolver (includes provider callbacks/metadata) | 1 | 68.272 |
| bytecode | odin-local | All import finders (_find_spec) | 577 | 30.255 |
| bytecode | odin-local | Provider open/catalog/module table (all calls) | 890 | 0.154 |
| bytecode | odin-local | Pip resolve phase (includes lazy imports/candidates/metadata) | 1 | 76.124 |
| bytecode | odin-local | Vendored resolver (includes provider callbacks/metadata) | 1 | 75.783 |
| bytecode | odin-local | Vendored resolver (includes provider callbacks/metadata) | 1 | 75.939 |

## Limits

This retains the same offline 22-wheel/12-package graph and pip 26.2.1; it is not a dependency-solver scale benchmark or a claim about difficult real-world graphs. The metadata-only discovery test bypasses normal sys.modules and parent-import behavior to isolate finders. Repeated scans measure finder caches, not cached import speed. All full CLI runs still validate report/selected versions, origins, resources, code counts and zero network attempts. Detailed disjoint buckets, inclusive function records and raw discovery samples/commands are in results.json. No new native resolver implementation or workload-specific optimization is introduced.
