# One JVM or many compiler JVMs

This experiment compares a bounded set of private JavaCompiler workers in one JVM with the same number of workers spread across separate JVMs. Each queue item compiles a complete pinned Picocli target. Compiler tasks, file managers and diagnostics stay private to a worker; immutable compiler code and runtime state can be shared inside one process.

The comparison varies 1, 2, 4 and 8 total worker slots. Every batch compiles eight complete targets, alternating original and public-constant-edited source trees. Both paths use the same compiler, target SDK, flags and byte-delivery contract. Each target's 227 class files must match an independent CLI reference. A fresh class loader also consumes the returned bytes and checks the current target version.

## Resource and timing contract

All compiler JVMs share the same eight-CPU affinity set. Their aggregate maximum Java heap is 3,072 MiB; it is divided evenly across JVMs rather than granting that entire budget to every process. G1 is explicit, and each JVM's `ActiveProcessorCount` is its share of the CPU budget. The effective heap caps are checked at startup. Other VM defaults remain active, so GC/JIT background threads and metadata are part of the topology cost. A heap cap is not an RSS quota. `ActiveProcessorCount` is an ergonomic input, not a per-process CPU pin or hard thread quota; all JVMs can run within the same shared affinity set. Runtime GC/JIT ergonomics and queue/cache locality are part of this topology comparison, not held-identical internals.

Measure startup, the first complete batch, an excluded warmup, late-window batches and normal shutdown separately. The primary two late batches do not establish fully converged steady state; a longer trace is a separate diagnostic. The complete lifecycle is recorded too. Compilation, memory delivery and digest calculation are included; the independent consuming class-loader checks occur afterwards. All eight targets must compile on every batch; there is no compiled-result cache.

RSS can count the same shared page in several JVMs. Endpoint observations therefore report aggregate PSS and private memory as well as RSS, using Linux `smaps_rollup`. Per-process observations are read sequentially, not as an atomic system snapshot. The [kernel documentation](https://docs.kernel.org/filesystems/proc.html) defines those counters.

Continuous memory sampling is a separate diagnostic run because reading memory maps can perturb the measured process. Its reported maximum is the largest observed **sequential aggregate**, not an enforced memory limit or exact simultaneous peak. Sequential per-process reads can overstate or understate an instantaneous group total when processes change between reads, so this is not a guaranteed lower bound on the true aggregate peak. Normal timing runs record command-boundary endpoints outside the operation clock; background GC/JIT activity can still change memory. JVM CPU time comes from each JVM's process counter, and controller CPU is separate.

`--gc-after` optionally requests GC only after all timed batches. That endpoint helps distinguish retained garbage/committed heap from immediately observed memory, but it is not an exact live-set measurement or proof that the remaining bytes are shared-runtime overhead. It must not be folded into latency samples or silently treated as a minimal-memory operating mode.

## Reproduce

Prepare the pinned JDK25 compiler inputs using the [parent experiment](../README.md). This driver copies both source trees into a new private run, builds its own harness and generates independent CLI references. The original prepared data and source trees are never edited.

```sh
python3 -B experiments/java/compiler/topology/run_topology.py \
  --prepared /path/to/prepared.json --trials 3 \
  --output experiments/java/compiler/topology/_work/main
python3 -B experiments/java/compiler/topology/run_topology.py \
  --prepared /path/to/prepared.json --workers 1 4 8 --trials 1 \
  --sample-interval 0.025 \
  --output experiments/java/compiler/topology/_work/memory-diagnostic
python3 -B -m unittest discover \
  -s experiments/java/compiler/topology -p 'test_*.py' -v
```

Use fresh output directories. `--workers 2 --tasks 2 --trials 1 --steady-batches 1` is a shorter correctness smoke. Child JVM option-injection environment variables are removed so flags cannot silently differ between topologies. Downloads, runtime images, generated classes, raw observations and local cache links remain ignored.

This is a whole-target queue and memory experiment. It does not establish annotation-processor safety, arbitrary source-graph partitioning, cancellation, long-lived service bounds or native-image equivalence.

## Measured runs

The [three-block primary comparison](results/primary/REPORT.md) finds shorter first and late batches in one JVM, with mixed memory results. The [separate ten-batch sampled trace](results/long-memory/REPORT.md) includes a requested-GC diagnostic outside compilation clocks. The [first incomplete attempt](results/failed-perfdata/REPORT.md) is preserved as environment failure evidence and excluded from timing statistics.

After completing the two runs, `python3 -B experiments/java/compiler/topology/publish_topology.py` checks every output, consumer version, heap/flag setting and frozen measured source before regenerating portable summaries. It expects completed local raw files under `_work/main-perfdata-off` and `_work/long-memory`; missing raw observations are not fetched automatically. Reports and compact observations remain versioned; full raw data stays ignored with hashes in provenance and the research evidence manifest.
