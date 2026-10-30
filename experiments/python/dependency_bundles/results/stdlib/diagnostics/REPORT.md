# Stdlib snapshot filesystem diagnostics

Parent run: `20261029T034650.363732Z`.

One separate trace per provider; identical application and source-inspection checks pass. The wrapper validates all seven worker clock calls and records only the application workload, including mounts and manifest validation. Common interpreter/harness preparation and post-workload source inspection are excluded. Import state/code-read counts match the uninstrumented run. No trace timing is used as a benchmark.

| Provider | Total metadata | Total opens | Total reads | Host pyc opens/reads | Host source opens/reads | Snapshot payload/index opens/reads |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| host | 930 | 289 | 509 | 118 / 236 | 118 / 234 | 0 / 0 |
| directory | 335 | 161 | 279 | 0 / 0 | 0 / 0 | 119 / 238 |
| python | 221 | 44 | 43 | 0 / 0 | 0 / 0 | 2 / 2 |
| odin | 219 | 44 | 41 | 0 / 0 | 0 / 0 | 2 / 0 |

Metadata includes failed path probes. Opens/reads count calls, including EOF reads. The descriptor is counted separately in JSON and totals. Snapshot payload/index includes the manifest. Mapped access still incurs page faults/page-cache work; zero read syscalls does not mean zero storage traffic. Remaining shared libraries, directory enumeration, project and dependency inputs retain their ordinary paths. Raw per-group syscall counts and byte totals are in results.json.
