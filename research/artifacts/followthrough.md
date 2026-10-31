# Sharing data across consumers and lifetimes

This follow-up separates four mechanisms that would otherwise be easy to conflate: reducing dependency bytes admitted, retaining a growing local cache, sharing an immutable structured representation, and charging retained data beside a resident compiler. The [prototype guide](../../experiments/artifacts/followthrough/README.md) contains commands and boundaries.

## Demand admission trades bytes against requests

The real Django consumer can execute framework code before all dependency reads complete. That establishes useful interleaving with demand delivery. It does not establish asynchronous network/CPU overlap or a general streaming-protocol speedup.

Small verified chunks reduce total fetched bytes across repeated starts. Larger chunks reduce service requests but overfetch more. Full admission minimizes subsequent service reads while paying to read unused payload bytes. Each policy retains identical installation, normal interpreter exit, loader behavior and per-file SHA-256/CRC32 checks. The [admission report](../../experiments/artifacts/followthrough/results/admission-frozen/REPORT.md) distinguishes frozen-source confirmation from an exploratory matrix whose constructor source changed during execution.

The artifact cache remains a client of the synchronous application-storage model. Host pages are warm; neither a real degraded disk nor a WAN is measured. Shared Python socket dispatch and copying are charged to every policy and can dominate nominal startup. The next boundary is a consumer/transport overlap test with a competent transport control, not a universal chunk-size choice.

## Growing-cache lookup needs its own control

The [lifecycle report](../../experiments/artifacts/followthrough/results/lifecycle/REPORT.md) uses actual dependency objects. Reopening a packed cache includes index parsing and recovery work; looking up one object through an already-open store is a different operation. Both must be visible when choosing a lifetime.

Eviction/consolidation preserve previously returned owned immutable byte views in this prototype. Those views are independently allocated buffers, not leases on a live file mapping. Their lifetime does not prove safe deletion of arbitrary mapped representations. Failure probes preserve the prior publication boundary, while corrupt metadata follows the existing empty-cache recovery policy. Strong offline durability and prior-index recovery remain open work.

## Sharing a representation differs from sharing an object graph

The [catalogue report](../../experiments/artifacts/followthrough/results/catalogue/REPORT.md) supplies one bounded immutable representation of real package metadata to Python, Odin and Node. Odin consumes Python-owned bytes through a borrowed C ABI call; Node independently consumes the same format. No compiler AST, runtime object graph or physical cross-process page sharing is required.

The controls retain independently parsed JSON objects and binary-to-object conversion. They compute identical aggregates, verify pinned bytes and enforce size/name bounds. Native code can fuse validation and queries without creating per-row runtime objects; that is a concrete interface to measure. A [matched fused Python follow-up](../../experiments/artifacts/followthrough/results/catalogue-fused/REPORT.md) preserves the gain against JSON without requiring a native query: 4.791 versus 2.356 ms, with the borrowed Odin path at 0.396 ms. These are read/verify/query operations, not complete tool starts. The result must not be generalized to arbitrary queries, persistence formats or zero-cost cross-process exchange. Consumer adaptation and producer preparation remain charged separately.

## Retained compiler and data memory need separate accounting

`hold_cache.py` supplies real repository-source generations and a verified artifact-chunk cache beside the JVM compiler study. A logical admission budget bounds source/chunk payload bytes. Process PSS includes additional runtime, metadata and transient costs. The companion's preparation is included in readiness and active replay adds useful cache work during compilation.

The [JVM follow-up](../java/followthrough.md#mixed-retention-exercises-admission-and-cache-eviction-not-os-pressure) owns aggregate sampling and its soft admission/stop policy. It does not establish a strict OS-enforced resident-memory limit, nor does the companion prove that compiler and artifact allocations share a production allocator. This is a bounded integration probe before selecting a global resource policy.
