# Source operations, changing facts and resource models

These bounded studies connect set/patch, graph, order/lattice, scheduling, retention and geometry ideas to explicit correctness oracles. Read the [main report](results/first-pass/REPORT.md), [geometry report](results/geometry/REPORT.md), [actual compiler observations](results/compiler-observations/REPORT.md), and [human guide](../../../research/science/graphs/README.md). Simulation/model quantities are kept separate from measured algorithm/tool timings.

## What is implemented

| Boundary | Implementation | Scope |
| --- | --- | --- |
| Source-operation algebra | `patches.py` | Partial add/delete/replace over regular bytes, executable flags and symlink entries; conservative path-independent commutation. |
| Information/authority | `patches.py` | Set-union fact lattice retains alternatives; a serialized expected-generation publication model illustrates coordination. |
| Dynamic observations | `facts.py` | Ordered lookup candidates, negative queries, membership, environment and cyclic union facts. Full, frontier and materialized-relation evaluators. |
| Native frontier | `frontier.odin` | Bounded dense reverse reachability through borrowed buffers. It does not replace the observation interpreter. |
| Scheduling | `scheduling.py` | Discrete-event CPU/cold-input model; FIFO, critical-path, fairness, deques/work stealing and decaying affinity. |
| Retention | `retention.py` | Sequential DAG pebbles with dependency leases and producer scratch; exact offline oracle limited to 12 nodes. |
| Logical geometry | `embedding.odin`, `geometry.py` | Train-only force layout in 1D/3D and fixed-size group ordering for a shared real access trace. |
| Actual compiler observations | `compiler_observations/` | Clang 22 VFS adapter with source-root observations, validation skips and refreshed depfiles on identical-IR hits. |

None selects a production source-control format, compiler service, public graph protocol or operating-system scheduler. Full snapshots remain the source truth; patch classification does not prove semantic program/test/review independence.

## Reproduce

Requirements: Python 3.10+, Linux, Odin, and a C linker driver. Native compiler oracle probes additionally require a compatible Clang. Supply an existing Ninja project/dependency-log fixture only for the captured positive-relation comparison; another project's relation is a new measurement. All generated data belongs in disposable caller-selected paths.

From the repository root, with fresh `$WORK` and `$OUTPUT` paths:

```sh
mkdir -p "$WORK"
odin build experiments/science/graphs/frontier.odin -file -build-mode:obj -o:speed -out:"$WORK/frontier.o"
cc -shared "$WORK/frontier.o" -o "$WORK/frontier.so"
odin build experiments/science/graphs/embedding.odin -file -build-mode:obj -o:speed -out:"$WORK/embedding.o"
cc -shared "$WORK/embedding.o" -o "$WORK/embedding.so" -lm
GAIA_EMBEDDING_LIBRARY="$WORK/embedding.so" python3 -B -m unittest discover -s experiments/science/graphs -p 'test_*.py'
python3 -B experiments/science/graphs/run.py \
  --work "$WORK/main" --output "$OUTPUT/main" --lock "$MEASUREMENT_LOCK" \
  --clang "$CLANG" --library "$WORK/frontier.so" \
  --ninja-project "$NINJA_PROJECT" --trials 3
```

The optional `--clang`, `--library` and `--ninja-project` flags enable separate probes; omitted probes are explicitly marked not run. Supply absolute tool paths. Each measured case acquires/releases the shared advisory lock. Preparation, oracle computation and unrelated host work may overlap; no idle-host guarantee follows.

`facts.py` is an explicit observation language, not a C preprocessor. Its local facts include selected path/content identities, directory membership and requested environment values. The frontier computes fresh fixed points over affected nodes; deletions remove prior facts rather than subtracting from a cyclic result blindly. The relational mode materializes root/node reachability and rebuilds it on topology changes. It is not an implementation of Differential Dataflow.

The main three-TU compiler probe uses declared lookup choices and an actual Clang object oracle. The separate extension extracts actual Clang observations, with scope and measured results in its report. Captured Ninja target IDs reuse the test-selection machinery but represent compile targets; they do not constitute a real test suite or a sound updated production scheduler.

Build the actual-observation extension with a compatible Clang 22 development SDK. Some distributions split generated headers into a separate directory; supply that directory through `LLVM_GENERATED_INCLUDE`.

```sh
c++ -O2 -std=c++17 -I"$LLVM_INCLUDE" -I"$LLVM_GENERATED_INCLUDE" \
  experiments/science/graphs/compiler_observations/observed_host.cpp \
  -L"$LLVM_LIBRARY" -Wl,-rpath,"$LLVM_LIBRARY" -lclang-cpp -lLLVM-22 \
  -o "$WORK/observed-host"
GAIA_OBSERVED_HOST="$WORK/observed-host" GAIA_CLANG="$CLANG" \
  python3 -B -m unittest discover -s experiments/science/graphs/compiler_observations -p 'test_*.py'
python3 -B experiments/science/graphs/compiler_observations/run.py \
  --host "$WORK/observed-host" --clang "$CLANG" --work "$WORK/observations" \
  --output "$OUTPUT/observations" --lock "$MEASUREMENT_LOCK" --trials 3
```

## Geometry input and interpretation

The data lane supplies a frozen `GAIA-COACCESS-1` JSON input with chunk sizes/pins, training-only weighted edges, training/held-out access IDs and a synthetic reverse trace. The recorded input contains 437 actual Django payload chunks and 1,629 edges derived from the first fresh start. Held-out access comes from another fresh start of the same application; it is not an unseen workload.

```sh
python3 -B experiments/science/graphs/geometry.py \
  --input "$COACCESS_INPUT" --library "$WORK/embedding.so" \
  --output "$OUTPUT/geometry/results.json" --lock "$MEASUREMENT_LOCK" --iterations 80
```

Only training edges initialize layout. The force model uses attraction on weighted edges, pairwise repulsion, bounded updates and centering, starting from one deterministic random seed. 1D order sorts the coordinate; 3D order uses quantized Morton keys. Complete permutations include unaccessed chunks. This is a logical embedding, not placement in hardware coordinates or a claim that three dimensions are inherently better.

The local geometry model caches whole eight-chunk groups under an 8 MiB payload budget. The data lane's actual verified-reader comparison uses per-chunk LRU and includes full repacking. Their read counts differ because the cache semantics differ. Compare policies within a single evaluator; never combine those counts into one speedup.

## Correctness and lifecycle limits

Fifteen tests cover tiny patch laws/context rejection, lattice joins, stale publication, negative/shadowing/membership/environment changes, graph cycles/removals, selected test/editor identities, safe cancellation, durable jobs, dependency leases, offline-cost bounds, geometry permutations and native numeric behavior on the supported fixtures.

The scheduling trace is deterministic model work; task durations are declared units. Its measured Python decision cost is separate. Cancellation occurs only at declared safe boundaries, and a new arrival does not create a new safe point. A preliminary version violated that distinction; it was corrected and rerun before the published primary measurement.

A [supplemental calibration](results/scheduler-calibration/REPORT.md) measures actual small C frontend/compiler/test/search subprocess tasks, then feeds those durations into the model. `calibrate_schedule.py --clang "$CLANG" --work "$WORK/calibration" --output "$OUTPUT/calibration/results.json" --lock "$MEASUREMENT_LOCK"` reproduces it. This still does not execute a concurrent scheduler or provide actual compiler cancellation callbacks.

The retention model counts payloads, pinned dependency pebbles and producer scratch, not process RSS. Malformed updates and arbitrary concurrent writers are outside the in-process fact model; a failed instance is not a transactional persistent service. The authority example is serialized, not a concurrent/durable CAS implementation.
