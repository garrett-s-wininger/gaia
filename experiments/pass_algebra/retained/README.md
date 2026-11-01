# Retained facts with two analysis consumers

This experiment asks whether producing compact def-use facts alongside liveness pays for itself during a sequence of queries and edits. The control uses LLVM's maintained use lists and the same result caching and invalidation scope as the compact variants. It continues the [pass formulation experiment](../README.md), whose native worklist kernel was faster than its alternate formulations.

This experiment changes LLVM analysis representation and fact production. The [shared-workspace integration](../../integration/README.md) measures compiler observations, source queries, identity scans and dependency sets separately.

## Required results and policies

Every policy returns the same two results:

- Block-by-SSA-value live-in masks, with the [previous PHI and fixed-point contract](../README.md#required-result-and-mathematical-transformation). The same native Odin worklist runs in every policy.
- A sorted, unique set of node ordinals reachable from a specified function argument by following **syntactic data uses**. Nodes include arguments and all instructions, including void endpoints. Constants, global values, and debug intrinsics do not propagate this relation. PHIs include all incoming value edges. Unreachable blocks participate.

The second result is a small source-navigation building block: which instructions use a parameter, directly or transitively? It omits memory aliasing, control dependence and interprocedural effects. It is not a sound program-impact analysis or a justification for excluding tests. Ordinals are local to a function revision, with separate numbering for liveness values; inserting an instruction can renumber later values.

| Policy | Liveness production | Slice miss | Unchanged result |
| --- | --- | --- | --- |
| `native_cached` | Produce and solve once per invalidated function | Traverse LLVM's existing use lists | Return retained immutable result |
| `compact_eager` | Also emit CSR def-use edges during the operand walk | Traverse retained CSR | Return retained immutable result |
| `compact_lazy` | Produce and solve without extra edges | Build CSR on first demand, then traverse | Return retained immutable result |

All use the same efficient liveness producer, per-function ordinal maps, kernel, and caches. Eager production shares an operand walk; it does not eliminate distinct representations with different meanings. Lazy construction walks operands separately. There is no source parser, modified Clang frontend, device execution or production pass-manager integration here. LLVM already retains use edges, so CSR is an additional representation whose costs must be recovered.

## Trace and validity

The trace selects the largest function with an integer parameter having an ordinary instruction use. Exploration queries up to eight arguments in each of the three largest functions with parameters. Selection uses instruction count and stable module order, not timing results.

Each of ten requests reads liveness for every defined function and asks its slice queries:

1. Initial liveness plus one parameter query.
2. Explore the other selected parameter roots.
3. Repeat unchanged requests.
4. Replace one ordinary operand using the selected parameter with a typed zero.
5. Insert a real `add parameter, 0` instruction at entry, shifting ordinals. This deliberately remains a syntactic use even if later optimization could erase it.
6. Split the entry block before its terminator; LLVM updates successor PHIs.
7. Add an unused internal function and query its argument.
8. Remove that function after checking it has no users.
9. Refresh an explicit analysis-context version and conservatively invalidate everything. This is a synthetic validity event, not a measured target-configuration change.
10. Repeat unchanged requests.

These are declared, controlled **IR edits**, not source edits or compiler round trips. Editing invalidates only the affected function; adding/removing an unused function preserves other intraprocedural results. Every edit advances the session generation. Old generation tokens and out-of-range argument requests are rejected. Published result vectors are immutable and an old result is held across edits to check its lifetime. There is no concurrent mutation, automatic edit detection or generic dependency broker.

## Measurements and correctness

A verified LLVM module is cloned for each independent policy trace. Cloning, initial parsing, source compilation, oracle production and exact checking are outside request clocks. Clone duration is recorded separately. Each request includes its declared IR mutation, cache invalidation/admission, missing ordinal/fact/graph production, liveness solve, query work, response assembly and complete result hashing. Phase clocks distinguish mutation, liveness and queries.

Seven blocks shuffle policy order with a fixed seed. The total is a **sum of ten measured request spans**, not uninterrupted interactive-session latency: verification between requests perturbs caches. There are no repeated traversal-only batches hiding producer cost. Cached requests still consume full outputs, so their duration includes hashing rather than representing only lookup latency. Response cleanup, session teardown and reference checks are outside these clocks; invalidation-time destruction is inside. Reported totals cannot be compared directly with the earlier one-pass measurements.

The input corpus is the retained `-O1` IR from the [previous acquisition](../results/no-names/provenance.json): Zstandard 1.5.7 common and lazy compression, and zlib 1.3.2 deflate. Exact input IR hashes are in the new provenance. The small common module is an overhead control. Inputs are already resident LLVM IR, not a newly captured development session. The selection and trace are experimental, not a measured user-demand distribution.

The liveness oracle uses the older independent extractor and ordered-set fixed point. The slice oracle repeatedly scans operands to closure; it uses neither LLVM use lists nor CSR. Every output is compared exactly after every measured event. Hand-checked fixtures additionally cover argument roots, PHI cycles, unreachable blocks, void endpoints and exception edges; both query-before-liveness and liveness-before-query orders are checked. The prior native-kernel and extraction tests also run. Counters require exactly one re-production for a changed function, zero for unchanged requests and full re-production only for context refresh.

Logical retained payload counts vector elements and key/value elements in ordinal maps. They exclude allocator overhead, unused capacities, container metadata, LLVM's resident IR, transient preparation/scratch, and the test's extra held result. They are not RSS or a peak process-memory estimate. Keeping LLVM resident gives its direct-use-list control its natural existing structure; this does not measure an IR-free compact service.

The runner takes a shared advisory measurement lock when supplied. This excludes cooperating measurements only, not unrelated host work or preparation. Build/source/IR/binary identities are checked before and after execution. Selected SDK identity files are pinned; this is not a hermetic SDK dependency manifest.

## Reproduce

Use explicit local toolchain paths. LLVM 22 headers/library and an Odin compiler are required. The parent build also produces the original adapter for its correctness tests.

```sh
python3 experiments/pass_algebra/retained/build.py \
  --odin /opt/odin/nightly/odin \
  --clangxx /usr/lib/llvm22/bin/clang++ \
  --llvm-include /path/to/llvm22/include \
  --llvm-library /usr/lib/llvm22/lib \
  --output experiments/_work/pass-algebra/retained-tools

python3 experiments/pass_algebra/retained/run.py \
  --host experiments/_work/pass-algebra/retained-tools/retained-host \
  --library experiments/_work/pass-algebra/retained-tools/liveness.so \
  --ir zstd-common-O1=/path/to/zstd-common-O1.ll \
  --ir zstd-lazy-O1=/path/to/zstd-lazy-O1.ll \
  --ir zlib-deflate-O1=/path/to/zlib-deflate-O1.ll \
  --lock /path/shared/measurement.lock \
  --output experiments/pass_algebra/retained/results/reproduction \
  --blocks 7 --seed 731
```

To regenerate upstream IR, use the [parent reproduction commands](../README.md#build-and-reproduce) and pinned archives. Different paths may be necessary; the new runner records actual IR identities. Existing `results.json` files are never overwritten. Full observations stay ignored; summary, validation, provenance, raw identity and interpretation are versioned.
