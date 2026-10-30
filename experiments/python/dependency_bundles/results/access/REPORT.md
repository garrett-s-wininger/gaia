# Generic stored-bundle access experiment

Run: `20261028T212315.366515Z`.

Same immutable ZIP bytes for all cases, no fixture imports/compilation/execution. Warm/reused filesystem cache; new process per trial. All backends verify payload CRC on every read/view. Indexed backends validate local headers/names/ranges up front; ZipFile validates its entry headers during reads. Full SHA-256 member equivalence is checked outside timing.

2104 entries, 429,600 payload bytes, 15 trials per case, 4 passes per process.

`zipfile` is the common-wrapper baseline. `pread` uses indexed positional reads. `mmap` uses mapped ranges. `resident` reads the whole archive into memory once. Opening, central parsing, header validation, mapping/whole-file reading are included in index time. Bytes mode returns copied bytes in every case. View mode can avoid payload copies for mmap/resident; ZipFile/pread views still wrap allocated bytes. All views are released before close.

## Timing

Medians, ms. Reused pass is the per-process mean of passes after the first. First-use median is computed from each sample's index + first-pass time, not a sum of medians. Close and extra correctness checks are outside these access intervals.

| Backend | Result | Order | Open/index ms | First pass ms | Reused pass ms | First use ms | Peak RSS MiB |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| zipfile | bytes | lexical | 28.330 | 19.257 | 18.542 | 48.256 | 24.80 |
| zipfile | bytes | shuffled | 27.739 | 35.683 | 35.542 | 64.515 | 24.80 |
| zipfile | view | lexical | 27.329 | 19.655 | 19.459 | 46.940 | 24.82 |
| zipfile | view | shuffled | 29.173 | 35.506 | 34.949 | 64.499 | 24.81 |
| pread | bytes | lexical | 37.333 | 3.750 | 3.565 | 41.169 | 25.30 |
| pread | bytes | shuffled | 39.839 | 4.204 | 4.239 | 44.193 | 25.30 |
| pread | view | lexical | 38.015 | 4.347 | 4.460 | 43.150 | 25.31 |
| pread | view | shuffled | 38.283 | 5.147 | 4.776 | 43.298 | 25.31 |
| mmap | bytes | lexical | 33.898 | 1.782 | 1.877 | 36.491 | 25.68 |
| mmap | bytes | shuffled | 34.001 | 2.316 | 1.877 | 36.701 | 25.70 |
| mmap | view | lexical | 33.902 | 1.681 | 1.680 | 35.491 | 25.70 |
| mmap | view | shuffled | 33.518 | 2.259 | 1.645 | 36.326 | 25.71 |
| resident | bytes | lexical | 35.210 | 1.748 | 1.651 | 36.870 | 25.79 |
| resident | bytes | shuffled | 35.221 | 2.244 | 1.825 | 38.221 | 25.81 |
| resident | view | lexical | 32.425 | 1.623 | 1.717 | 33.934 | 25.80 |
| resident | view | shuffled | 33.693 | 1.925 | 1.685 | 35.440 | 25.80 |

## Separate syscall observations

Read-loop counts cover all repeated passes; index work is bracketed separately. mmap page faults are not `read` syscalls and may still perform work/I/O. Returned read bytes are syscall results, not physical disk traffic. Timing samples exclude tracing.

| Backend | Result | Order | Index calls | Loop reads | Loop seeks | Loop calls |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| zipfile | bytes | lexical | 29 | 20 | 25252 | 25272 |
| zipfile | bytes | shuffled | 29 | 6624 | 31864 | 38488 |
| zipfile | view | lexical | 29 | 20 | 25252 | 25272 |
| zipfile | view | shuffled | 29 | 6624 | 31864 | 38488 |
| pread | bytes | lexical | 4238 | 8416 | 0 | 8416 |
| pread | bytes | shuffled | 4238 | 8416 | 0 | 8416 |
| pread | view | lexical | 4238 | 8416 | 0 | 8416 |
| pread | view | shuffled | 4238 | 8416 | 0 | 8416 |
| mmap | bytes | lexical | 32 | 0 | 0 | 0 |
| mmap | bytes | shuffled | 32 | 0 | 0 | 0 |
| mmap | view | lexical | 32 | 0 | 0 | 0 |
| mmap | view | shuffled | 32 | 0 | 0 | 0 |
| resident | bytes | lexical | 35 | 0 | 0 | 0 |
| resident | bytes | shuffled | 35 | 0 | 0 | 0 |
| resident | view | lexical | 35 | 0 | 0 | 0 |
| resident | view | shuffled | 35 | 0 | 0 | 0 |

## Limits

This establishes a relative access-layer baseline under Python with this CRC/copy policy, not a universal hardware/native-language floor. Directory parsing and request iteration still use Python/ZipFile. The synthetic corpus is many tiny source files plus a few resources. Compressed/encrypted/descriptor/ZIP64 members, mutable files during mapping, large-file workloads, network access, and cold storage are not covered. Views have explicit reader lifetimes. Whole-file residency and mmap setup are not free. End-to-end language-loader measurements are reported separately in the access-loader run.
