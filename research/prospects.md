# What looks worth trying next

The next useful work should improve a complete operation while preserving correctness, recovery and a lightweight local experience. The evidence supports a few concrete experiments; it does not yet support a universal format or service architecture.

## Keep unchanged builds cheap

Use exact input-view equality as a fast path. Replay the dependency journal only when the visible inputs differ. The current journal recovers header-edit reuse but adds around 30 ms when a coarse key already hits. A good result would retain the low-fanout header gains while bringing unchanged/source-edit costs back toward the simpler cache.

The [compiler prospects](compiler/prospects.md) give the controls, failure cases and stopping conditions.

## Make prepared inputs genuinely cheap to update

Explicit deltas eliminate loose SDK/source reads, but the producer still writes and hashes the whole roughly 3 MiB snapshot. Test metadata/content-ID snapshots or retained immutable mappings before choosing a durable representation. Include the cost of initial admission and change discovery when expanding beyond an already admitted SDK.

## Turn process reuse into a bounded service experiment

Repeated builds in one process helped. Next establish request isolation, cancellation, error recovery and memory growth before relying on long-lived workers. Compare threads with isolated processes using the same request and artifact contracts.

## Test broader workflows

A multi-target C++ project can reveal frontend reuse, target readiness and resource contention that single C libraries cannot. Existing incremental build tools need a matched comparison. Python work should reopen for a representative real tool or a specific compatibility gap, rather than more tuning of one framework.

## Develop product designs at their own pace

The agreed [source-control milestone](../components/source-control/milestone-1.md) is ready to guide implementation. The [editor](../components/editor/README.md) and [artifact host](../components/artifact-host/README.md) need scoped design discussions. Research can inform their interfaces without deciding their MVPs implicitly.
