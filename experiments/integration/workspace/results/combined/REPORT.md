# Sharing current compiler observations with a real query consumer

The fixture builds all 33 production Ninja translation units and runs project declaration-record queries against the same admitted generation. Independent cached consumers run concurrently; Ninja + ccache has a separate cached index consumer. Each row is a median of three blocks on one laptop.

| Operation | Shared complete | Independent complete | Ninja + ccache complete | Shared editor | Independent editor |
| --- | ---: | ---: | ---: | ---: | ---: |
| noop | 17.19 ms | 25.14 ms | 22.34 ms | 17.17 ms | 21.68 ms |
| source | 535.19 ms | 529.07 ms | 653.02 ms | 535.17 ms | 240.96 ms |
| rewire | 550.92 ms | 530.64 ms | 618.74 ms | 550.89 ms | 226.78 ms |
| old header | 20.98 ms | 23.57 ms | 20.59 ms | 20.96 ms | 22.87 ms |
| new header | 518.98 ms | 552.65 ms | 649.71 ms | 518.94 ms | 250.92 ms |
| optional appear | 545.60 ms | 515.98 ms | 631.78 ms | 545.57 ms | 230.97 ms |
| optional remove | 541.24 ms | 532.40 ms | 345.88 ms | 541.20 ms | 238.88 ms |
| shadow | 574.43 ms | 526.03 ms | 645.32 ms | 574.39 ms | 233.73 ms |
| unrelated | 20.81 ms | 27.40 ms | 20.81 ms | 20.77 ms | 26.30 ms |
| header | 5468.37 ms | 7002.23 ms | 6025.67 ms | 5468.32 ms | 2771.78 ms |
| configuration | 28392.31 ms | 30211.87 ms | 14427.05 ms | 28392.28 ms | 16960.94 ms |
| burst | 518.09 ms | 540.71 ms | 658.18 ms | 518.07 ms | 235.96 ms |

A final-current editor result and a completed executable have different readiness times. The first shared controller publishes only after compilation and linking; earlier handoff is not implemented. An independent query can finish while the build continues. Full physical CLI objects, depfiles and executables, and uncached physical syntax/index results validate every operation. The burst rejects stale generations but does not cancel an already-running compiler pass.

Noop/unchanged targets reuse validated facts and objects. Include rewiring refreshes observations even if an IR hit is possible; debug metadata can make a nominally equivalent include change alter object bytes. The configuration case uses a new context and conservatively reparses all targets. The exact-input cache remains an important baseline.

Ninja receives an explicit single-probe-TU invalidation hint for optional-header appearance/removal and include shadowing. This fixture adapter is charged inside the operation; ccache uses preprocessor mode for these events after a stale direct hit was rejected. This is not a generic negative-dependency importer. Each trace restores a baseline-only ccache seed. Physical input edit application, native admission, scanning, queries, compilation and required linking are timed. Initial preparation, reference builds, warmup and correctness reads are outside those clocks and separately recorded.

Worker memory values are current samples, not peaks or enforced budgets. CPU sums coarse persistent-host ticks with controller and completed-child usage. No dependency-aware retention policy, multiple in-flight immutable generations or concurrent mutable Clang AST sharing is implemented.

[Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), [reproduction](../../README.md).
