# Resolution diagnostics

Run: `20261028T230639.248141Z`.

Two distinct questions: import discovery binds module names to code locations; dependency resolution selects compatible package versions. The prior pip CLI already exercised version selection/backtracking, but did not isolate its duration. These diagnostics do not replace the original end-to-end observations.

## Import discovery with no code execution

15 randomized fresh processes per case, warm filesystem cache. Requests use the 312 code files actually executed by pip. Each process does four successful discovery scans and four same-parent missing-name scans, with exactly one miss per hit. This is a controlled hit/miss stress mix, not a measured miss rate from the CLI. Parent search paths are provided explicitly, so discovery never imports parent packages. Every result's origin/package flag is validated. No pip module imports or per-module code fetches occur. Hash-policy setup still scans bundle bytes for integrity verification. Each pass measures hits before misses, so the first miss scan already has parent-finder caches warmed by the first hit scan.

Directory discovery uses PathFinder/FileFinder, including normal per-directory importer caches. Bundle discovery opens/verifies/builds the module table during setup, then uses the existing Python meta-path provider for every indexed backend. Odin supplies bytes/index data, but the current module-name resolution map and spec creation still execute in Python. Request-list decoding/path construction is common untimed setup. Hit/miss scans include spec allocation; correctness validation and releasing result lists occur outside scans. Medians, ms; first use is computed per sample as setup + first successful scan.

| Input | Reader | Setup | First hits | Reused hits | First misses | Reused misses | Setup + first hits |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| source | directory | 0.002 | 6.096 | 3.803 | 1.988 | 1.990 | 6.097 |
| source | mmap | 8.388 | 0.484 | 0.259 | 0.034 | 0.027 | 8.821 |
| source | python-hash | 5.854 | 0.482 | 0.254 | 0.033 | 0.028 | 6.550 |
| source | python-local | 1.135 | 0.476 | 0.279 | 0.033 | 0.028 | 1.562 |
| source | odin-hash | 5.078 | 0.625 | 0.282 | 0.044 | 0.030 | 5.843 |
| source | odin-local | 0.782 | 0.472 | 0.277 | 0.034 | 0.029 | 1.307 |
| bytecode | directory | 0.002 | 7.713 | 4.399 | 2.047 | 2.117 | 7.715 |
| bytecode | mmap | 9.474 | 0.599 | 0.363 | 0.050 | 0.035 | 10.151 |
| bytecode | python-hash | 6.702 | 0.447 | 0.264 | 0.033 | 0.028 | 7.173 |
| bytecode | python-local | 1.091 | 0.461 | 0.265 | 0.033 | 0.027 | 1.514 |
| bytecode | odin-hash | 6.115 | 0.572 | 0.301 | 0.040 | 0.031 | 6.705 |
| bytecode | odin-local | 0.746 | 0.464 | 0.267 | 0.033 | 0.031 | 1.247 |

## Separately profiled full CLI

One whole-command cProfile run per selected case. Instrumentation adds overhead; these times must not be substituted into unprofiled timings. The profiler is imported before registering the input provider so it cannot accidentally prime the bundle index. Profiler imports can still change host-stdlib import state. Self-time buckets are disjoint and sum to profiled self time. Module-body self time does not include child functions called during initialization. The import bucket includes discovery/spec construction plus other import bookkeeping; it is not solely filesystem path resolution.

| Input | Reader | Profiled workload ms | Compilation ms | Bytecode decode ms | Import machinery ms | Solver/core integration self ms | Bundle provider self ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| source | directory | 911.307 | 471.320 | 13.085 | 67.825 | 4.881 | 0.000 |
| source | python-local | 892.157 | 472.522 | 13.492 | 59.401 | 5.146 | 3.660 |
| source | odin-local | 867.281 | 446.640 | 12.216 | 49.027 | 6.414 | 4.242 |
| bytecode | directory | 460.931 | 1.841 | 42.549 | 61.995 | 5.331 | 0.000 |
| bytecode | python-local | 441.104 | 1.551 | 40.923 | 63.872 | 5.276 | 3.512 |
| bytecode | odin-local | 444.339 | 1.880 | 44.530 | 52.080 | 5.230 | 4.654 |

### Inclusive phase observations

Each row includes nested calls and overlaps other rows. In particular, solver resolve phases include candidate/provider callbacks, wheel metadata work and imports triggered inside solving. They are not measurements of pure solver-algorithm CPU time. Import finder time includes lazy provider opening/index construction. Do not add these rows.

| Input | Reader | Phase | Calls | Inclusive ms |
| --- | --- | --- | ---: | ---: |
| source | directory | All import finders (_find_spec) | 580 | 41.581 |
| source | directory | Vendored resolver (includes provider callbacks/metadata) | 1 | 69.481 |
| source | directory | Pip resolve phase (includes lazy imports/candidates/metadata) | 1 | 69.855 |
| source | directory | Vendored resolver (includes provider callbacks/metadata) | 1 | 69.638 |
| source | python-local | All import finders (_find_spec) | 577 | 34.407 |
| source | python-local | Provider open/catalog/module table (all calls) | 890 | 5.909 |
| source | python-local | Pip resolve phase (includes lazy imports/candidates/metadata) | 1 | 67.171 |
| source | python-local | Vendored resolver (includes provider callbacks/metadata) | 1 | 66.756 |
| source | python-local | Vendored resolver (includes provider callbacks/metadata) | 1 | 66.953 |
| source | odin-local | All import finders (_find_spec) | 577 | 32.335 |
| source | odin-local | Provider open/catalog/module table (all calls) | 890 | 2.039 |
| source | odin-local | Pip resolve phase (includes lazy imports/candidates/metadata) | 1 | 74.846 |
| source | odin-local | Vendored resolver (includes provider callbacks/metadata) | 1 | 74.410 |
| source | odin-local | Vendored resolver (includes provider callbacks/metadata) | 1 | 74.615 |
| bytecode | directory | All import finders (_find_spec) | 580 | 38.371 |
| bytecode | directory | Vendored resolver (includes provider callbacks/metadata) | 1 | 74.282 |
| bytecode | directory | Pip resolve phase (includes lazy imports/candidates/metadata) | 1 | 74.728 |
| bytecode | directory | Vendored resolver (includes provider callbacks/metadata) | 1 | 74.506 |
| bytecode | python-local | All import finders (_find_spec) | 577 | 33.544 |
| bytecode | python-local | Provider open/catalog/module table (all calls) | 890 | 6.235 |
| bytecode | python-local | Pip resolve phase (includes lazy imports/candidates/metadata) | 1 | 69.110 |
| bytecode | python-local | Vendored resolver (includes provider callbacks/metadata) | 1 | 68.760 |
| bytecode | python-local | Vendored resolver (includes provider callbacks/metadata) | 1 | 68.915 |
| bytecode | odin-local | All import finders (_find_spec) | 577 | 29.428 |
| bytecode | odin-local | Provider open/catalog/module table (all calls) | 890 | 1.532 |
| bytecode | odin-local | Pip resolve phase (includes lazy imports/candidates/metadata) | 1 | 62.778 |
| bytecode | odin-local | Vendored resolver (includes provider callbacks/metadata) | 1 | 62.095 |
| bytecode | odin-local | Vendored resolver (includes provider callbacks/metadata) | 1 | 62.516 |

## Limits

This retains the same offline 22-wheel/12-package graph and pip 26.2.1; it is not a dependency-solver scale benchmark or a claim about difficult real-world graphs. The metadata-only discovery test bypasses normal sys.modules and parent-import behavior to isolate finders. Repeated scans measure finder caches, not cached import speed. All full CLI runs still validate report/selected versions, origins, resources, code counts and zero network attempts. Detailed disjoint buckets, inclusive function records and raw discovery samples/commands are in results.json. No new native resolver implementation or workload-specific optimization is introduced.
