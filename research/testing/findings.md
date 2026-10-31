# Sharing preparation in test workflows

The first passes establish reusable boundaries with real SQLite and JUnit APIs, using generated fixtures. They do not establish production-suite speedups or a new test-runner architecture.

## Prepared SQLite fixtures remove repeated schema work

The fixture has twelve tables, twelve thousand seed rows and twelve indexes, serialized into 495,616 bytes. Three blocks each run sixteen independent test operations with one or four workers. Every operation changes private rows, adds a current-request value, asserts it and rolls back; injected SQL failures must also leave the fixture intact.

| Mode | Workers | Complete charged session median |
| --- | ---: | ---: |
| replay | 1 | 355.5 ms |
| backup | 1 | 27.4 ms |
| deserialize | 1 | 24.5 ms |
| rollback | 1 | 26.3 ms |
| replay | 4 | 1305.1 ms |
| backup | 4 | 38.4 ms |
| deserialize | 4 | 43.7 ms |
| rollback | 4 | 36.6 ms |

Prepared modes include necessary seed construction and teardown; deserialize additionally charges serialized-image construction. Required private connection closes and executor shutdown are included. Full logical-dump correctness oracles are separate from performance clocks. Replay does not pay for a template constructed only as the harness's independent oracle.

The gain comes from amortizing construction over sixteen tests. Copying a prepared database is not copy-on-write, and the fixture is only about half a megabyte. The four-worker replay result also includes this SQLite/Python workload's contention; it does not imply that parallel test execution is generally slower. No PostgreSQL server or physical storage/durability behavior is measured.

Rollback requires a narrower contract than cloning: a test cannot commit the fixture transaction or depend on external effects. A negative control proves committed changes escape rollback. Isolated backup/deserialize copies allow independent database transactions but still do not restore filesystem or network side effects. Three database tests cover success/error recovery, parallel private state and commit escape.

## JUnit already supports sharing a discovered plan

Forty generated test classes contain four hundred ordinary tests plus dynamic factories. A request discovers between forty and one hundred twenty additional dynamic tests during actual execution. Three consumers enumerate stable discovered IDs and verify deterministic shard coverage; then the plan executes real tests.

| Arrangement | Complete fresh-process median |
| --- | ---: |
| independent | 1679 ms |
| independent-parallel | 1564 ms |
| shared | 1505 ms |
| direct | 1443 ms |

Five blocks execute 9,440 measured tests successfully, with changing dynamic counts. One shared plan improves on three redundant discovery operations, including the concurrent control. The existing direct JUnit API remains the faster lower-work control; it does not supply the three pre-execution consumer views. We have demonstrated useful existing API composition, not a novel discovery algorithm or a win over a competent single runner.

Dynamic leaves appear during execution and cannot be fully pre-sharded from discovery alone. Changed, added and removed class files invalidate the external input-generation guard. That check runs outside process clocks and is not a complete persistent-plan invalidation protocol for arbitrary classpath resources, engines or extensions. The prototype uses one process per request and shares objects within it, not across JVMs or machines.

Read the [reproduction guide](../../experiments/testing/managed/README.md) and [run index](experiments.json). The database and discovery summaries record exact raw hashes, preparation boundaries and successful-operation evidence.
