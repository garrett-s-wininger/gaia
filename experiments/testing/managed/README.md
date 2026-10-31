# Share test preparation and discovery

These are bounded research probes, not a replacement test service. The database workload is synthetic; discovery uses the real JUnit Jupiter engine with generated tests.

## Database fixtures

`database.py` compares replaying a schema/fixture SQL script for each test, copying a prepared SQLite database through the backup API, restoring a serialized database, and retaining one prepared connection per worker with transaction rollback. Every worker has private mutable state. Backup and deserialize copy data; neither is copy-on-write.

The ordinary operation includes setup, SQL updates/insertion/assertions, rollback and required connection close. The complete session includes executor startup/shutdown and final retained-connection teardown. Prepared modes additionally charge their necessary seed construction; deserialize also charges image creation. An independently constructed template/image used by the harness for correctness is outside the replay timer and is not a necessary replay cost. Full logical-dump equality is checked in preflight and unit tests, outside performance measurements. Timed operations check current private row values and counts.

Rollback is a narrower contract: test code cannot commit the fixture transaction or depend on external side effects. A negative test proves that a committed escape is not repaired by rollback. Failure injection exercises SQL errors; it does not simulate process death or database-server failure. No PostgreSQL measurement is claimed.

```sh
python3 -B -m unittest discover -s experiments/testing/managed -p 'test_*.py'
python3 experiments/testing/managed/database.py \
  --output experiments/testing/managed/results/database \
  --tables 12 --rows 1000 --tasks 16 --workers 1 4 --trials 3
```

## JUnit discovery

`discovery.py` generates 40 Java test classes, each with ten ordinary methods and one dynamic-test factory. The dynamic count changes across measured requests. Three consumers enumerate test IDs and produce deterministic shard coverage; the last plan executes real tests.

Compare independent sequential discovery, independent concurrent discovery and one plan shared by the three consumers. The `direct` control uses JUnit's existing execute-request API and has no three pre-execution consumer views, so it is a useful lower-work baseline rather than the equal-output comparison. Sharing a `TestPlan` is an existing JUnit capability, not a new Gaia invention.

Dynamic tests are created during execution and are not available as discovered leaf IDs for advance sharding. Compiled-class identities are checked before each fresh process, with changed/added/removed class negative controls. This is an external admission guard, not a durable plan invalidation implementation or proof for arbitrary classpath dependencies.

Provide a JDK 25 and `junit-platform-console-standalone-1.14.1.jar` (Jupiter 5.14.1). The artifact can be obtained from Maven Central; its exact SHA-256 is recorded in the raw result. Acquisition and fixture compilation are preparation, not process startup.

```sh
python3 experiments/testing/managed/discovery.py \
  --jdk "$JDK" --junit "$JUNIT_STANDALONE" \
  --work "$WORK/junit" \
  --output experiments/testing/managed/results/discovery --trials 5
```

The fixture generators, preparation and measured boundaries are intentionally visible. Results cannot be generalized to a production suite with database servers, containers, expensive application bootstraps or arbitrary JUnit extensions without further tests.

References: [SQLite backup](https://www.sqlite.org/backup.html), [Python SQLite API](https://docs.python.org/3/library/sqlite3.html), [JUnit Launcher API](https://docs.junit.org/5.14.1/advanced-topics/launcher-api.html).
