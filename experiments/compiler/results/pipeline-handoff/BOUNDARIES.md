# Compile-heavy correctness checks

One observation per engine/scenario, independently prepared from baseline state. These are correctness checks, not timing conclusions.

| Scenario | Compilers per engine | Reused fragments | New fragments | Validation trees | Total trees |
| --- | ---: | ---: | ---: | ---: | ---: |
| High-fanout header | 26 | 5 | 26 | 1 | 27 |
| Changed flags | 31 | 0 | 31 | 0 | 31 |
| Clean build | 31 | 0 | 31 | 0 | 31 |

Previous memo, inline snapshot and resident paths all pass: nine libraries and 279 object identities match independent CLI references and runtime probes. Native launch counts are two, one and zero respectively on these already-started resident requests. The resident seed includes startup; native per-request pools and filesystems are released before acknowledgement. Five resident requests (two seeds and three observations) exercise repeated full compilation/linking within one process.

[Validation](boundary-validation.json) binds ignored `boundary-raw/results.json`; [summary](boundary-summary.json) retains native/request counters, source pins and resident high-water observations.
