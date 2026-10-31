# Managed JVM compiler research

A real Picocli source compilation compares full JDK/jlink CLIs, fresh JavaCompiler API processes, a trained compiler AOT cache and resident private compiler contexts. Start with the [report](results/initial/REPORT.md), [human findings](../../../research/compiler/jvm/findings.md) and [prospects](../../../research/compiler/jvm/prospects.md).

## Inputs and preparation

Provide a local JDK 25 and the official Picocli 4.7.7 binary/source JARs. [Provenance](results/initial/provenance.json) records their exact hashes and the measured JDK identity. The driver verifies the JARs and extracts all three Java sources. Their target SDK is the same full JDK for every runtime, passed explicitly with `--system`; the minimal compiler image is not a complete replacement for that SDK.

```sh
python3 -B experiments/java/compiler/benchmark.py \
  --jdk /path/to/jdk-25 \
  --picocli-jar /path/to/picocli-4.7.7.jar \
  --sources /path/to/picocli-4.7.7-sources.jar \
  --prepare-only
```

Preparation compiles the harness, constructs a five-module jlink image, copies the supplied classlist if necessary, and generates a compatible default CDS archive with the measurement VM flags. It prints a local `prepared.json` path. All generated data belongs under ignored `_work`; that name may also be an ignored symlink to a larger local volume.

A second complete source target changes the public `CommandLine.VERSION` constant. Both targets compile all three sources jointly, against an empty project classpath. There is no prebuilt project JAR providing stale symbols to independent per-file tasks.

Compiler AOT training is an explicit separate preparation step:

```sh
python3 -B experiments/java/compiler/benchmark.py \
  --prepared /path/to/prepared.json --train --prepare-only
```

It executes one real compiler request and records/assembles the JDK AOT cache. Subsequent cached launches require it with `AOTMode=on`; incompatible caches fail instead of silently falling back. This training is for the compiler track and is not the separate Groovy no-application-training experiment. No Native Image toolchain is used.

## Measure and verify

```sh
python3 -B experiments/java/compiler/benchmark.py \
  --prepared /path/to/prepared.json \
  --trials 3 --pair-trials 3 \
  --output experiments/java/compiler/_work/runs/comparison
GAIA_JVM_PREPARED=/path/to/prepared.json \
  python3 -B -m unittest discover -s experiments/java/compiler -p 'test_*.py' -v
```

Single-target and two-target rows perform different work and must remain separate. Resident services receive a validated first request and excluded warmup before paired observations; their startup/first/shutdown costs are recorded for lifecycle accounting. Every measured request compiles, delivers and hashes actual classes. The API's memory endpoint is separate from file publication. The final byte set is also consumed by a fresh in-process class loader, outside compile/delivery latency timing.

The pool schedules independent **complete compilation targets** with one compiler/file manager per worker, reused sequentially on that worker. It does not split a mutually dependent Java source graph into files against old binary classes. Processing is disabled (`-proc:none`), and source/target 25, the admitted SDK and all other flags match the CLI controls. Heap size/processor count are explicit; RSS is sampled, CPU time is not collected.

If the harness source changes, create fresh preparation or explicitly use `--rebuild-harness --prepare-only`; doing so invalidates the previous trained-cache selection. Do not reuse an old cache while claiming a new measured binary/source identity. Keep source/SDK inputs immutable during a performance run; the driver rechecks admitted source hashes before starting.

[CompilerHarness.java](CompilerHarness.java) owns task contexts, bounded queues and memory/file delivery. [benchmark.py](benchmark.py) owns preparation, lifecycle, comparisons and byte checks. [test_compiler.py](test_compiler.py) verifies no-loose-file delivery, same-path constant edits with preserved mtime, dependent outputs, failure recovery and current target data under the trained cache.

The prototype does not implement a general build graph, incremental result cache, processor sandbox, cancellation protocol or long-lived-service memory quota. All archives, runtime images, JARs, bytecode, raw observations and frozen sources remain ignored. Rebuild on the machine under test rather than replaying historical absolute paths.

[Experiment notes](FINDINGS.md) retain the detailed comparisons behind the linked research review and reports.
