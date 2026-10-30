# Django filesystem and execution diagnostics

Parent application run: `20261029T025706.004897Z`.

One trace and one separate profile per bytecode REST reader. The unchanged app worker is wrapped by django_probe.py, which marks/enables instrumentation at the first workload clock and stops it at the sixth. All seven main clock calls are checked. Common wrapper/profiler stdlib imports can change host import state. Traces were collected concurrently; profiles were collected separately in sequence. Neither instrumented wall time nor strace syscall durations are used as ordinary timings or cycle estimates. App/import/code validation remains enabled.

## Workload filesystem activity

| Reader | All metadata calls | All opens | All reads | Dependency-input metadata | Dependency-input opens | Dependency-input reads | Host opens | Host reads |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| directory | 3018 | 896 | 1464 | 2086 | 604 | 944 | 276 | 504 |
| python-legacy | 1030 | 289 | 515 | 113 | 3 | 7 | 270 | 492 |
| python-index | 931 | 288 | 510 | 14 | 2 | 2 | 270 | 492 |
| odin-legacy | 1029 | 290 | 514 | 111 | 3 | 5 | 270 | 492 |
| odin-index | 930 | 289 | 509 | 12 | 2 | 0 | 270 | 492 |

Dependency input includes the root/archive and its sidecar; the Odin shared extension is categorized separately. Host paths include pure-Python stdlib sources/bytecode, native modules and shared libraries. The project fixture is separate. These calls occur inside application initialization/checks/DB-fixture/API/admin workload, excluding common worker preparation and final correctness checks. Read bytes are returned syscall bytes, not physical storage traffic or mmap payload bytes.

## Disjoint profile self time

Instrumented milliseconds; all buckets are exclusive and sum to the profile total. Do not use them as partitions of earlier unprofiled medians.

| Bucket | directory | python-legacy | python-index | odin-legacy | odin-index |
| --- | ---: | ---: | ---: | ---: | ---: |
| Bundle provider | 0.000 | 67.391 | 51.057 | 31.949 | 32.191 |
| Bytecode decoding | 98.224 | 102.501 | 110.672 | 92.369 | 92.693 |
| C filesystem primitives | 47.990 | 22.198 | 17.367 | 18.865 | 15.758 |
| Class construction | 35.690 | 31.051 | 32.454 | 30.509 | 29.452 |
| Django code | 112.701 | 88.548 | 103.491 | 92.712 | 92.997 |
| Import machinery | 97.714 | 83.739 | 71.706 | 83.753 | 71.822 |
| Other stdlib/runtime | 185.399 | 201.602 | 167.041 | 199.161 | 174.497 |
| Project fixture | 1.214 | 0.858 | 0.788 | 0.627 | 0.588 |
| REST/filter code | 5.147 | 4.940 | 4.706 | 5.676 | 3.994 |
| ZIP/module enumeration | 1.217 | 49.119 | 0.331 | 51.761 | 0.394 |

## Selected Odin profile functions

Inclusive values overlap other functions/buckets; do not add them. Profiler activation counts include generator resumptions, not just distinct enumeration requests. These are hypotheses for the next uninstrumented comparison, not promised time savings.

| Function | Calls | Self ms | Inclusive ms |
| --- | ---: | ---: | ---: |
| <built-in method marshal.loads> | 578 | 92.693 | 92.693 |
| <built-in method builtins.__build_class__> | 2034 | 29.452 | 115.912 |

Indexed discovery must show no _read_directory or iter_zipimport_modules activations for the controlled app. Direct-child iteration still yields lazily: its profiler activation count includes resumptions; the worker counter records distinct requests. Residual host imports and Python runtime initialization are unchanged. Compare the uninstrumented parent report for speed, not these diagnostic times.
