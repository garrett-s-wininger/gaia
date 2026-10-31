# What is worth testing next

The next experiments should connect the demonstrated pieces and broaden their workloads. More isolated format tuning is useful only when a profile identifies meaningful work in the complete operation.

## Connect workspace authority to a larger build graph

The [semantic-invalidation proof](compiler/findings.md) adds a concrete compiler boundary to test: retain frontend IR, check its identity before optimization/code generation, and continue with that same IR on a miss. This would avoid the prototype's repeated frontend work. Preserve ccache controls, diagnostics, side products and the packing/target/assembly/debug regressions; AST fingerprints are not object-cache proofs.

The [logical workspace](compiler/findings.md) and four-target C++ graph have been measured separately. Combine them on a larger production project with generated inputs, configuration changes and wider header fanout. Retain independent artifacts and matched Ninja controls; keep fresh compilation separate from repeated-edit hits. Charge initial SDK admission and filesystem change discovery when that adapter is used.

The question is whether a shared authoritative input generation reduces repeated target validation at useful repository sizes. Success means lower complete-operation latency without stale readiness, excessive retained generations or weaker invalidation.

## Establish bounded tool lifetimes

Native and [JVM compiler](compiler/jvm/prospects.md) reuse justify longer sessions. The new topology and execution studies measure CPU and memory separately, but neither establishes a long-lived bound or peak throughput. Test mixed targets under a resident-memory budget, characterize the PSS remainder with native-memory/smaps diagnostics, and extend a small JIT/GC finalist set beyond the still-changing 32-request trace. Keep Java source targets whole until an incremental compiler provides a stronger grouping contract.

A managed service should earn its lifetime complexity through amortized complete workflows and bounded resource use. Short warm measurements and serialized cache limits are not sufficient memory guarantees.

## Make artifact access useful under real network and cache conditions

The [artifact work](artifacts/prospects.md) supports missing-hash batches and verified logical views. Test useful consumer work during delivery, sparse access, byte budgets, growing caches and interruption/recovery. Include bandwidth limits, realistic latency and a competent native HTTP implementation before attributing a general win to binary framing.

Producer indexes and binary locks have already removed much repeated metadata work. Measure remaining shared lookup/cache work in both flat and ZIP controls. Keep name/version discovery, ecosystem resolution, metadata trust and content transfer as separate contracts.

The [storage-service model](storage/prospects.md) demonstrates latency gains and bandwidth losses from full memory admission. Test demand granularity, selective admission and longer reuse, then validate on an isolated actual storage setup. Warm page-cache hits need not encounter device throttling; a logical service delay is a separate contract.

## Prepare framework data only where the complete tool benefits

For [Groovy](java/prospects.md), JVMTI supports a modest module-classification index and points to runtime-image/class lookup work. Reuse that diagnostic evidence with fresh classloader and mutable bindings; preserve uninstrumented controls and the unstable negative run. The DGM decoder alone is too small to explain startup. For [Ruby](ruby/prospects.md), test whether unused pack/index data can stay outside eager Ruby objects while preserving require behavior and full verification.

A broader [Node/Python session](python/prospects.md) must beat competent cache baselines and justify preparation/rebinding costs. A broader [.NET workload](dotnet/prospects.md) must justify its modest composite-R2R gain and servicing cost. Preserve negative results when changing the workload.

## Keep product design separate

The [source-control milestone](../components/source-control/milestone-1.md) remains ready to guide local-engine implementation. The [editor](../components/editor/README.md), [dependency](../components/dependencies/README.md) and [artifact-host](../components/artifact-host/README.md) interfaces need their own scoped decisions. Experimental encodings and local process arrangements should not become public standards by accident.
