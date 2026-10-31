# What prepared test workflows should establish next

The [first results](findings.md) demonstrate existing SQLite and JUnit mechanisms with generated fixtures. Broaden the workload before building a replacement runner or fixture service.

## Use production suites with complete setup costs

Choose a project whose tests actually spend meaningful time on migrations, fixtures or discovery. Retain its existing runner and competent caching controls. Measure first admission, repeated requests, parallel work, cleanup and memory together. The current half-megabyte SQLite fixture and 40 generated JUnit classes do not establish production scale.

## Preserve the isolation contract

Rollback cannot isolate committed writes or external effects. Compare private database clones with rollback only where tests permit both, and include a server-backed database if it is part of the selected workload. Track fixture version changes and interrupted cleanup. Copying a prepared database is a useful baseline; it does not establish copy-on-write performance.

## Share discovery without freezing dynamic tests

JUnit already supports discovery and execution through a shared plan. Test actual editor/sharding/reporting consumers against that API before adding a protocol. Dynamic tests appear during execution; unchanged class files alone do not validate classpath resources, engines, extensions or environment. Any retained-plan interface needs those observations and explicit invalidation, with discovery-only and complete-run clocks separated.
