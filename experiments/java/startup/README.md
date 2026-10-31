# JVM startup with declared framework knowledge

This experiment executes regular JVM bytecode. It builds static CDS archives from package-provided class names without executing the application, recording an application trace or compiling a native image. The [human review](../../../research/java/findings.md) and [report](results/initial/REPORT.md) explain the gains and remaining initialization work.

The fixture uses pinned Groovy 6.0.0 and Picocli 4.7.7 with JDK 25.0.5.0.3. `Command.java` compares parser construction, statically compiled Groovy and an actual runtime `GroovyShell` expression. The parser's ordinary factory discovers Groovy when its JAR is present; this is measured behavior rather than an isolated Picocli baseline. `PlainPicocli.java` and `EmptyMain.java` provide separate honest controls.

## Acquire locally

Place a compatible JDK in ignored `_work/toolchain/` and the pinned `groovy-6.0.0.jar` and `picocli-4.7.7.jar` in ignored `_work/downloads/`. The [provenance](results/initial/provenance.json) records original URLs, SHA-256 identities and sizes. The JDK's original `latest` URL is mutable; verify the recorded hash to reproduce that exact distribution, or explicitly record a new toolchain when repeating the experiment. Do not assume a newly downloaded release has the old identity.

No system installation, Gradle, Maven, native compiler or native-image tool is required. The JDK supplies `java`, `javac`, `jar` and `lib/classlist`. Every dependency JAR is hash-checked before use. JAR/source compilation, classlist production and archive creation are outside consumer timing and recorded separately.

## Run

```sh
python3 -B experiments/java/startup/benchmark.py \
  --jdk /path/to/jdk \
  --downloads /path/to/pinned-jars \
  --linking --core --trials 7 \
  --output experiments/java/startup/_work/runs/declared-core
```

This builds all three archive forms and compares default CDS, a broad classic static archive, a broad `AOTClassLinking` archive and a declared-core `AOTClassLinking` archive. Dropping `--core` retains the broad-linking comparison; dropping both flags compares CDS off, default and explicit classic. Each run randomizes paired blocks, validates fresh env/token and output, and records exact sources, runtime version, archive identities and class-loading/initialization diagnostics.

The classlist starts with the JDK's supplied default list. The broad list adds every non-multi-release class name found in the two JARs. The core list uses all Picocli names plus the explicit Groovy roots listed in the script; dependencies discovered by JVM loading/linking can add more classes. No list is derived from workload execution. The archive classpath contains only the two framework JARs; the application JAR is appended at runtime.

Phase controls use a completed run's raw file:

```sh
python3 -B experiments/java/startup/controls.py \
  --run experiments/java/startup/_work/runs/declared-core/results.json \
  --trials 7 --output experiments/java/startup/_work/runs/phase-controls
GAIA_JDK=/path/to/jdk python3 -B -m unittest discover \
  -s experiments/java/startup -p 'test_*.py' -v
```

Controls compile a separate Java-only parser and empty process, compare classpaths with/without Groovy and Picocli's closure feature toggle, and correlate Java/Python monotonic clocks on Linux. The clock relationship is checked for every observation; another platform/JVM that does not satisfy it is rejected. Phase timers and normal-shutdown hooks are diagnostic harness overhead and apply consistently within those controls; do not subtract their medians from the separate main fixture.

`-Xshare:on` makes unusable archives fail visibly during the experiment. Ordinary production launchers usually want fallback behavior (`auto`) and an explicit archive admission/invalidation policy instead. The regression test verifies that an archived application class still executes its initializer with fresh process state and that altered archived JAR identity is rejected.

All generated archives, toolchains, JARs, bytecode, raw logs and frozen experiment sources remain under ignored `_work/`. Full published observations under `results/**/results.json` are also ignored and identified by the repository evidence manifest. Reports, compact summaries, provenance and correctness evidence remain versioned.

## Prepared Groovy method data

The [DGM report](results/dgm-binding/REPORT.md) compares published/rebuilt Groovy, serial binding and dense class-ID binding over the unchanged package-provided method table. [dgm_prepare.py](dgm_prepare.py) builds bounded research variants, [dgm_benchmark.py](dgm_benchmark.py) measures fresh complete processes with matching CDS, and [test_dgm.py](test_dgm.py) checks mutable metaclasses, independent loaders and new extension modules. The Groovy source JAR is pinned and required alongside the binary JAR. See the report for commands and producer costs.

[registry_profile.py](registry_profile.py) is a separate intrusive source-timer diagnostic. It takes a completed DGM run, JDK and fresh output directory; never run it alongside latency measurements or pool its timings with uninstrumented controls.

[Experiment notes](FINDINGS.md) retain the detailed comparisons behind the linked research review and reports.

The [JVMTI follow-up](jvmti/README.md) quantifies diagnostic overhead and finds additional module/runtime-image metadata work. Its [report](results/jvmti/REPORT.md) preserves the unstable first candidate matrix and dynamic-behavior validation.
