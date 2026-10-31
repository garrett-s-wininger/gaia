# What to test next for artifact access

The existing studies establish batching, verified local views and producer indexes. The [shared-data follow-up](followthrough.md) adds synchronous demand consumption, a 3,931-object cache trace and direct metadata queries across three runtimes. The next useful work should extend these bounded results into real transport overlap and longer lifetimes, rather than repeat the completed format comparisons.

## Use verified data while it arrives

The Django demand consumer executes before its final fetch, but still uses synchronous socket requests. Connect useful consumer work to the progressive missing-hash stream and measure actual transfer/CPU overlap. Include ownership, admission, callback work, cache visibility and final receipt publication in the complete clock. Large-object head-of-line blocking needs its own evidence.

Keep the established-connection case separate from index discovery, connection setup and name/version lookup. A trusted lock may already name the exact content; an unresolved package request may not.

## Measure network and sparse-access budgets

Compare bounded concurrent objects, missing-hash batches, coalesced ranges and full payloads under bandwidth limits as well as latency. Charge negotiation/probes and report both requests and bytes. Preserve a policy that fetches one missing 4 KiB object when a caller cannot afford a multi-megabyte payload.

A competent native HTTP control is needed before attributing a general advantage to the private binary framing. Preserve the same batching, digest, cache and lifecycle semantics. TLS, authorization, real WAN behavior and CDN/object-store compatibility remain separate measurements.

## Retain compact metadata without rebuilding equivalent objects

The [binary lock](../../experiments/artifacts/results/generic-lock/REPORT.md) reduces parse cost, and [producer-preindexed admission](../../experiments/artifacts/results/preindexed-bundle/REPORT.md) removes receiver index construction from both flat and ZIP controls. Profile the remaining descriptor wrappers, cache locators and repeated name lookups. A producer hash table or bounded lookup memo may benefit both readers; apply it to both controls before claiming a container gain.

Include producer cost, malformed/compatibility vectors, stale-index repair and algorithm/extension rules. Opaque versions and artifact associations should not grow implicit universal dependency semantics.

## Test growing caches and recovery

Extend the existing real-artifact trace beyond 3,931 objects and exercise changed live sets over longer consolidation/eviction sessions. The new single-blob probe separates open-store lookup from reopening/index reconstruction; optimize that reconstruction before assuming one lifetime. Account for retained readers and mapped leases separately from serialized pack budgets and the prototype's owned byte views.

Inject cancellation, disk full, interrupted bodies, corrupt locators, restart and mismatched partial representations. Current retries retain complete verified objects; resumable byte staging needs an explicit identity and publication rule. Establish prior-index recovery and fsync ordering before promising authoritative offline durability.

## Keep compatibility costs visible

Direct logical access is useful only when a tool consumes it. Measure native input collections, package/module/resource adapters and ordinary-file materialization separately and together. The real Django workload is useful evidence but not universal package compatibility. Target SDKs, native extensions, editable installs, upload negotiation and metadata trust remain open interfaces.

Read the [findings](findings.md), [reproduction guide](../../experiments/artifacts/README.md) and [artifact-host boundary](../../components/artifact-host/README.md) before selecting a production protocol.
