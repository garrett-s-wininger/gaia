# Compile-heavy correctness checks

One separately prepared observation per engine/scenario; these are work-count and artifact checks, not performance conclusions. The previous incremental path, shared-tree path and shared-tree-plus-memo path all pass.

| Scenario | Compilers per engine | Reused fragments | New fragments | Shared/memo validation trees | Shared/memo total trees |
| --- | ---: | ---: | ---: | ---: | ---: |
| Real high-fanout header | 26 | 5 | 26 | 1 | 27 |
| Changed global flags | 31 | 0 | 31 | 0 | 31 |
| Clean build | 31 | 0 | 31 | 0 | 31 |

All nine libraries and 279 object identities match independent CLI references, with successful runtime probes, expected compile/link work and fragment counts. The high-fanout case builds one shared validation tree plus 26 private compiler trees. Flag and clean requests have no reusable action candidates and build 31 private compiler trees; sharing does not pretend to remove compilation.

[Validation](boundary-validation.json) binds ignored `boundary-raw/results.json`; [summary](boundary-summary.json) retains counters. The main comparison and sharing pilot together add 378 libraries and 11,718 object checks: 387 libraries and 11,997 object checks across the three runs. Counts include repeated validation of retained objects on no-ops, not that many unique compilations.
