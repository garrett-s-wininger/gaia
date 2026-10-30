# Django filesystem and execution diagnostics

Parent application run: `20261029T014251.176632Z`.

One trace and one separate profile per bytecode REST reader. The unchanged app worker is wrapped by django_probe.py, which marks/enables instrumentation at the first workload clock and stops it at the sixth. All seven main clock calls are checked. Common wrapper/profiler stdlib imports can change host import state. Traces were collected concurrently; profiles were collected separately in sequence. Neither instrumented wall time nor strace syscall durations are used as ordinary timings or cycle estimates. App/import/code validation remains enabled.

## Workload filesystem activity

| Reader | All metadata calls | All opens | All reads | Dependency-input metadata | Dependency-input opens | Dependency-input reads | Host opens | Host reads |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| directory-stock | 3010 | 856 | 1450 | 2101 | 574 | 948 | 268 | 488 |
| directory | 3018 | 896 | 1464 | 2086 | 604 | 944 | 276 | 504 |
| python | 1030 | 289 | 515 | 113 | 3 | 7 | 270 | 492 |
| odin | 1029 | 290 | 514 | 111 | 3 | 5 | 270 | 492 |

Dependency input includes the root/archive and its sidecar; the Odin shared extension is categorized separately. Host paths include pure-Python stdlib sources/bytecode, native modules and shared libraries. The project fixture is separate. These calls occur inside application initialization/checks/DB-fixture/API/admin workload, excluding common worker preparation and final correctness checks. Read bytes are returned syscall bytes, not physical storage traffic or mmap payload bytes.

## Disjoint profile self time

Instrumented milliseconds; all buckets are exclusive and sum to the profile total. Do not use them as partitions of earlier unprofiled medians.

| Bucket | Directory | Python bundle | Odin bundle |
| --- | ---: | ---: | ---: |
| Bundle provider | 0.000 | 52.216 | 27.422 |
| Bytecode decoding | 88.673 | 76.358 | 75.678 |
| C filesystem primitives | 49.309 | 18.489 | 17.157 |
| Class construction | 31.593 | 27.785 | 27.535 |
| Django code | 85.642 | 80.806 | 84.349 |
| Import machinery | 91.947 | 78.455 | 75.190 |
| Other stdlib/runtime | 151.776 | 186.291 | 184.132 |
| Project fixture | 0.662 | 0.599 | 0.607 |
| REST/filter code | 3.718 | 4.003 | 3.916 |
| ZIP/module enumeration | 0.844 | 45.025 | 44.900 |

## Selected Odin profile functions

Inclusive values overlap other functions/buckets; do not add them. These are hypotheses for the next uninstrumented comparison, not promised time savings.

| Function | Calls | Self ms | Inclusive ms |
| --- | ---: | ---: | ---: |
| <built-in method marshal.loads> | 578 | 75.678 | 75.678 |
| <built-in method builtins.__build_class__> | 2034 | 27.535 | 104.122 |
| _read_directory | 1 | 25.621 | 64.554 |
| iter_zipimport_modules | 77 | 17.056 | 35.977 |

The native payload reader already uses mapped memory. Remaining dependency-related reads include a second ZIP-directory pass through stock zipimport, and pkgutil enumeration still scans its file table. An index-backed path-entry finder/iter_modules implementation is the next candidate. Residual host-runtime imports and bytecode/class reconstruction are separate costs; warm page cache does not eliminate filesystem operations or Python object construction. Inspect raw counts/function records before treating native byte access as the full startup path.
