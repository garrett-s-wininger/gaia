# Interpreter state reuse: compare complete tools and lifetimes

Initialized state can improve startup, but a useful snapshot depends on the real workload and its existing caches. The experiments separate live Python templates, a Node dependency snapshot and complete TypeScript CLI execution.

## Python templates trade startup for a retained process

A single-threaded Linux template imports pinned Django dependencies before forking a fresh request child. Complete core/REST operations fall from 251/256 to 135/161 ms. An explicit framework preparation hook reaches 105/131 ms. Both prepared stages win all seven paired blocks, with normal child finalization. [Template report](../../experiments/python/interpreter_snapshots/results/initial/REPORT.md).

Creating and shutting down the template makes a single request slower; modeled amortization crosses the fresh-exec control around two requests. Ready templates retain roughly 40–47 MiB RSS plus child work, with shared pages preventing a simple sum. Inputs/settings/cwd are fixed, and threads or unapproved live resources are rejected. Forking isolates parent Python heap mutations, not arbitrary native state or external effects. No CPython disk restore was measured.

## A real dependency changes the Node snapshot result

An initial synthetic Node graph restores correctly but loses to ordinary construction: about 120 vs 99 ms for 100,000 metadata records. It was a poor proxy for an expensive real dependency.

The TypeScript 5.9.3 compiler initializes a 9.11 MB module with 2,244 API properties. A fresh parse/transpile request takes 202 ms from the same bundle, 198 ms through stock require, 117 ms from the default snapshot and 132 ms without its code cache. Both restored paths win all seven blocks. No request result or source AST is prepared. Creation costs 553 ms for the 19.38 MiB default blob. [Dependency snapshot report](../../experiments/python/interpreter_snapshots/results/typescript/REPORT.md).

That report retains its `perf_hooks` warning and narrow parser/transpiler scope. Restoring valid state did not yet establish general watch, resource or performance-API behavior.

## The complete project loses to a competent stock cache

The full project follow-up runs genuine TypeScript checking/emission on published exponential-backoff sources and standard libraries. Every one of the 44 outputs and the changing runtime consumer matches. Snapshot restoration takes 738 ms versus 799 ms for the identical API bundle, winning seven of seven pairs. The ordinary stock CLI with its warmed Node compile cache takes 722 ms and wins five of seven against the snapshot. [Complete-project report](../../experiments/python/interpreter_snapshots/results/typescript-project/REPORT.md).

A deserialization bridge supplies live `perf_hooks` bindings instead of serializing their native objects. Build/rebuild are warning-free, and extended diagnostics, source/config changes, current argv/env/cwd and normal exit are checked. Preparation still costs 578 ms and about 19 MiB; rebuilding costs 467 ms. Consumer correctness and preparation costs remain separate from the complete command timing.

## What carries forward

Use explicit preparation/request boundaries and a representative complete operation. Compare against warmed ecosystem caches, charge producer/rebuild and teardown work, and validate current resources rather than serializing them blindly. Broader language servers, concurrent sessions, failure recovery and memory bounds remain untested. The loader measurements are independent clocks and cannot be subtracted from these results.

See [reproduction](../../experiments/python/interpreter_snapshots/README.md), [Python prospects](prospects.md) and the [run index](experiments.json).
