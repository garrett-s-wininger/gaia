# CPython/Odin bridge diagnosis

Run: `20261029T020824.661458Z`.

Existing reader/library implementations, exact Django REST dependency-code request traces. Both named APIs return owned Python bytes with payload CRC verification. No module execution, compilation or Django initialization is timed. No native kernel or bridge optimization is introduced. The Python reader delegates mapping, CRC and copying to native runtime libraries.

15 fresh processes per corpus, warm filesystem cache. Both readers open once in randomized order within each process. Read variants are interleaved in randomized blocks after warmup. Each block repeats the entire trace; reported scans are normalized by repeat count, then median within each process and across fresh processes. Setup is reported separately. CPU observations and all raw blocks are retained. The separate Odin ordinal variant bypasses the Python name/wrapper API and is a diagnostic, not a named-provider comparison.

| Input | Requests | Payload MiB | Python open ms | Odin open ms | Python named scan ms | Odin named scan ms | Odin ordinal scan ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| source | 460 | 4.601 | 8.472 | 3.671 | 2.370 | 2.056 | 1.938 |
| bytecode | 460 | 5.764 | 7.629 | 3.452 | 2.779 | 2.442 | 2.349 |

The common Python request loop/checksum is included in every scan. Constructor profiles are separate instrumented observations and must not be used as subdivisions of unprofiled timings. This test measures bridge-inclusive reads, not a pure ABI-only call cost. It cannot by itself prove that startup differences are ABI overhead or inefficient Odin codegen. Read loops follow validation/warmup, so they exclude first-touch payload page faults and are not a partition of application startup. Natural full-application timings remain in the parent Django report.
