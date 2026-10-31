# Shared parsing versus separate parallel workers

One initialized Clang worker shares a frontend between code generation and a detached-name analysis. The stronger control uses two initialized workers: one parses for analysis while the other compiles, either sequentially or concurrently. The analysis hashes declaration names and counts a selected digest predicate; it is a deliberately small surrogate, not a production linter.

Three randomized blocks verify all 24 object outputs and analysis results. Time is the complete host-request operation; CPU is sampled for both child processes outside its clock using Linux process counters (10 ms tick granularity on the measured host).

| Translation unit | Arrangement | Median wall, ms | Sampled process CPU, ms |
| --- | --- | ---: | ---: |
| common/zstd_common.c | independent-serial | 94.19 | 90 |
| common/zstd_common.c | independent-parallel | 51.95 | 100 |
| common/zstd_common.c | shared-serial | 51.13 | 50 |
| common/zstd_common.c | shared-parallel | 54.76 | 50 |
| compress/zstd_lazy.c | independent-serial | 4136.63 | 4130 |
| compress/zstd_lazy.c | independent-parallel | 4027.64 | 4120 |
| compress/zstd_lazy.c | shared-serial | 4129.44 | 4120 |
| compress/zstd_lazy.c | shared-parallel | 3938.37 | 3940 |

For the small TU, shared serial work and independent parallel work have nearly equal wall time. Sharing reduces sampled CPU from about 100 to 50 ms against the parallel control; merely moving the tiny detached analysis to another thread does not establish a latency win. Comparing only with independent sequential parsing would overstate the wall-time result. For the heavy TU, several seconds of backend work dominate the tens of milliseconds potentially saved by frontend sharing; three blocks do not establish a broad latency advantage.

Threads never concurrently traverse Clang's mutable/lazy AST. A consumer detaches immutable declaration-name records while the AST is alive, then independent analysis can overlap the backend. The result supports a narrow shared-facts boundary; arbitrary AST passes, compiler versions and language frontends are not interchangeable.

Both worker processes stay alive throughout this control, including an idle analysis worker in shared modes. Recorded RSS samples therefore do not establish a one-worker memory saving or peak/PSS bound. Host and relevant implementation identities are checked before/after. [Reproduction and limits](../../README.md).
