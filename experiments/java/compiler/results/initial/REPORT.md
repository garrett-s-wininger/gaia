# A small JVM compiler runtime, prepared cache and private compiler queue

Programmatic compilation becomes much faster when the initialized JVM/compiler is reused. A smaller runtime alone shows no dependable latency gain. A trained AOT cache improves fresh launches, and a bounded queue of private compiler contexts improves throughput when each task owns a complete compilation target.

This is ordinary JVM bytecode compilation through `javax.tools.JavaCompiler`, not native-image compilation. It uses real Picocli 4.7.7 sources: the 1.24 MB `CommandLine.java`, 55 KB `AutoComplete.java` and package descriptor. Every single target produces exactly 227 classes/755,217 bytes matching independent CLI output. A second target changes the public version constant, exercising dependent annotation/constants across the complete source graph.

## One complete target

Run `20261031T032913.223449Z`; three randomized paired blocks per mode, warm pages, actual compilation on every request. Cold measurements include process creation, compilation, class delivery/hash verification and normal shutdown. Resident clocks include request/reply, compilation, optional class-file publication and hashes; startup/first request/shutdown are recorded separately.

| Delivery mode | Complete operation |
| --- | ---: |
| Full JDK `javac`, class files | 1,492 ms |
| jlink image `javac`, class files | 1,471 ms |
| Fresh full-JDK JavaCompiler API, class files | 1,529 ms |
| Fresh image JavaCompiler API, class files | 1,563 ms |
| Fresh image API + trained AOT cache, class files | **1,130 ms** |
| Warm resident image API, class files | **415 ms** |
| Warm resident image API, owned memory bytes | **354 ms** |

The jlink CLI wins only one of three paired blocks against full `javac`; its median difference is not evidence of a dependable speedup. A new JVM calling the API does not beat the CLI either. The trained cache and resident modes win all three blocks against the full CLI in this fixture. Prepared cold API is about 24% below CLI; warm file-delivering API about 72% below it.

Memory delivery is a distinct endpoint. The file-delivering resident spends a median 31 ms writing classes; the memory mode skips those writes. Their total median gap is 61 ms, which also contains separate resident/JIT variation; it cannot all be attributed to filesystem output. Both deliver the same class bytes. The workload does not cache compiled outputs or ASTs: every request makes a new compilation task and compiles all three sources.

## Two independent complete targets

Java source files are not generally independent translation units. Compiling one file against stale prebuilt classes can miss changed constants or source APIs. This experiment therefore queues **whole three-source compilation targets**, each with a private task/file-manager context. The compiler classpath is empty; no prebuilt Picocli JAR supplies stale project symbols.

Target A is the pinned source. Target B changes `CommandLine.VERSION` to `4.7.7-gaia-probe`; `AutoComplete` embeds that constant in dependent annotations/strings. The pair produces 454 classes/1,510,478 bytes. Each target is compiled jointly before delivery. This is not parallel source-file compilation within a single Java target.

| Same two-target work | Batch completion |
| --- | ---: |
| Two cold CLI processes running concurrently | 1,969 ms |
| Resident API, complete targets sequentially | **619 ms** |
| Resident API, two private compiler workers | **448 ms** |

Both resident modes win all three blocks against the two-CLI baseline. The pool's median is about 28% below sequential reuse for the same work, at a larger observed resident footprint. Target readiness, grouping and input discovery are supplied by the fixture, not solved by a new build system. This is one small graph and three blocks, not a universal scheduling result.

Each worker owns its compiler/file manager and uses it sequentially. No mutable compiler context, file manager or task is used concurrently. The queue and worker count are bounded (two workers measured; at most four supported). The [JavaCompiler API documentation](https://docs.oracle.com/en/java/javase/25/docs/api/java.compiler/javax/tools/JavaCompiler.html) recommends file-manager reuse across sequential compilations; the harness extends that pattern by keeping separate worker-owned managers.

## Runtime image, target SDK and preparation costs

`jlink` builds a five-module image: `java.base`, `java.compiler`, `jdk.compiler`, `jdk.internal.opt` and `jdk.zipfs`. The image is **66.7 MiB including a freshly generated 13.4 MiB default CDS archive**. The archive is constructed with the same VM settings before comparing startup. The image is not an archive-disabled baseline.

An untimed [CDS reader check](default-cds-validation.json) confirms actual base-class sharing in both CLI launchers (856/887 shared loads in the version probe). Their archived module-graph optimization falls back because `javac` launches module `jdk.compiler`, unlike the default dump entrypoint. Base class sharing remains enabled in both; neither is a CDS-disabled control. A module-main-specific prepared CLI archive is a separate possible control.

The compiler's **target SDK remains the same full pinned JDK**, explicitly supplied through `--system`, for every mode. A small compiler runtime does not imply that this experiment needs only 66.7 MiB installed in total. Runtime modules and target-library metadata are separate inputs; arbitrary target applications are not promised to execute on the minimal compiler image. [jlink documentation](https://docs.oracle.com/en/java/javase/25/docs/specs/man/jlink.html) describes constructing a module closure and optional CDS generation.

Measured setup observations:

| Preparation | Cost |
| --- | ---: |
| jlink image construction | 2.63 s |
| Default CDS generation | 0.49 s |
| Initial harness compilation | 0.81 s |
| Final compiler AOT training/assembly | 2.96 s |
| AOT cache size | 26.8 MiB |

The AOT cache is trained by one actual compiler request, then assembled by JDK 25. Training is explicitly allowed for this compiler experiment; it is separate from the Groovy supplied-knowledge/no-application-training question. Production observations use fail-fast `AOTMode=on`, so an incompatible cache cannot silently fall back. The cache does not precompile target applications to native code or preserve their previous compilation results. A separately trained CLI cache was not measured: this gain demonstrates preparation, not a capability exclusive to the programmatic API. [JDK AOT options](https://docs.oracle.com/en/java/javase/25/docs/specs/man/java.html#ahead-of-time-cache) describe that record/assembly/use workflow.

All modes share `-Xms32m -Xmx768m -XX:ActiveProcessorCount=4` and the same compiler options: UTF-8, `-g:none`, `-proc:none`, `-implicit:none`, source/target 25, explicit SDK and empty project class/source paths. Annotation processors/plugins are outside this first proof. The runtime bound is a heap limit, not an RSS or total-process quota.

## Lifecycle and memory

These are separate startup/first-request observations, not cold-pool latency distributions:

| Resident mode | Start/ready | First request | Normal shutdown | Median warm post-request RSS |
| --- | ---: | ---: | ---: | ---: |
| Single target, class files | 89 ms | 1,373 ms | 35 ms | 332 MiB |
| Single target, memory | 97 ms | 1,516 ms | 32 ms | 312 MiB |
| Two targets, sequential | 125 ms | 2,135 ms | 26 ms | 316 MiB |
| Two targets, private pool | 110 ms | 1,627 ms | 45 ms | 444 MiB |

The first request still pays substantial lazy initialization/JIT work. A warm-request comparison must not hide it. For example, the file-delivering single-target mode models about 1,497 ms for one session request including lifecycle and 632 ms/request across five. The pool models about 715 ms per two-target batch across five batches. These use measured one-time startup/first/shutdown and median warm requests; they are not measured session distributions or paired cold-pool claims.

RSS is sampled after work; it is not peak memory. Four comparison services are resident during the run, and file-backed pages may be shared. CPU time/cycles were not collected, so there is no claim of lower CPU cost. Longer runs, varied projects, quotas, cancellation, processor isolation and memory-growth/recovery policies remain open.

## Real in-process bytecode handoff and validity

The API file manager captures class bytes. After the timed observations, a fresh in-process class loader consumes the last complete byte set, constructs a real Picocli command model and parses an integer option. Target versions are checked separately for A/B. These consumer checks take roughly 28–52 ms in single additional observations; they are **outside** the compile/delivery latency table. There is no claim of a native linker or a measured compile-plus-execute pipeline.

The [three regression tests](correctness-tests.txt) verify memory output without loose class files, private-worker lifecycle and failed-compilation recovery, and current input compilation under a trained cache. They also edit a public constant at the **same source path while preserving its mtime**, compare all dependent class bytes with a new CLI reference, restore it and verify recovery. The trained cache handles the distinct target version correctly; it does not freeze the training source's result.

All 30 timed operations validate complete output hashes, counts and bytes against independent CLI references; one-target and two-target work counts remain separate. Additional seeds/warmups, corrected-implementation smoke checks and regressions are excluded from that count. See [summary](summary.json), [validation](validation.json) and [provenance](provenance.json).

## Reproduction and boundaries

Use the [experiment README](../../README.md), [Java harness](../../CompilerHarness.java), [driver](../../benchmark.py) and [tests](../../test_compiler.py). The project sources and JDK are pinned; image construction and training can be reproduced locally. Reused SDK/source assumptions are explicit, and every compiler task actually executes.

This does not implement a general Java build graph, incremental compiler, remote execution system, daemon lifecycle product or portable compiler protocol. Classpath/module mutation and processors require their own admission/isolation contracts. Supplied whole-target requests are an appropriate unit for the bounded pool; arbitrary per-file splitting is not.

Raw `results.json` is an ignored local artifact registered in the [evidence manifest](../../../../../research/evidence.json). Toolchains, runtime images, trained caches, bytecode and frozen measured sources remain ignored. Reports, compact summaries, provenance and correctness results remain versioned. Nothing was staged, committed or merged by this experiment.
