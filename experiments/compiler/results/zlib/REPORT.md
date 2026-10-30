# Real-project compiler invocation: zlib 1.3.2

Run `20261029T165946.317034Z`; **complete**. 15 randomized blocks, fresh processes, warm filesystem cache.

Configured upstream static library, all 15 translation units, -O2/PIC. Same pinned source, generated configuration, compiler/flags/explicit header search and deterministic archive. Native modes use the generic Odin/C++ request-plan adapter; no zlib logic in the native compiler code, no PCH/AST/result cache. Memory mode hashes a mapped collection containing project inputs plus admitted system headers and has no real-filesystem input fallback.

| Mode | Complete library median ms | Range ms | Child CPU ms | Native compile ms | Native mount/setup ms |
| --- | ---: | --- | ---: | ---: | ---: |
| make-serial | 2233.466 | 2158.6–2425.0 | 2212.113 | — | — |
| make-parallel | 560.194 | 515.0–636.7 | 2944.920 | — | — |
| cli-batch | 2201.293 | 2151.4–2343.3 | 2183.581 | — | — |
| physical | 1651.582 | 1608.4–1715.0 | 1637.826 | 1593.929 | 0.564 |
| memory | 1620.408 | 1570.1–1685.9 | 1618.140 | 1547.405 | 4.552 |

## Paired complete-library comparisons

| Comparison | Median paired change ms | Wins / blocks |
| --- | ---: | ---: |
| make-serial → cli-batch | -23.183 | 8/15 |
| cli-batch → physical | -544.431 | 15/15 |
| physical → memory | -46.939 | 12/15 |
| cli-batch → memory | -607.085 | 15/15 |
| make-parallel → memory | +1061.551 | 0/15 |

make-serial and make-parallel run upstream make for libz.a, forcing all library objects/archive to rebuild before each observation; cleanup is outside timing. Parallel make uses 8 jobs. CLI batch is one normal clang command for all source files. Other modes compile sequentially and archive with the same ar rcsD command. Whole library time includes compiler/driver process startup, compilation/object writes, normal disposal and archive creation. make has its own archive/ranlib recipe. Linking/executing upstream tests is separate validation, not hidden work inside a reported build.

All timed objects and the final archive must match the CLI control byte for byte. Each mode warmup additionally passes upstream make check (normal and 64-bit tests) without changing the library. Native modes dispose per-request state and use normal exit. Parallel make has different execution concurrency; its CPU and wall time are both shown. This is one small C library, not a claim about C++, whole applications or general project builds.

Upstream test logs: /root/source/gaia/experiments/compiler_invocation/_work/project-20261029T165946.317034Z/make-serial-upstream-check.txt, /root/source/gaia/experiments/compiler_invocation/_work/project-20261029T165946.317034Z/make-parallel-upstream-check.txt, /root/source/gaia/experiments/compiler_invocation/_work/project-20261029T165946.317034Z/cli-batch-upstream-check.txt, /root/source/gaia/experiments/compiler_invocation/_work/project-20261029T165946.317034Z/physical-upstream-check.txt, /root/source/gaia/experiments/compiler_invocation/_work/project-20261029T165946.317034Z/memory-upstream-check.txt.

Boundary checks: wrong-pin, truncated-input, unsafe-name, missing-project-header, missing-system-header, truncated-plan, project-tree-unavailable.

## Separate compiler input traces

| Mode | Project input calls | System-header input calls | Bundle calls | Execs / cc1 execs |
| --- | --- | --- | --- | ---: |
| cli-batch | {'newfstatat': 15, 'openat': 75, 'pread64': 35, 'mmap': 40} | {'openat': 1256, 'pread64': 1165, 'mmap': 91} | {} | 16 / 15 |
| physical | {'newfstatat': 15, 'openat': 75, 'pread64': 35, 'mmap': 40} | {'openat': 1256, 'pread64': 1165, 'mmap': 91} | {} | 1 / 0 |
| memory | {} | {} | {'openat': 1, 'mmap': 1} | 1 / 0 |

Untimed traces include compilation only, not archive creation. Counts match admitted logical/canonical filenames in file/read/mmap syscalls, including failed probes; unrelated runtime/output activity and directory probes are excluded. They are not whole-process syscall totals or disk reads. All traced objects and the existing archive remain byte-identical. Raw traces are local artifacts.
