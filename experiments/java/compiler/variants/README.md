# JVM compiler variants

The [report](../results/variants/REPORT.md) separates compiler execution from startup. One JavaCompiler endpoint runs under GC/JIT variants, experimental Leyden compiled-method caches and optimized Native Image. Its `compile_ns` covers `Worker.compile`, including fresh task creation and file-manager flush. Separate fields record compiling-thread CPU, class-file delivery, hashing, client request wall, whole-process CPU and fresh normal-process lifetime.

Every final endpoint uses the same Picocli 4.7.7 complete three-unit targets and the same explicit 77-module Graal 25 SDK representation. TargetB changes the public VERSION constant and its dependent output. Each runtime's independent CLI compiles both targets through the ordinary SDK; all three compiler distributions happen to produce identical bytes here. Source-set membership is fixed at admission. A separate same-path/size/mtime edit test checks mutable file contents with a retained native file manager.

All setup is outside primary clocks: verified downloads, Java compilation, SDK extraction, reachability training, AOT recording/assembly and Native Image builds. Annotation processing is disabled (`-proc:none`). Every runtime has 32 MiB initial/768 MiB maximum Java heap, a common four-CPU affinity and four active processors where the JVM supports that flag. RSS is measured separately and has no 768 MiB cap. HotSpot performance-data files are disabled to avoid PID collisions across Linux sandbox namespaces. Ambient Java option injection is removed from measured process environments.

## Reproduction

Acquire and verify the archives in [toolchains.json](toolchains.json). Paths below are caller-supplied. Run commands from this directory. `GAIA_RUN` must be a fresh ignored directory with enough space for toolchains and generated SDK files.

```sh
python3 prepare.py --jdk "$GAIA_GRAAL" --sources "$GAIA_PICO_SOURCES" --output "$GAIA_RUN/prepared-instrumented"
python3 unpack_sdk.py --jdk "$GAIA_GRAAL" --output "$GAIA_RUN/platform-sdk"
python3 build_native.py --optimization 2 --gc serial --prepared "$GAIA_RUN/prepared-instrumented/prepared.json" --modules "$GAIA_RUN/platform-sdk" --output "$GAIA_RUN/native-final-serial"
python3 build_native.py --optimization 2 --gc epsilon --build-only --configuration "$GAIA_RUN/native-final-serial/reachability" --prepared "$GAIA_RUN/prepared-instrumented/prepared.json" --output "$GAIA_RUN/native-final-epsilon"
python3 configure_endpoint.py --prepared "$GAIA_RUN/prepared-instrumented/prepared.json" --oracle "$GAIA_ORACLE25" --ea "$GAIA_LEYDEN" --data "$GAIA_RUN"
python3 prepare_endpoint.py --data "$GAIA_RUN"
```

`prepare_endpoint.py` creates independent CLI references, records five complete compiler tasks, assembles code-enabled/disabled caches from that same recording, verifies actual cache admission with AOT logging, and probes actual compiler requests under every JVM candidate. Check availability on the destination machine. In this run, Oracle 25 and EA2 omit Shenandoah. Graal 25 supplies it but requires disabling its JVMCI compiler; use the matched C2-G1 control too. `effective-flags.json` records the effective GC/JIT settings. There is no automatic toolchain substitution.

`configure_endpoint.py` declares a bounded candidate set. Its paths and collector availability must be reviewed for a different acquisition. Once prepared, freeze the sources and run the three independent interleaved comparisons:

```sh
python3 freeze.py --data "$GAIA_RUN"
python3 measure_endpoint.py --prepared "$GAIA_RUN/prepared-instrumented/prepared.json" --config "$GAIA_RUN/flags-config.json" --references "$GAIA_RUN/endpoint-references.json" --modules "$GAIA_RUN/platform-sdk" --output "$GAIA_RUN/flags-main" --trials 3 --warm-count 8
python3 measure_endpoint.py --prepared "$GAIA_RUN/prepared-instrumented/prepared.json" --config "$GAIA_RUN/head-config.json" --references "$GAIA_RUN/endpoint-references.json" --modules "$GAIA_RUN/platform-sdk" --output "$GAIA_RUN/head-main" --trials 3 --warm-count 12
python3 measure_endpoint.py --prepared "$GAIA_RUN/prepared-instrumented/prepared.json" --config "$GAIA_RUN/epsilon-config.json" --references "$GAIA_RUN/endpoint-references.json" --modules "$GAIA_RUN/platform-sdk" --output "$GAIA_RUN/epsilon-main" --trials 3 --warm-count 1 --short
```

Epsilon epochs have exactly two successful compilations per resident lifecycle under the same heap cap as Serial. `post_checks.py` separately records up to 16 Epsilon attempts and stops on the first failure. It preserves the resulting out-of-memory failure and exit status. Never increase only Epsilon's heap to admit more requests.

```sh
python3 convergence.py --data "$GAIA_RUN" --count 32
python3 post_checks.py --data "$GAIA_RUN"
python3 test_native_mutation.py --prepared "$GAIA_RUN/prepared-instrumented/prepared.json" --modules "$GAIA_RUN/platform-sdk" --native "$GAIA_RUN/native-final-serial/native-compiler" --output "$GAIA_RUN/native-mutation"
python3 probe_sdk.py --prepared "$GAIA_RUN/prepared-instrumented/prepared.json" --modules "$GAIA_RUN/platform-sdk" --native "$GAIA_RUN/native-final-serial/native-compiler" --output "$GAIA_RUN/sdk-final-probes"
```

The 32-request diagnostic reads Linux thread CPU counters around each request. Names classify C1/C2/JVMCI and named GC workers; counters are coarse, exited-thread CPU can be missing, and foreground work is not attributed to named workers, and VM-thread work is not exclusively GC. Its samples are separate from primary latency runs. It retains the full trace and compares the preceding/last eight requests without declaring a peak steady state.

`NativeOutputCheck.java` consumes emitted bytecode in a separate JVM, outside compiler clocks. SDK probes require a named module using java.sql to match CLI output and require missing-readability/private-package cases to fail. The native SDK boundary must fail visibly if the explicit module representation is omitted: a native image's default jrt resource filesystem does not provide the target SDK's complete class bytes.

The public `StandardJavaFileManager.setLocationForModule(SYSTEM_MODULES, ...)` adapter supplies every exact SDK module class file. This proves a useful interface and the tested module behavior; arbitrary module graphs, release targets and annotation processors still need a broader test corpus.

## Evidence and follow-up

`publish_results.py` copies compact observations into ignored result paths and generates summaries, validation, provenance, the experiment index and evidence hashes. Human interpretation stays in the report and research findings. Recreate inputs on the destination machine; recorded absolute paths in raw observations describe the original run.

`run_native.py` and `run_variants.py` also contain earlier exploratory entry points; the final matrix uses `measure_endpoint.py`. The earlier quick-build image has different instrumentation and is retained as exploratory evidence, without a final build-level throughput comparison. The final Serial and Epsilon images share one frozen source/JAR, SDK and reachability configuration and both use ordinary optimized `-O2` builds with fallback disabled.
