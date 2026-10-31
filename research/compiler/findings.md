# What the compiler experiments taught us

Programmatic compilation is useful when the caller can retain inputs, initialized tools and correctly scoped results. The prototypes now improve several incremental operations against matched Ninja controls. Direct object buffers alone produced little consistent benefit; avoiding repeated preparation and validation made the larger difference.

Native experiments use Odin with narrow Clang/LLVM/LLD adapters. They cover zlib, Zstandard and a small C++ dependency graph on one Linux laptop. [Managed JVM compilation](jvm/findings.md) is a separate experiment with a different runtime and lifetime contract.

## Current incremental results

The latest C comparison uses Zstandard 1.5.7 plus an invalidation probe: 31 objects, eight workers and seven randomized paired blocks. Each output matches an independent CLI build.

| Operation | Physical compatibility adapter | Authoritative logical API | Ninja | Ninja + ccache |
| --- | ---: | ---: | ---: | ---: |
| Unchanged | 2.35 ms | 2.32 ms | 3.50 ms | 3.08 ms |
| Source edit | 48.78 ms | 42.25 ms | 66.35 ms | 98.33 ms |
| Shared audit header | 27.84 ms | 21.00 ms | 44.01 ms | 66.04 ms |
| Generated audit header | 27.80 ms | 21.19 ms | 42.65 ms | 66.72 ms |
| Unused header | 2.59 ms | 2.21 ms | 3.11 ms | 3.06 ms |
| Revert | 9.46 ms | 6.53 ms | 66.54 ms | 24.73 ms |

Logical source/header edits win all seven pairs against the physical adapter. The audit headers have low fanout; a separate real header correctly rebuilds 26 objects. These are warm operations after initial input/tool admission. See the [complete report](../../experiments/compiler/results/logical-inputs/REPORT.md), including clean builds and strict physical-import costs.

## Workspace authority determines what validation can avoid

An editor or source-control API can publish an immutable generation of file bytes and visibility. A build consumes one generation, records its positive and negative input conditions, and checks those conditions against the current generation before declaring readiness. Relevant concurrent edits reject publication; unrelated edits can remain selective. Tool identities and output hashes still matter.

That contract removes repeated source-mirror reads. Condition export falls from about 4.4 to 1.3–1.6 ms in the matched run. It does not discover unreported filesystem edits: a mutable-directory adapter must still observe and import changes. Separately, strict import of a known 263-file namespace takes 4.88 ms; admission of an already supplied source edit takes 0.050 ms. Initial SDK discovery is additional work. The current logical map copies on update, so large-repository update cost remains unproven.

The checker transport also changes from a resident process to an in-process reference implementation. Complete wall time includes that change; child-only CPU would not be comparable. The [input/lifetime contract](../../components/compiler/immutable-input-research.md) records the precise boundary.

## A small C++ graph preserves dependency propagation

The C++ experiment combines two unchanged upstream fmt sources with a labelled integration library and two executables: four targets and six translation units.

| Operation | Programmatic host | Ninja + ccache |
| --- | ---: | ---: |
| Source edit | 293.49 ms | 397.91 ms |
| Used header | 382.32 ms | 423.45 ms |
| Revert | 55.10 ms | 71.18 ms |

Changed operations win all three paired blocks. Source/header edits compile exactly one/four units and relink three dependent targets. Both object caches reset to baseline before each block; input authentication stays warm. Neither path restores complete historical linked results. No-op stays near parity at about 24 ms, while clean builds favor Ninja.

The [primary report](../../experiments/compiler/cpp_graph/results/baseline-seeded/REPORT.md) distinguishes these actual compilation misses from a [repeated-edit trace](../../experiments/compiler/cpp_graph/results/repeated-trace/REPORT.md). Objects, public artifacts, runtime behavior and byte-identical CRT aliases are checked independently. This validates graph mechanics, not large-production-project scale or arbitrary linker inputs.

## Source changes and object changes are different boundaries

A compiler-visible identity can avoid substantial backend work on a heavy translation unit. Appending an unused typedef changes preprocessed bytes and the AST but preserves exact pre-optimization IR and the independently compiled object: IR-only reuse takes 74.58 ms versus 2265.93 ms for a freshly seeded ccache control, improving all three matched blocks. Comments and unused macros favor ccache's existing preprocessor reuse at about 40 ms versus 71–73 ms for IR. The lighter source has no dependable comparable win.

A direct Clang AST walk removes the expensive JSON bridge, but the tested normalized AST and ODR fingerprints are incomplete object identities: packing, target attributes, inline assembly and debug locations produce unsafe candidate hits. Conversely, an extra unused type changes the AST without changing the object; the AST filter unnecessarily recompiles it. Exact IR checks plus fixed tool/SDK/options context match every independent object in the tested cases. This is a bounded translation-unit proof, not a production cache or per-function dirty-bit design. [Report and controls](../../experiments/compiler/semantic_invalidation/results/REPORT.md).

## The mechanisms behind the gains

The experiments below isolate different repeated work. Their absolute timings come from separate runs and must not be added together.

| Mechanism | What changed | Evidence |
| --- | --- | --- |
| Selective build decisions | Skip producer, LLVM and linking when compiler-observed conditions still hold, including missing paths and visibility. | [Decision gate](../../experiments/compiler/results/build-decisions/REPORT.md), [selective conditions](../../experiments/compiler/results/selective-conditions/REPORT.md) |
| Shared validation structures | Reuse namespace/replay structures and batch job masks instead of rebuilding equivalent data. | [Shared validation](../../experiments/compiler/results/shared-validation/REPORT.md), [incremental production](../../experiments/compiler/results/incremental-conditions/REPORT.md) |
| Retained producer data | Reuse parsed condition fragments and admitted logical hashes; physical backing-file guards still run. | [Retained production](../../experiments/compiler/results/retained-conditions/REPORT.md) |
| Resident tools and direct publication | Avoid a producer round trip and repeated LLVM/LLD startup; dispose request state before acknowledgement. | [Pipeline handoff](../../experiments/compiler/results/pipeline-handoff/REPORT.md) |
| Complete-result history | Restore a bounded successful linked result and revalidate its completion proof, making reverts cheap. | [Linked results](../../experiments/compiler/results/linked-results/REPORT.md) |
| Digest providers | Faster SHA-256 implementation first, then separately versioned BLAKE3 identities for selected native inputs. | [Digest comparisons](../../experiments/compiler/results/digest-providers/REPORT.md) |
| Native physical verification | Batch the same file reads, hashes and stability checks through one Odin call; the ABI transition is only about 17 microseconds. | [Native conditions](../../experiments/compiler/results/native-conditions/REPORT.md) |
| Shared immutable input segments | Publish and authenticate small edits instead of repeating a full 3.34 MB collection and unchanged file digests. | [Shared inputs](../../experiments/compiler/results/shared-inputs/REPORT.md) |

A complete-result hit still proves request/tool identity, observed input conditions and copied-output integrity. Selectivity includes failed lookups: hashing only successful reads would miss optional-header appearance or include shadowing. Cache quotas and staging are explicit; a serialized payload budget is not a process memory limit.

## What helped less

Direct object buffers remove generated-object filesystem calls, but did not consistently accelerate parallel zlib or Zstandard builds. Compilation dominated; the recorded compiler phase spans are not CPU samples. [Direct handoff](../../experiments/compiler/results/direct-handoff/REPORT.md), [larger-library comparison](../../experiments/compiler/results/zstd-handoff/REPORT.md).

Cost-based dispatch improves Zstandard wall medians by 2.3–5.2% with slightly more aggregate CPU. It is an optional policy using compatible history, not a universal ordering rule. [Scheduling comparison](../../experiments/compiler/results/cost-scheduling/REPORT.md).

## Confidence and remaining limits

The combined compiler suite passes 213 tests with optional providers enabled; the separate graph has three helper tests and exact work-count assertions. Reports retain their own independent artifact, runtime, corruption, failure and boundary checks. No performance matrix was rerun merely to reorganize the repository.

The current providers have explicit regular-file namespaces, pinned toolchains and narrow link contracts. Linux process-local descriptors, active leases, retained generations and warm workers have lifecycle costs. Arbitrary aliases/plugins, full SDK discovery, cancellation, crash isolation, long-run memory bounds and durable concurrent storage remain open. Read the [prospects](prospects.md) before extending the prototype into a service.
