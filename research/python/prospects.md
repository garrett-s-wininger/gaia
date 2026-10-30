# Where Python research could go next

Python research is paused while the independent compiler track develops. Reopen it for a specific unanswered question rather than another tiny improvement to the same fixture.

## Measure an actual developer tool

Choose a real tool whose fixed operation loads many modules. Pin its inputs, compare ordinary and indexed/bundled loading, validate the operation and include startup/shutdown plus preparation/materialization costs. This would tell us more than another synthetic catalog size alone.

## Pick a concrete compatibility gap

Native wheels, namespace packages, package metadata/entry points and editable dependencies need explicit behavior. Establish supported/rejected cases before claiming a general dependency format. Measure the compatibility adapter as well as the direct reader.

## Widen the resolver's real candidate universe

The published Django fixture has only a small candidate inventory. A larger pinned universe could test whether the gains survive denser conflicts and realistic version alternatives. Separate source/metadata delivery from search, and compare selected artifact identities under a documented policy.

## Investigate reuse as its own problem

Interpreter sessions need isolation, invalidation, finalizer behavior and memory limits. Resolver sessions need immutable universe/target/policy identities. Treat these as lifetime experiments; faster container reads alone do not answer them.

Remote metadata/artifact delivery belongs with the [artifact-host](../../components/artifact-host/README.md) and [dependency](../../components/dependencies/README.md) designs when those boundaries are ready. No remote protocol is selected by the local fixtures.

The [technical task register](follow-up.md) retains stable IDs and detailed acceptance criteria for follow-up work. Start with the [findings](findings.md) for current evidence.
