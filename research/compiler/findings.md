# What the compiler experiments taught us

The biggest gains came from reusing work that did not need to run again. Process reuse and scheduling helped too. Replacing warm-cache object files with native buffers changed the mechanism but added little measured speed on the tested libraries.

The experiments use real C compilation through Clang/LLD, with Odin orchestration. They include zlib and Zstandard, plus small generated fixtures and explicit probes for invalidation behavior. The current baselines rebuild a complete native batch; they are not matched comparisons with make/ninja/ccache incremental builds.

## Reuse needs the right input boundary

With already prepared inputs, local object reuse reduced a Zstandard-plus-probe unchanged consumer from 4.65 seconds to 53 ms. A light implementation edit took 117 ms with 30 of 31 objects reused. Editing the expensive implementation still took 3.77 seconds because that object had to be regenerated. [Object-cache measurements](../../experiments/compiler/results/object-cache/REPORT.md).

A key containing the entire collection invalidated every object after any source edit. Per-request input-view keys preserved reuse for unrelated source files, but still treated every visible header as relevant. That was safe and unnecessarily broad.

## Record what the compiler actually observed

The next prototype retained reads, metadata/existence checks and failed lookups. Before reusing an object, it checked that those observations still held in the new hermetic input view. A new optional header or an earlier include-path match correctly changed the result instead of returning an old object.

These timings include snapshot preparation, receipt handoff, linking and normal shutdown of both native processes:

| Change | Coarse view cache | Observed-query cache | Compilers executed |
| --- | ---: | ---: | ---: |
| Shared audit header | 4.624 s | 110 ms | 1 of 31 |
| Generated audit header | 4.678 s | 116 ms | 1 of 31 |
| Optional header appears | 4.683 s | 115 ms | 1 of 31 |
| Earlier header shadows fallback | 4.620 s | 119 ms | 1 of 31 |
| Unused header changes | 4.711 s | 102 ms | 0 of 31 |

Those audit headers are visible to every request but consumed only by the probe. A real Zstandard shared-header check rebuilt its 26 independently identified readers and reused five objects. Widely used headers still require rebuilding their readers. [Pipeline measurements](../../experiments/compiler/results/dependency-cache/REPORT.md), [real shared-header check](../../experiments/compiler/results/dependency-cache/fanout-check.json).

Precision has overhead. Unchanged pipelines rose from 77 to 104 ms, and implementation-edit pipelines from 129 to 164 ms. Replaying observations when an entire input view is unchanged is avoidable work; it is the strongest next experiment.

## Updating an admitted snapshot is cheaper than refreshing every file

Applying supplied changes to a prior snapshot opened no loose project/SDK files. A full refresh opened 198–199. Producer savings were only about 3–8 ms on this warm-cache fixture: both implementations still serialized and hashed the complete roughly 3 MiB collection.

This is an update to an already admitted namespace. Initial SDK discovery and creating the change events are separate costs. Complete-pipeline improvements from the producer alone were smaller and mixed. The large header-edit gains came from selective compilation reuse. [Producer/consumer comparison](../../experiments/compiler/results/dependency-cache/REPORT.md).

## Process lifetime and scheduling offer smaller, useful gains

Four independent complete builds per process saved about 36 ms per build, with compiler state recreated each time. It validates finite batching, not an indefinitely running or crash-isolated worker. [Lifetime comparison](../../experiments/compiler/results/compiler-lifecycle/REPORT.md).

Starting historically expensive jobs first improved Zstandard wall medians by 2.3–5.2%, with 165–221 ms paired median savings. Aggregate CPU rose 1.6–2.9%. This is an optional scheduling policy with compatible history, not a universal default. [Scheduling comparison](../../experiments/compiler/results/cost-scheduling/REPORT.md).

## Direct handoff was not the main bottleneck

Direct buffers removed generated-object filesystem calls. They did not establish a consistent extra parallel-build win in zlib or in Zstandard release/debug builds. The complete embedded link was small relative to compilation; separate traces placed 86–88% of summed Zstandard job spans in the backend. Those spans include scheduling delays and are not CPU samples. [Direct handoff](../../experiments/compiler/results/direct-handoff/REPORT.md), [larger project](../../experiments/compiler/results/zstd-handoff/REPORT.md), [phase attribution](../../experiments/compiler/results/zstd-handoff/PHASES.md).

## How much confidence to place in this

The latest journal comparison checked all 4,960 timed object identities and 160 libraries against fresh CLI references, plus negative-lookup/failure/corruption/concurrency checks and 246 upstream round trips. Earlier reports retain their own validation counts.

The provider uses explicit regular-file namespaces and fixed metadata. It has no host-input fallback. Arbitrary aliases, plugins, complete SDK discovery, remote trust, storage quotas and persistent crash recovery remain open. Experiments use warm page cache on one Linux laptop. Compare controls within a run; their absolute medians cannot be combined into a larger claimed speedup.

Read the [prospects](prospects.md) for the next decisions. Detailed implementation limits and evidence remain in the [lab journal](../../experiments/compiler/FINDINGS.md).
