# What we have learned

The strongest gains came from avoiding repeated work and preserving useful knowledge between stages. Changing a container or replacing a reader with native code helped only when it removed work from the complete workflow.

## Compiler work can often be reused

On the tested Zstandard library, a native full build takes roughly 4.6 seconds. With already admitted inputs, local object reuse reduces an unchanged consumer to about 53 ms and a light implementation edit to about 117 ms. A heavy implementation edit still takes about 3.77 seconds because that object must be regenerated.

Broader keys lose reuse. Our first conservative policy included every visible header, so changing an unused shared input rebuilt everything. Recording what the compiler actually observed recovered that reuse while preserving negative lookups and include shadowing. Low-fanout header-edit pipelines then took about 110–121 ms **including snapshot preparation**. A real widely shared header correctly rebuilt its 26 readers and reused five objects.

That precision costs something. Journal validation slowed unchanged pipelines from 77 to 104 ms. An exact-view fast path before replay is the next focused experiment. Read the [compiler findings](compiler/findings.md) for matched evidence and limits.

## Process lifetime and scheduling matter

Four complete independent builds per process saved about 36 ms per build without caching ASTs or compiled results. Starting predicted expensive jobs first improved Zstandard build medians by 2.3–5.2%, with slightly higher CPU consumption. Neither is a general proof of a production worker service or build-DAG scheduler.

Direct compiler-to-linker buffers removed object-file I/O, but did not produce a consistent extra parallel-build win on the C libraries we tested. The larger library still spent most measured compiler time in optimization and code generation. Fewer syscalls are useful evidence about mechanism, not sufficient evidence of faster work.

## Python benefits depend on the workload

Keeping archive/index state alive and avoiding eager reconstruction of unused metadata helped the measured Python loading paths. Generic startup changes improved short commands substantially, while the Django improvement was more modest. Moving bytes through Odin alone did not make the framework start faster.

The resolver experiments found repeated scans, predicate work and state copying that could be removed. Those improvements do not make dependency solving easy in general, or replace pip's full behavior. Read the [Python findings](python/findings.md) for the distinction between loading, resolution and full-process startup.

## What the evidence does not establish

The compiler baselines are full uncached batches, not a head-to-head comparison with existing incremental build tools. Header timing cases deliberately have low fanout. Input/SDK admission and edit discovery can be substantial work outside a consumer clock; the latest pipeline comparison includes updating a known snapshot, not discovering an arbitrary new SDK.

Measurements use the available Linux laptop, pinned software and warm page cache. Results from different runs should not be added together. No artifact-host protocol, editor, general compiler service or source-control implementation follows from these experiments.

The [prospects](prospects.md) explain the next measurements that could change our decisions.
