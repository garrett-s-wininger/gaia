# Programmatic compiler invocation: Clang 22 / Odin host

Run `20261029T163845.341343Z`; **complete**. 15 randomized fresh processes per case; warm filesystem cache.

Actual C object generation at -O2, same compiler/target/flags and input bytes. CLI is one ordinary Clang command accepting all requested source files, not one artificial wrapper process per file. Physical and memory modes use Odin + Clang ToolInvocation/EmitObjAction in process. Memory mode hashes/validates one mapped collection and uses a VFS with no host input fallback. Each request creates/disposes its compiler/FileManager state; no PCH, saved AST, completed result or incremental parse state is reused.

| Headers per TU | TUs per process | Mode | Process median ms | Range ms | Child CPU ms | Compile ms | Input mount ms |
| ---: | ---: | --- | ---: | --- | ---: | ---: | ---: |
| 32 | 1 | cli | 53.150 | 45.85–70.92 | 52.520 | — | — |
| 32 | 1 | physical | 47.359 | 43.92–63.34 | 46.893 | 19.161 | 0.410 |
| 32 | 1 | memory | 47.013 | 41.89–95.21 | 46.367 | 17.694 | 0.651 |
| 32 | 8 | cli | 400.779 | 384.62–465.27 | 394.558 | — | — |
| 32 | 8 | physical | 133.275 | 121.88–155.30 | 132.567 | 103.040 | 0.424 |
| 32 | 8 | memory | 121.574 | 113.43–143.49 | 120.924 | 92.692 | 0.659 |
| 512 | 1 | cli | 141.173 | 133.85–158.97 | 140.555 | — | — |
| 512 | 1 | physical | 137.784 | 126.36–169.12 | 137.233 | 108.688 | 0.419 |
| 512 | 1 | memory | 131.827 | 125.21–196.03 | 131.235 | 100.062 | 1.796 |
| 512 | 8 | cli | 1184.909 | 1112.81–1255.73 | 1177.578 | — | — |
| 512 | 8 | physical | 880.484 | 835.58–921.90 | 876.187 | 850.820 | 0.416 |
| 512 | 8 | memory | 805.435 | 769.84–846.60 | 803.860 | 774.618 | 1.738 |

## Paired full-process comparisons

| Headers | TUs | Comparison | Median paired change ms | Wins / trials |
| ---: | ---: | --- | ---: | ---: |
| 32 | 1 | cli → physical | -5.864 | 12/15 |
| 32 | 1 | cli → memory | -6.822 | 13/15 |
| 32 | 1 | physical → memory | -2.008 | 10/15 |
| 32 | 8 | cli → physical | -267.137 | 15/15 |
| 32 | 8 | cli → memory | -279.499 | 15/15 |
| 32 | 8 | physical → memory | -11.372 | 11/15 |
| 512 | 1 | cli → physical | -2.277 | 8/15 |
| 512 | 1 | cli → memory | -3.122 | 12/15 |
| 512 | 1 | physical → memory | -4.240 | 9/15 |
| 512 | 8 | cli → physical | -304.774 | 15/15 |
| 512 | 8 | cli → memory | -387.416 | 15/15 |
| 512 | 8 | physical → memory | -72.536 | 15/15 |

All timed object hashes match CLI controls. Each mode/case warmup is linked and executed against independently computed results; linking/validation are outside compile timing. Timing includes compiler startup, mapped input authentication/setup, code generation/object writes, compiler-state disposal and process exit. Native phase clocks exclude startup; do not subtract independent medians. Native registration is included in setup, and compilation includes per-request setup/destruction. Programmatic mode disables Clang DisableFree to reclaim each request; CLI defaults may use process-exit reclamation. Both use normal process exit.

This is a synthetic flat C input fixture with repeated headers and eight generated source files, not a representative project or a standard protocol. In-memory VFS still uses path lookups and mutable per-file metadata; only payloads borrow the immutable mapping. Output and runtime-library activity remain filesystem based. Producer fixture generation, toolchain/header acquisition and adapter compilation are separate recorded costs. Current target: Linux x86-64, Clang/LLVM 22.1.8.

Boundary checks: wrong-pin, truncated, unsafe-name, missing-header, syntax-error, loose-inputs-unavailable.

## Separate syscall observations

| Headers | TUs | Mode | Loose-input path syscalls | Bundle path syscalls | Process execs / cc1 execs |
| ---: | ---: | --- | --- | --- | ---: |
| 32 | 8 | cli | {'newfstatat': 16, 'openat': 264, 'pread64': 264} | {} | 9 / 8 |
| 32 | 8 | physical | {'newfstatat': 16, 'openat': 264, 'pread64': 264} | {} | 1 / 0 |
| 32 | 8 | memory | {} | {'openat': 1, 'mmap': 1} | 1 / 0 |
| 512 | 8 | cli | {'newfstatat': 16, 'openat': 4104, 'mmap': 8, 'pread64': 4096} | {} | 9 / 8 |
| 512 | 8 | physical | {'newfstatat': 16, 'openat': 4104, 'mmap': 8, 'pread64': 4096} | {} | 1 / 0 |
| 512 | 8 | memory | {} | {'openat': 1, 'mmap': 1} | 1 / 0 |

Traces are separate runs and not benchmark samples. Counts match absolute input paths in file/read/mmap syscalls; failed probes are included. They are not whole process syscall totals or physical disk reads. Raw paths/traces are local artifacts.
