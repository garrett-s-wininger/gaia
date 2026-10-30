# Direct compiler-to-linker object buffers

Run `20261029T203940.351942Z`; **complete**; 15 randomized warm-cache blocks.

Fresh process per build, normal compiler disposal and process exit. Same zlib 1.3.2 inputs, Clang/LLD 22.1.8 flags, object order and single-threaded linker as the preceding queue experiment. File, buffer-file and direct cases use the same native binary. Buffer-file emits to memory then writes objects before linking; direct passes borrowed payloads to LLD without object files or memfd. The final shared library remains a real file.

| Mode | Whole process ms | Range ms | Child CPU ms | Compile wall ms | LLD call ms | Peak RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| make-8 | 538.527 | 479.9–630.2 | 2994.770 | — | — | — |
| physical-8-file | 497.958 | 455.6–621.0 | 2322.436 | 456.713 | 4.134 | 134.36 |
| physical-8-buffer-file | 499.913 | 477.4–553.1 | 2345.152 | 458.090 | 4.115 | 136.75 |
| physical-8-direct | 497.411 | 460.5–543.0 | 2317.349 | 454.052 | 3.903 | 136.77 |
| physical-1-file | 1709.552 | 1641.3–1833.5 | 1705.583 | 1669.212 | 4.268 | 116.66 |
| physical-1-direct | 1684.398 | 1615.7–1931.5 | 1680.662 | 1643.509 | 4.521 | 118.80 |
| memory-8-file | 480.457 | 439.8–577.7 | 2246.984 | 435.271 | 4.249 | 131.86 |
| memory-8-direct | 490.461 | 463.1–539.9 | 2260.679 | 448.431 | 4.502 | 136.22 |

## Paired wall time

| Change | Median delta ms | Wins |
| --- | ---: | ---: |
| make-8 → physical-8-direct | -43.058 | 13/15 |
| make-8 → physical-8-file | -39.020 | 13/15 |
| physical-8-file → physical-8-direct | +5.673 | 6/15 |
| physical-8-file → physical-8-buffer-file | +4.992 | 6/15 |
| physical-8-buffer-file → physical-8-direct | +0.229 | 7/15 |
| physical-1-file → physical-1-direct | -20.963 | 12/15 |
| memory-8-file → memory-8-direct | -6.412 | 8/15 |
| physical-8-direct → memory-8-direct | -6.950 | 9/15 |

## Boundary and interpretation

Direct mode captures Clang object output in native SmallVector buffers. A Linux executable symbol interposition adapter, pinned to this LLVM ABI, substitutes MemoryBuffer::getFile only during the serialized embedded link. LLD retains its normal readFile/input/context bookkeeping and owns borrowed buffer wrappers; payloads outlive the link context. The symbol is delegated normally outside this scope. This is an experimental integration, not an upstream supported object-provider API or a proposed standard. No binary patching or LLD rebuild is used. Missing object lookups fail rather than reading stale files.

Timed direct runs require exactly 15 buffer hits, zero object misses and zero object files. All object SHA-256 values and shared libraries must match the prior CLI/file control. Each configuration warmup passes upstream normal/64-bit checks. Direct warmups export objects only after linking to let upstream make check inspect the existing artifacts; timed direct runs never export. Direct/buffer-file hashes are computed inside the child after the native workload clock; file hashes are checked outside the whole-process clock. Whole-process results therefore include a small extra validation cost for captured modes. All modes perform normal teardown.

Compile/link wall counters exclude process startup and final teardown. LLD call time excludes handoff map setup; whole-process time includes it. Buffer-file export times are per job and overlap across workers; their sum is not a wall-time savings estimate. The worker/job count is bounded but compiler memory and per-object byte size have no hard allocator cap. Warm cache is not cold storage. CPU and scheduling variance can overwhelm small I/O savings.
