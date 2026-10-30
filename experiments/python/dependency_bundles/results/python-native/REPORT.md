# Odin connected to CPython

Run: `20261028T223649.522893Z`.

Fresh `python -I -S -B` per observation, warm/reused filesystem cache, randomized trials. All module source/bytecode is interpreted by CPython. Odin supplies byte access through a GIL-held C extension shim; no per-read IPC or external native worker is involved. The module/resource loader, compiler and bytecode semantics are unchanged.

## Cases and integrity

- `directory`: equivalent source-only/pyc-only loose input tree; generated caches disabled.
- `mmap`: Python index construction from ZIP metadata and mapped reads.
- `python-*`: Python binary-sidecar reader.
- `odin-*`: Odin loads/verifies/maps the sidecar and bundle, returns a catalog in one call, and checks CRC in native code on every read. The C shim copies the payload directly into an owned Python bytes object before returning, with the GIL held. Python still builds the name/module lookup objects; this measures the real boundary overhead too.
- `hash` rechecks whole-bundle SHA-256 at open; `local` checks admitted file identity in a trusted immutable local store. Sidecar digest pinning, bounds/UTF-8 checks and CRC remain. Mapping mutation/truncation is unsupported. Native input failures return Python exceptions; capsule destruction and explicit close release native mappings/allocations.
- Timing correction: in this original run, a lazy host import during temporary-directory setup opened pip bundle providers before the workload timer. Pip workload columns exclude that provider setup, while process-wall columns include it and remain valid. Synthetic workload timing is unaffected. The current worker defers provider/input publication until the timer starts; corrected phase diagnostics are in ../resolution/REPORT.md. Original observations are preserved rather than relabeled as corrected measurements. Their separate observed times are retained in raw samples. Common Python adapter imports are equal across controls. Process wall includes interpreter setup, the workload, validation and cleanup. Build and producer costs are outside consumer timing.

## Workloads

Synthetic: the existing 2,048-leaf fixture, 2,072 imported modules, relative imports, 32 package resources and a deterministic application checksum. The same worker/validation is used as before.

Representative: bundled pip 26.2.1 from `pip-26.2.1-py3-none-any.whl`, SHA-256 `71138adf1f4ca900cdb7d289c21b7494329f2332b6d85f0e1c42108c0384ed3e`. Its real pure-Python package/vendored dependency code executes normally through `runpy` as a CLI invocation. It performs an offline `install --dry-run --ignore-installed --no-index --find-links ... --report ...`, with isolated settings, cache/version checks disabled and an audit hook rejecting network operations. The 22 generated tiny wheels model a 12-package solution and force A 2.0 → A 1.0 backtracking. The graph/target wheels are synthetic; pip and its vendored implementation are unmodified. Nothing is installed. Host stdlib/native extensions remain ordinary interpreter inputs.

Pip validation compares exact selected versions, normalized report SHA-256 across layouts, all imported pip module origins/loaders, vendor.txt contents, missing-module rejection, one provider open, matching code-read counts across bundle providers, file-execution counts across all readers, and zero network events. Any certificate/path materialization and standard distribution-metadata/wheel access performed by pip are included in the workload; they are not intercepted by the Odin content adapter.

This invocation retains 310 unique pip module origins and 32 aliases; the execution audit records 312 distinct pip code files, including the CLI main and code no longer retained in sys.modules. Bundle code-read counts match the file-execution counts. Source and bytecode execution filenames are normalized to the same logical paths.

15 trials per case, plus one warmup. Medians, ms. Source/bytecode inputs have identical contents across readers within each mode; all timings are actual Python consumption.

| Workload | Input | Reader | Workload ms | Process wall ms | Workload p95 ms | Unique module origins | Peak RSS MiB |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| synthetic | source | directory | 263.148 | 364.416 | 299.069 | 2072 | 27.50 |
| synthetic | source | mmap | 174.305 | 301.019 | 210.367 | 2072 | 31.21 |
| synthetic | source | python-hash | 140.297 | 251.278 | 186.775 | 2072 | 30.35 |
| synthetic | source | python-local | 139.238 | 252.233 | 169.369 | 2072 | 30.35 |
| synthetic | source | odin-hash | 132.975 | 244.388 | 192.922 | 2072 | 30.59 |
| synthetic | source | odin-local | 131.621 | 247.368 | 159.287 | 2072 | 30.42 |
| synthetic | bytecode | directory | 121.438 | 225.695 | 144.200 | 2072 | 27.12 |
| synthetic | bytecode | mmap | 86.924 | 199.941 | 124.207 | 2072 | 31.47 |
| synthetic | bytecode | python-hash | 59.107 | 170.637 | 65.283 | 2072 | 30.48 |
| synthetic | bytecode | python-local | 59.296 | 176.075 | 102.881 | 2072 | 30.45 |
| synthetic | bytecode | odin-hash | 56.606 | 168.067 | 78.891 | 2072 | 30.56 |
| synthetic | bytecode | odin-local | 54.948 | 174.400 | 66.688 | 2072 | 30.43 |
| pip | source | directory | 738.338 | 920.262 | 884.260 | 310 | 48.88 |
| pip | source | mmap | 712.007 | 917.710 | 777.497 | 310 | 54.81 |
| pip | source | python-hash | 710.503 | 922.463 | 803.982 | 310 | 53.98 |
| pip | source | python-local | 723.284 | 947.005 | 837.297 | 310 | 53.98 |
| pip | source | odin-hash | 720.773 | 914.174 | 845.114 | 310 | 55.30 |
| pip | source | odin-local | 712.707 | 910.099 | 852.183 | 310 | 54.00 |
| pip | bytecode | directory | 297.166 | 471.435 | 373.431 | 310 | 47.59 |
| pip | bytecode | mmap | 262.666 | 458.222 | 355.004 | 310 | 54.67 |
| pip | bytecode | python-hash | 259.755 | 458.546 | 333.503 | 310 | 53.84 |
| pip | bytecode | python-local | 257.804 | 437.296 | 379.771 | 310 | 53.81 |
| pip | bytecode | odin-hash | 264.963 | 440.797 | 352.257 | 310 | 55.10 |
| pip | bytecode | odin-local | 285.473 | 460.768 | 325.124 | 310 | 53.84 |

## Limits

Linux/CPython-specific bridge; no stable platform ABI or container format is declared. The extension holds the GIL, returns bytes rather than exposed mapped views, and does not accelerate compilation, marshal, import machinery or application execution. Pip is one representative real tool over a generated graph, not evidence of typical ecosystem module counts, graph sizes or arbitrary real package startup. Repeated consumers, cold storage, concurrent mutation, namespace packages and native extensions inside the bundle are not covered. No syscall-count claim is made. Exact commands, input/extension hashes, raw phases and correctness observations are retained in results.json.
