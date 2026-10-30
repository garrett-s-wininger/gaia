# Odin binary-index access experiment

Run: `20261028T221649.126132Z`.

Linux, warm/reused filesystem cache, fresh process per observation. All cases in a corpus consume identical payloads from the same ZIP or an exact materialization. No module compilation, imports or application initialization is performed. This is a native data-access experiment, not an Odin integration into CPython or a new end-to-end language-loader result.

## Methods

- Odin is built with `-o:speed`, bounds checks retained, as an object file, then linked with the installed C driver and system zlib/OpenSSL. The local Odin executable expects absent Clang for automatic linking; no compiler/dependency download was needed. Build commands/version/hash are recorded in results.json. Executable bootstrap primes SHA/CRC once, outside access setup; process wall includes bootstrap, library/runtime startup, validation, cleanup and output.
- `index`: mmap the pinned binary sidecar and bundle; validate header/tables/UTF-8/ranges; retain offsets into the table/string pool. No per-entry Entry objects are built. The basename position array and directory views are built at setup because names are variable length.
- `named`: construct full names and a native name-to-entry map during setup, then look up each name in the timed loop. This is the closest comparison to Python's named-read API. `ordinal`: request entries by stable row number, bypassing name-map construction/lookup. It is a different access API and must not be credited solely to the implementation language.
- `zip`: additionally rebuild entry ranges from central/local ZIP headers and compare every name/range/size/CRC to the certified manifest. This is a controlled stored-ZIP parser: ordered central entries, no ZIP64/multipart/encryption/descriptors/compression or non-ASCII CP437. It uses the pinned sidecar as a certified request manifest, so it is not an independent general ZIP-reader baseline and its startup includes that manifest loading too.
- `directory`: known-file requests from that same pinned manifest; build full C paths during setup. Each read opens, fstats, reads the exact bytes and closes the file. No directory walk or dependency discovery is charged. CRC is checked against the manifest. There is no whole-directory hash/stat admission at setup; this baseline favors known inputs.
- `bytes`: allocate/copy/release a payload buffer per request in both native file and bundle readers. `view`: use mapped payload slices, with no per-read payload allocation. Python bytes likewise copy and views avoid copying, but Python still uses its existing Entry/dictionary reader.
- Every payload read verifies CRC using system zlib in both implementations. Sidecar SHA-256 is pinned by the parent and checked at every setup. `hash` verifies bundle SHA-256 per open; `local` compares dev/inode/size/mtime/ctime from producer admission in a trusted immutable local store. All archive setups compare fstat identity again after loading. Stat checks are cache invalidation, not authentication. Mutation/truncation during mapped access is unsupported.
- Full member SHA-256 checks happen after timed scans. Odin reports SHA-256 of concatenated per-member SHA-256 digests in physical/lexical fixture order; the parent independently checks it against Python's expected payloads. Python checks each member against expected SHA-256.

15 randomized trials per case, four lexical scans per process, plus one warmup. Medians in ms. First-use median is taken from each setup + first-pass sample, not a sum of independent medians. Reused scan is each process's mean of scans 2–4, then median.

| Corpus | Implementation | Reader | Binding | Result | Lookup | Setup ms | First scan ms | Reused scan ms | First use ms | First use p95 ms | Process wall ms |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| source | odin | index | hash | bytes | named | 1.225 | 0.476 | 0.465 | 1.711 | 2.582 | 9.050 |
| source | odin | index | hash | bytes | ordinal | 0.732 | 0.422 | 0.416 | 1.140 | 3.121 | 8.225 |
| source | odin | index | hash | view | named | 1.179 | 0.368 | 0.369 | 1.560 | 1.795 | 8.750 |
| source | odin | index | hash | view | ordinal | 0.691 | 0.328 | 0.328 | 1.020 | 1.118 | 7.455 |
| source | odin | index | local | bytes | named | 0.598 | 0.537 | 0.421 | 1.134 | 1.595 | 8.181 |
| source | odin | index | local | bytes | ordinal | 0.133 | 0.516 | 0.416 | 0.647 | 0.741 | 7.345 |
| source | odin | index | local | view | named | 0.564 | 0.444 | 0.368 | 1.008 | 1.329 | 8.133 |
| source | odin | index | local | view | ordinal | 0.136 | 0.430 | 0.338 | 0.567 | 0.682 | 7.422 |
| source | odin | zip | hash | bytes | named | 1.618 | 0.449 | 0.446 | 2.094 | 3.302 | 10.140 |
| source | odin | zip | hash | view | named | 1.456 | 0.357 | 0.372 | 1.824 | 3.144 | 8.606 |
| source | odin | zip | local | bytes | named | 1.051 | 0.466 | 0.438 | 1.504 | 2.298 | 8.564 |
| source | odin | zip | local | view | named | 0.961 | 0.373 | 0.371 | 1.351 | 1.915 | 8.107 |
| source | odin | directory | manifest | bytes | named | 0.990 | 17.228 | 15.995 | 18.274 | 25.534 | 88.393 |
| source | python | index | hash | bytes | named | 3.932 | 1.754 | 1.734 | 5.989 | 8.345 | 125.405 |
| source | python | index | hash | view | named | 3.817 | 1.655 | 1.669 | 5.712 | 11.133 | 123.435 |
| source | python | index | local | bytes | named | 3.032 | 1.949 | 1.780 | 4.906 | 7.068 | 126.362 |
| source | python | index | local | view | named | 3.416 | 1.775 | 1.600 | 5.140 | 9.296 | 130.935 |
| bytecode | odin | index | hash | bytes | named | 1.746 | 0.755 | 0.730 | 2.541 | 3.149 | 11.656 |
| bytecode | odin | index | hash | bytes | ordinal | 1.255 | 0.744 | 0.690 | 2.043 | 2.125 | 10.913 |
| bytecode | odin | index | hash | view | named | 1.694 | 0.616 | 0.657 | 2.364 | 2.828 | 11.104 |
| bytecode | odin | index | hash | view | ordinal | 1.273 | 0.616 | 0.595 | 1.937 | 2.215 | 10.503 |
| bytecode | odin | index | local | bytes | named | 0.641 | 1.174 | 0.750 | 1.775 | 2.820 | 10.976 |
| bytecode | odin | index | local | bytes | ordinal | 0.135 | 0.975 | 0.715 | 1.173 | 1.517 | 9.685 |
| bytecode | odin | index | local | view | named | 0.618 | 0.964 | 0.643 | 1.659 | 2.104 | 10.042 |
| bytecode | odin | index | local | view | ordinal | 0.139 | 0.856 | 0.587 | 1.012 | 1.546 | 9.638 |
| bytecode | odin | zip | hash | bytes | named | 1.979 | 0.770 | 0.722 | 2.752 | 3.322 | 11.181 |
| bytecode | odin | zip | hash | view | named | 2.069 | 0.615 | 0.642 | 2.693 | 3.041 | 11.348 |
| bytecode | odin | zip | local | bytes | named | 1.355 | 0.877 | 0.783 | 2.376 | 3.686 | 11.273 |
| bytecode | odin | zip | local | view | named | 1.203 | 0.642 | 0.647 | 1.880 | 3.251 | 10.052 |
| bytecode | odin | directory | manifest | bytes | named | 0.966 | 16.084 | 16.161 | 17.090 | 20.105 | 89.232 |
| bytecode | python | index | hash | bytes | named | 4.734 | 2.238 | 2.021 | 7.419 | 12.372 | 123.260 |
| bytecode | python | index | hash | view | named | 4.799 | 2.480 | 1.983 | 7.444 | 11.819 | 134.995 |
| bytecode | python | index | local | bytes | named | 3.278 | 2.473 | 2.223 | 6.165 | 10.449 | 136.506 |
| bytecode | python | index | local | view | named | 3.236 | 2.417 | 1.954 | 5.667 | 7.640 | 129.511 |
| 1 MiB entries | odin | index | hash | bytes | named | 45.355 | 32.020 | 29.392 | 76.333 | 90.528 | 215.136 |
| 1 MiB entries | odin | index | hash | bytes | ordinal | 45.006 | 31.189 | 31.193 | 76.758 | 85.256 | 222.454 |
| 1 MiB entries | odin | index | hash | view | named | 44.631 | 23.255 | 23.735 | 68.795 | 76.419 | 189.668 |
| 1 MiB entries | odin | index | hash | view | ordinal | 44.595 | 23.860 | 23.851 | 68.689 | 75.024 | 190.078 |
| 1 MiB entries | odin | index | local | bytes | named | 0.071 | 32.280 | 29.001 | 32.342 | 39.914 | 167.856 |
| 1 MiB entries | odin | index | local | bytes | ordinal | 0.048 | 33.362 | 29.361 | 33.404 | 45.806 | 173.512 |
| 1 MiB entries | odin | index | local | view | named | 0.062 | 27.787 | 24.185 | 27.840 | 31.413 | 148.461 |
| 1 MiB entries | odin | index | local | view | ordinal | 0.053 | 26.543 | 23.415 | 26.583 | 32.325 | 145.480 |
| 1 MiB entries | odin | zip | hash | bytes | named | 45.148 | 31.574 | 29.040 | 76.594 | 87.105 | 214.760 |
| 1 MiB entries | odin | zip | hash | view | named | 44.828 | 23.203 | 23.228 | 67.696 | 80.452 | 185.949 |
| 1 MiB entries | odin | zip | local | bytes | named | 0.466 | 34.324 | 30.153 | 34.748 | 36.635 | 172.576 |
| 1 MiB entries | odin | zip | local | view | named | 0.436 | 27.636 | 23.862 | 28.042 | 30.515 | 148.250 |
| 1 MiB entries | odin | directory | manifest | bytes | named | 0.065 | 33.285 | 30.416 | 33.348 | 35.175 | 178.161 |
| 1 MiB entries | python | index | hash | bytes | named | 49.654 | 33.104 | 27.870 | 83.947 | 92.473 | 347.004 |
| 1 MiB entries | python | index | hash | view | named | 48.509 | 27.089 | 24.325 | 76.494 | 93.975 | 326.176 |
| 1 MiB entries | python | index | local | bytes | named | 0.330 | 34.367 | 28.285 | 34.755 | 42.729 | 310.345 |
| 1 MiB entries | python | index | local | view | named | 0.295 | 28.165 | 24.322 | 28.439 | 30.754 | 283.174 |

## Inputs and limits

- source: 2,104 entries, 429,600 payload bytes; ZIP SHA-256 `2e6c927afac97a19d75a51022083274fa816175abd2c7cacf837fcbc0fcec6db`, index SHA-256 `b2fc8a1c6756488b247b7edaf91237b93ceae8304def78d0fce5dff0bf82022d`.
- bytecode: 2,104 entries, 1,107,434 payload bytes; ZIP SHA-256 `43385c852e7f0351bc0557d88020f5a226628d2c3c085887455b9e3440a54805`, index SHA-256 `0039b77ec0c78238e92754e1c518faa2b6f70ee450def1c0e954c67faa147fcd`.
- 1 MiB entries: 64 entries, 67,108,864 payload bytes; ZIP SHA-256 `caa6c7308dbcae6ffd033293bd17ab4b772b283b620324d9e003f0037078f1ae`, index SHA-256 `44cea499eb0bed1292c9d3f88df9174ecbb2d239f0bdd66f15df14c534e1877a`.

The existing binary encoding is unchanged. Producer validation/index creation occurs before consumer timing and is recorded separately; materialization cost is recorded too. Known-path directory reading is compared with mapped views and copied bytes separately. This experiment does not test real dependency startup, random/sparse requests, memory pressure, cold storage, remote exchange or an Odin-only crypto/CRC implementation. Native RSS and syscall counts are not measured. Odin named lookups remain eager; ordinal scans do not establish a generic path-lookup floor. Neither microbenchmark speed ratios nor native process-wall timings can be substituted for the previous CPython module-loading measurements.
