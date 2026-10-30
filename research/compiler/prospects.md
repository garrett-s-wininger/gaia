# Where compiler research should go next

## First: an exact-view fast path

The dependency journal recovered header-edit reuse but added about 30 ms to unchanged and simple source-edit pipelines. Check exact input-view equality first, then replay observations only on mismatch.

Keep the coarse and journal controls in the same executable. Test unchanged work, source edits, used/unused headers, optional-file appearance, shadowing, deletion and request reordering. A useful result preserves header-edit correctness and brings already-cheap cases back toward coarse-cache costs. Retain the existing conservative path if the new policy does not earn its complexity.

## Then: avoid rebuilding the entire snapshot representation

The delta producer avoids loose reads but still copies and hashes a complete roughly 3 MiB snapshot. Compare retained immutable bases, metadata/content-ID snapshots or a structured overlay against the current materialized collection. Include producer work, admission and consumer access in one clock.

Keep the SDK/input contract explicit. New compiler configurations may need readmission. A filesystem watcher or edit-to-delta adapter is separate work; change detection must be measured when claiming complete edit latency.

## Establish bounded process reuse

Finite batching saved time. A service experiment needs memory-growth limits, cancellation, orderly failure handling and crash recovery. Compare threaded and isolated-process workers with identical inputs and output checks. Fast paths must still preserve diagnostics and normal cleanup.

## Broaden the workload and the comparison

Use a multi-target C++ project to test target readiness, frontend work and resource-aware scheduling. Measure clean builds, implementation edits, low- and high-fanout headers, configuration changes and branch/revert behavior. Add matched existing incremental-build/cache controls before making an ecosystem-level performance claim.

## Questions for storage and interfaces

The current cache retains one latest journal candidate per action. Eviction, quotas, deduplication, historical variants and authenticated remote records need design and measurements. The [artifact-host component](../../components/artifact-host/README.md) is the home for that broader scope.

Observed conditions could become a useful tool-result capability. First define their identity, completeness, negative-query semantics and lifetime. The current LLVM adapter and binary records are evidence for that discussion, not the open protocol itself.

For source code, fixtures and the run index, start with the [research guide](README.md). These are prospects, not implementations already in progress.
