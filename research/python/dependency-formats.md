# Python dependency formats and loading: review

**Conclusion:** immutable admission, retained indexes and avoiding bulk Python metadata reconstruction help the measured loading paths. An Odin byte reader by itself does not establish faster framework startup. Generic bootstrap changes help short commands substantially and Django modestly; framework-specific tuning is paused.

This is Python-specific evidence, including CPython bytecode, importlib/resource adapters and a Django fixture. Mechanisms such as compact mapped metadata may transfer to other consumers, but those consumers need independent measurements. No experimental sidecar is a standard format.

## Results to assess

| Finding | Matched evidence | Practical limit |
| --- | --- | --- |
| Retain archive/index state and connect resource/module discovery to it | [Persistent loader](../../experiments/python/dependency_bundles/results/persistent/REPORT.md), [index-backed discovery](../../experiments/python/dependency_bundles/results/path-index/REPORT.md) | Removing syscalls is distinct from complete-process latency; compatibility paths still matter. |
| Move derived metadata work to a producer | [Precomputed catalog](../../experiments/python/dependency_bundles/results/catalog/REPORT.md), [mapped native lookup](../../experiments/python/dependency_bundles/results/mapped-catalog/REPORT.md) | Producer/storage costs remain; admission hashing and structural checks still scale with metadata. |
| Keep available-but-unused metadata native and mapped | [Bounded native catalog](../../experiments/python/dependency_bundles/results/native-catalog/REPORT.md) | At 131,072 available leaves and 33 imports, process/RSS improve versus Python reconstruction; Django has no demonstrated readiness gain. Arena capacity is not an RSS limit. |
| Representation density helps at large catalog sizes | [Compact metadata](../../experiments/python/dependency_bundles/results/unified-catalog/REPORT.md) | Metadata 16.5 → 9.0 MiB, setup 26.1 → 16.6 ms; full process only 5.7% better by medians with 10/15 wins. Wide consolidation alone does not help. |
| Native access performance and framework startup are different measurements | [Bridge diagnosis](../../experiments/python/dependency_bundles/results/bridge/REPORT.md), [Django](../../experiments/python/dependency_bundles/results/django/REPORT.md) | Native reads win in isolation; the framework also compiles/decodes code, constructs classes, discovers inputs and initializes itself. |
| Consumer bootstrap remains material | [Seven-mode comparison](../../experiments/python/dependency_bundles/results/bootstrap/REPORT.md), [Django confirmation](../../experiments/python/dependency_bundles/results/bootstrap-confirmation/REPORT.md) | Short commands gain 27–31% with combined changes. Focused Django thin/precompiled launch gains 3.6%, winning 23/30 blocks; additional CLI bypass benefit is uncertain. |
| Faster readiness can hide deferred work | [Process lifecycle](../../experiments/python/dependency_bundles/results/process-characterization/REPORT.md) | GC batching improves Django readiness but worsens whole-process time. Diagnostic fast exit changes finalizer semantics and is not an optimization to ship. |

## Reproduction and implementation map

The [experiment README](../../experiments/python/dependency_bundles/README.md) contains per-stage commands. Generate predecessor datasets on your machine before running a downstream comparison; saved commands describe the original measurement environment. Input production is separate from startup timing. See the [reproduction guide](../../experiments/reproducing.md). Published wheel acquisition requires network access; core synthetic tests run locally.

| Concern | Implementation |
| --- | --- |
| Python loader/resource/path integration | [persistent_zip_loader.py](../../experiments/python/dependency_bundles/persistent_zip_loader.py), [indexed_path_loader.py](../../experiments/python/dependency_bundles/indexed_path_loader.py) |
| Python/native handoff and lazy metadata | [native_loader.py](../../experiments/python/dependency_bundles/native_loader.py), [native_catalog.py](../../experiments/python/dependency_bundles/native_catalog.py) |
| Native storage and CPython lifetime boundary | [Odin accessor](../../experiments/python/dependency_bundles/native/main.odin), [C shim](../../experiments/python/dependency_bundles/native/python_shim.c) |
| Producer-built mapped/compact layouts | [mapped_catalog.py](../../experiments/python/dependency_bundles/mapped_catalog.py), [unified_catalog.py](../../experiments/python/dependency_bundles/unified_catalog.py), [native consumer](../../experiments/python/dependency_bundles/native/unified_catalog.odin) |
| Lifecycle and generic bootstrap experiments | [process_characterization.py](../../experiments/python/dependency_bundles/process_characterization.py), [bootstrap_benchmark.py](../../experiments/python/dependency_bundles/bootstrap_benchmark.py) |

## Review boundaries

Check trusted immutable admission versus per-open whole-file authentication, payload CRC, malformed-input bounds, mapping/decoder lifetimes and source-inspection behavior before comparing timings. Source-only and precompiled bytecode inputs are separate controls. Warm page cache is not cold storage. Producer cost, mount/setup, actual workload, validation and full shutdown need distinct clocks.

The bootstrap research retains 405 validated timed processes and 70 passing regression tests. Earlier reports have their own test/sample counts. Synthetic large catalogs hold imported modules fixed; they are not millions of executed modules. Django is a pinned ORM/admin/REST fixture, not an arbitrary deployed application.

The [technical task register](follow-up.md) retains acceptance criteria. Interpreter preparation and lifetime are covered separately in the [state-reuse review](interpreter-state.md).

## Connection to artifact delivery

The artifact experiments connect a trusted hash lock to the same real Django dependency workload. Python imports and resources can use a retained pack without extracting loose files. A compact retained index removes most eager reader setup; charging producer construction and acquisition still matters. When both flat payloads and ZIP receive producer-built portable indexes and identical per-read SHA-256/CRC checks, cold installation is near parity around 45 ms, with no reliable complete-startup lead for flat payloads.

The [artifact findings](../artifacts/findings.md), [preindexed comparison](../../experiments/artifacts/results/preindexed-bundle/REPORT.md) and [lock/consumer contract](../../components/artifact-host/locked-python-research.md) own the detailed evidence. This extends Python consumer integration without selecting a universal dependency format or replacing ecosystem selection rules.
