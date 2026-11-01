# Reformulating a compiler pass for different execution patterns

This experiment applies Gaia's mechanical-sympathy question inside a compiler analysis: can the same required result be expressed in a form that fits the execution machinery better? It measures three exact formulations of SSA value liveness on freshly compiled upstream Zstandard and zlib LLVM IR.

The [retained-facts continuation](retained/README.md) adds a second consumer and controlled IR edits, comparing compact graph production with LLVM's existing use lists under equal result caching. Its [measured report](retained/results/initial/REPORT.md) charges graph production and invalidation to complete requests.

This study changes the analysis formulation and measures conversion costs. It is separate from the [shared-workspace and CPU integration experiments](../integration/README.md). The recorded run used an advisory measurement lock for cooperating timed cases; unrelated activity and preparation remain outside that lock.

Read the [current-source report](results/no-names/REPORT.md), [summary](results/no-names/summary.json), [validation](results/no-names/validation.json) and [interpretation](../../research/connections/pass-experiments.md). The [initial exploratory run](results/initial/REPORT.md) is retained separately. This is a bounded analysis experiment, not a new compiler backend or a complete development-session benchmark.

## Required result and mathematical transformation

For each function, enumerate its basic blocks and its SSA arguments/non-void instruction results. The required output is a dense block-by-value Boolean relation `L`: whether each value is live at block entry. Constants and globals are not members of this value universe. Debug-only intrinsic uses are excluded. This is syntactic SSA value liveness, not memory-location liveness, register allocation, alias analysis or proof that an instruction's result contributes to an observable effect.

Let `S[b,s]` denote a control-flow edge from block `b` to successor `s`, `D[b,v]` mean that block `b` defines value `v`, and `G[b,v]` be the generator relation. `G` contains ordinary uses before a local definition and PHI incoming operands used on outgoing edges when the value is not defined by that predecessor. LLVM PHI uses belong to the incoming edge, not to an ordinary read at the successor's entry. [LLVM PHI semantics](https://llvm.org/docs/LangRef.html#phi-instruction).

The least fixed point is:

```text
L = G OR ((S Boolean-multiply L) AND NOT D)

Boolean multiplication: (S * L)[b,v] = OR over s of (S[b,s] AND L[s,v])
```

All blocks, including unreachable blocks, participate. The result is the least solution from empty sets. In the implementation, seeding with `G` skips the first empty iteration. A kill-free path witnessing any propagated fact can be shortened to a simple path, which bounds synchronous convergence by the number of blocks plus the final no-change check.

| Formulation | Implementation | Execution property being tested |
| --- | --- | --- |
| Block worklist | Queued blocks with packed value masks; update predecessors when a row changes | Avoid unaffected blocks and perform contiguous word operations |
| Boolean sweeps | Sparse CFG multiplication plus packed generate/kill masks, using two generations of `L` | Uniform independent row computation within a sweep; extra global iterations and storage |
| Per-value sparse traversal | Transpose the generators into value-to-block lists; walk predecessors until a definition stops propagation | Visit live facts sparsely, with more irregular accesses into the common output layout |

`S` uses adjacency lists, not a dense block-by-block matrix. The block-oriented methods use dense packed block-by-value masks. The sparse method retains a dense kill mask and produces the same dense output, so it pays that output cost too. Layouts, generator transposition, scratch allocation and cleanup are charged in the complete pass.

The Boolean formulation exposes potential parallel row execution, but this experiment executes all kernels on one CPU thread. It does not establish GPU/NPU suitability. Iteration depth, batch shape, representation construction, device-supported exact operations, transfer and synchronization costs would all matter in a later device experiment.

## Build and reproduce

Use Linux, Odin and matching Clang/LLVM 22.1.8 development headers/libraries. Supply an include root containing both LLVM source and generated configuration headers, as in the [existing LLVM experiment](../science/compiler/README.md). Paths below are caller-selected absolute paths. The output tools target the measurement CPU and are not portable deployment binaries.

```sh
python3 -B experiments/pass_algebra/build.py \
  --odin "$ODIN" --clangxx "$CLANGXX" \
  --llvm-include "$LLVM_INCLUDE" --llvm-library "$LLVM_LIBRARY" \
  --output "$TOOLS"

GAIA_LIVENESS_LIBRARY="$TOOLS/liveness.so" \
  GAIA_LIVENESS_HOST="$TOOLS/liveness-host" \
  python3 -B -m unittest discover -s experiments/pass_algebra -p 'test_*.py' -v

python3 -B experiments/pass_algebra/run.py \
  --host "$TOOLS/liveness-host" --library "$TOOLS/liveness.so" \
  --clang "$CLANG" --zstd-archive "$ZSTD_ARCHIVE" --zlib-archive "$ZLIB_ARCHIVE" \
  --work "$WORK" --output "$OUTPUT" --lock "$MEASUREMENT_LOCK" \
  --blocks 7 --repetitions 10
```

Use the unchanged Zstandard 1.5.7 and zlib 1.3.2 release archives used by the [compiler experiments](../compiler/README.md); the run records their SHA-256 identities. `WORK` must not exist, and `OUTPUT` must not already contain `results.json`. The lock's parent must exist. Source archives are extracted into this new private work directory. Each selected upstream translation unit is compiled at `-O1` to LLVM IR; the source-to-IR command, time, source digest and IR digest are recorded.

`build.py` records compiler commands, binary identities, versions and selected SDK identity pins in `build.json`. This is not a complete SDK-header dependency manifest. `run.py` reruns the required tests without skips, verifies source/tool pins after measurement, and writes raw observations plus reviewable summaries. Generated code, extracted sources and full observations remain ignored. The small hand-authored LLVM fixture is versioned because it is part of the correctness specification.

## Correctness

An independent C++ ordered-set solver uses synchronous full recomputation over the extracted facts. Every output bit from each formulation is compared with that solver; padding bits must be zero. The timing loop consumes results and verifies the complete-pass digest against the already checked result. Prepared outputs are compared bit-for-bit again after each timed batch. The checksum is a timing/result-consumption mechanism, not a substitute for the initial exact checks or a content-authentication claim.

Python tests independently exercise all 4,096 graph/generator/kill combinations with two blocks and two values, plus 175 deterministic randomized cases covering cycles, disconnected graphs and 64-bit word boundaries. Output and scratch guards check buffer bounds in these cases. Six hand-checked LLVM functions cover edge PHIs, loop PHIs, unreachable blocks, a self-referential PHI, an empty value universe and an `invoke` result feeding a PHI.

The extraction adapter is common to all three formulations. The hand-checked cases test its semantics independently; the ordered-set oracle alone would not detect a shared extraction error. No stock LLVM liveness implementation is used as a performance control. These are competing native formulations of the declared analysis, not a claim to outperform LLVM's production analyses.

## Timing and lifetime boundaries

The host parses and verifies the module once before measurement. Each shuffled block measures six cases: three formulations at two boundaries.

- **Prepared kernel:** retained input layouts and scratch, output reset, propagation and a consumed work count. No allocation, extraction or full-result hashing inside the clock.
- **Resident IR to result:** extract facts from the unchanged module, prepare the selected layout, allocate scratch, solve, consume the entire output through a checksum and destroy request state. IR parsing and source compilation are outside this clock and recorded separately.

Repetitions reduce clock noise; they do not represent natural repeated requests whose analysis result should be recomputed. A real unchanged request could simply reuse its prior result. The question is how much one necessary analysis costs, and how its cost changes if a representation is already maintained for another consumer.

Extraction uses ordinary C++ containers, with its costs included consistently in complete-pass timings. Textual operand names are constructed only in diagnostic dump mode; the initial exploratory run also constructed them during measurement. The [correction patch](results/initial/remove-unused-names.patch) transforms that measured host source into the current host; reversing it in a disposable copy reconstructs the earlier extraction behavior. Exact historical source/binary pins remain in each run's provenance.

All formulations use the same native Odin compiler settings; ordinary loops can auto-vectorize. Counts labeled `work_units` are block visits for the worklist, complete sweeps for the synchronous method and block/value visits for sparse traversal. They are explanatory counters with different units, not direct throughput comparisons.

Reported memory counts are vector element payload plus scratch for one prepared formulation. They exclude capacities, container metadata, allocator overhead, LLVM storage and the other simultaneously retained comparison cases. They are not RSS or peak-memory measurements. The host rejects a function requiring more than 128 MiB for one block/value bit matrix; it does not silently omit a large function.

## What follows from a result

A sparse traversal win would favor preserving definitions, uses and CFG structure directly across analysis consumers. A Boolean-sweep win would support investigating naturally batched row execution; a loss would quantify how much iteration or conversion overhead an accelerator must overcome. A kernel win that disappears in the complete pass points to representation production and lifetime as the next useful boundary.

Any follow-up should use a real consumer or an actual device boundary and keep the current exact controls. This experiment supplies evidence for choosing that next step; it does not justify replacing every compiler pass with matrices.
