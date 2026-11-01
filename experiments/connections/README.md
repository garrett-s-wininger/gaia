# Native facts, ownership and source discovery

These experiments test connections between native tool internals, incremental data maintenance, runtime isolation and source/test evidence. Start with the [findings](../../research/connections/findings.md), [next questions](../../research/connections/prospects.md) and [run index](../../research/connections/experiments.json). The broader [connection map](../../research/connections/connections.md) contains hypotheses, not additional measured gains.

The implementations retain their own directories so that source pins, reproduction paths and measured input identities remain stable.

| Implementation and reproduction | Comparison | Correctness boundary |
| --- | --- | --- |
| [Pass formulations](../pass_algebra/README.md) | Worklist, Boolean sweep and per-value SSA liveness | Independent fixed-point oracle and LLVM extraction fixtures |
| [Retained facts](../pass_algebra/retained/README.md) | LLVM use lists versus a compact shared def-use representation | Immutable results, invalidation and two equivalent consumers |
| [Backend policy](../backend_policy/README.md) | Stock development settings and cheaper machine passes | Identical optimized IR where required; equivalent current-edit compressed frames and byte-exact round trips |
| [Source deltas](../delta_analysis/README.md) | Public native rebuild/cache, retained native parsing and extra proof maintenance | Fresh Grimp graph, unmodified Import Linter contract, current witnesses and randomized graph checks |
| [Namespace rebinding](../import_rebinding/README.md) | Full rescans, scoped native parsing and complete retained references | Fresh native graph and observed-name/absence index consistency |
| [Branched test state](../branched_tests/README.md) | Fresh tests, native database reuse, private fixture copies, warm and forked workers | Same upstream test bodies, source/settings invalidation, heap/file isolation and interrupted cleanup |
| [Discovery and validation](../discovery_validation/README.md) | Native testmon with and without an exported source/evidence view | Same native selections/outcomes, full-suite failure sets, stale-result rejection and separate coverage oracle |

The [compiler integration](../integration/README.md) measures shared build/fact consumers, bounded backend handoffs and CPU controls separately. Its timings are not pooled with these studies.

Reproduction uses prepared, pinned upstream inputs and caller-owned work directories. Each guide identifies its environment, native helpers, acquisition, clock and limitations. Generated tools, source copies, virtual environments, observations and profiler traces remain ignored. Reports, summaries, acquisition records, validation and provenance are retained; [the evidence manifest](../../research/evidence.json) verifies locally available raw data by size and SHA-256.

After importing or reorganizing this work, run the focused tests named in the individual guides and `python3 -B tools/check_repository.py`. Documentation cleanup does not require rerunning historical timing matrices. A change to producer, consumer, toolchain or validity semantics needs new evidence rather than replacing the old measurement silently.
