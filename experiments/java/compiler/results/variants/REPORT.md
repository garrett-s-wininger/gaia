# JVM compiler execution: GC, JIT, Leyden code caching and Native Image

An optimized native javac endpoint makes a fresh complete compilation much cheaper, but warmed compiler execution favors the JVM in this bounded test. Native Image finishes a fresh process in 346 ms and its late compile phase takes 288 ms. The experimental Leyden cache gives 873 ms fresh and 275 ms late compile. A separate 32-request trace reaches 206 ms with Parallel GC,255 ms with cached Leyden and 281 ms natively. JIT activity remains visible, so these are bounded warm-up observations.

The first actual `Worker.compile` also improves: 307 ms natively versus 737 ms with the EA compiled-method cache. The gain extends into first-compilation work, beyond process launch.

All final endpoints use one frozen Java source/JAR, complete Picocli 4.7.7 targets and the same Graal 25 target SDK class bytes. A second target changes the public VERSION constant and dependent bytecode. Independent Oracle 25, Graal 25 and EA 26 CLI compilers all emit exactly the same 227 classes here; each measured result must match its own CLI reference. Compiler implementations still differ across distributions, so within-toolchain controls carry the causal comparison.

## Clocks and controls

`compile_ns` measures `Worker.compile`: creating a fresh compilation task, resolving/reading sources and types, analysis, generation and file-manager flush. Compiling-thread CPU is measured with ThreadMXBean. File delivery and hashing have separate timers; client request wall and Linux whole-process CPU include those operations and concurrent runtime work. Fresh process lifetime includes initialization, one complete target, delivery and normal shutdown.

Each runtime has 32 MiB initial/768 MiB maximum Java heap and the same four-CPU affinity; JVMs also use four active processors. RSS is a separate post-request measurement, not a heap quota or peak. The machine is an AMD Ryzen AI 7 PRO 450 laptop under WSL2. Process launches use a warm host page cache. Runtime order is shuffled within three blocks. Annotation processing is disabled. Source membership is fixed at admission; mutable-body invalidation is checked separately.

The first table has eight warm requests per lifecycle; the shared runtime table has twelve. Late values pool the last three warm requests in each block. Fresh-process samples are separate launches. No process is declared JIT-settled from its request count.

## GC and JIT candidates, Oracle JDK 25.0.5.0.3

| Runtime | Fresh process ms | First compile ms | Late compile ms | Compile-thread CPU ms | Whole-process CPU ms | RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| G1 / normal tiered | 1642 | 1499 | 306 | 291 | 1060 | 378 |
| Serial / normal tiered | 1596 | 1426 | 397 | 286 | 1140 | 362 |
| Parallel / normal tiered | 1468 | 1280 | 267 | 257 | 940 | 467 |
| ZGC / normal tiered | 1753 | 1515 | 325 | 324 | 810 | 764 |
| C1 only, level 1 | 1238 | 1116 | 406 | 382 | 540 | 315 |
| C1 only, profiling level 3 | 1735 | 1623 | 810 | 774 | 930 | 290 |
| C2 only, tiered disabled | 2516 | 2384 | 330 | 302 | 670 | 369 |

C1 level 1 reduces fresh lifetime but gives slower late compilation. Level 3 keeps C1 profiling without enabling C2 and is substantially worse here. Disabling tiered compilation selects C2-only behavior; it does not disable C2. Parallel GC is the most promising throughput candidate in this bounded comparison. ZGC's median post-request RSS is 764 MiB. RSS is not heap usage, and the 768 MiB Java-heap cap is not an RSS quota.

## One endpoint: Graal JVM, experimental Leyden and native execution

| Runtime | Fresh process ms | First compile ms | Late compile ms | Compile-thread CPU ms | Whole-process CPU ms | RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Graal 25 JVM, Graal JIT / G1 | 1815 | 1664 | 330 | 303 | 780 | 436 |
| Graal 25 JVM, Graal JIT / Serial | 1872 | 1712 | 427 | 319 | 860 | 512 |
| Graal 25 JVM, C2 backend / G1 | 1744 | 1554 | 275 | 248 | 730 | 380 |
| Graal 25 JVM, C2 backend / Shenandoah | 1859 | 1693 | 335 | 326 | 1000 | 934 |
| LeydenEA2 JVM, uncached / G1 | 1540 | 1462 | 285 | 261 | 790 | 672 |
| EA2 AOT metadata/profiles, code off | 1277 | 1233 | 247 | 233 | 410 | 635 |
| EA2 AOT compiled methods enabled | 873 | 737 | 275 | 258 | 520 | 682 |
| Native Image 25 O2 / Serial | 346 | 307 | 288 | 288 | 310 | 108 |

The earlier JDK 25 AOTCache experiment already used Leyden's loading/linking and profiling work. This experiment adds EA2's compiled-method cache. Its code-enabled and code-disabled caches are assembled from one five-compilation recording under the same G1, heap and CPU settings. Logging proves 5,527 AOT code entries were admitted. These experimental features and their CPU/GC compatibility conditions are described in the [OpenJDK EA2 release notes](https://raw.githubusercontent.com/openjdk/leyden/leyden-ea2-release-notes/README.md).

The code cache improves fresh execution substantially; it establishes no late-throughput improvement over the metadata/profile cache in this table. Native execution is near the JVM's late compile phase, with much lower fresh-process cost and post-request RSS. Its lower whole-process CPU here includes the difference in ongoing runtime work; the longer trace below separates named worker activity.

Oracle 25 and the EA2 binary reject Shenandoah. Graal 25 includes it, but its default Graal JIT aborts with that collector. The paired Graal 25 C2-G1/C2-Shenandoah cases explicitly disable JVMCI and the Graal JIT while retaining normal C1/C2 tiering. Actual compiler requests and effective flags are checked, not just `java -version`. Shenandoah supplies no advantage in this measured pair.

## Longer bounded convergence diagnostic

| Runtime | Requests 17–24 compile ms | Requests 25–32 compile ms | Compile-thread CPU ms | Whole-process CPU ms | Named JIT CPU ms | Named GC-worker CPU ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| G1 / normal tiered | 260 | 235 | 213 | 430 | 90 | 90 |
| Parallel / normal tiered | 215 | 206 | 202 | 370 | 120 | 25 |
| EA2 AOT compiled methods enabled | 268 | 255 | 243 | 400 | 75 | 80 |
| Native Image 25 O2 / Serial | 284 | 281 | 281 | 310 | 0 | 0 |

Each row is one independent 32-request diagnostic with source/output guards, separate from primary latency measurements. All three JVM traces still improve between the preceding and final eight requests. Named C1/C2/JVMCI thread counters show continued JIT work. The native trace changes little and has no JIT worker CPU.

Thread-name classification is a heuristic over Linux 10 ms CPU ticks. “Named GC-worker CPU” covers recognized worker names. Foreground CPU includes work executed on that thread; VM-thread work is not classified exclusively as GC. Exited threads and counter quantization can leave an unattributed remainder. Independently computed medians are not an exact additive CPU balance. The traces support further convergence work, not a claim of peak throughput or a settled CPU-cost ranking.

## Epsilon under the same memory budget

| Runtime | Fresh process ms | First compile ms | Late compile ms | Compile-thread CPU ms | Whole-process CPU ms | RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Native Image 25 O2 / Serial | 306 | 270 | 275 | 275 | 290 | 137 |
| Native Image 25 O2 / Epsilon | 343 | 289 | 369 | 369 | 390 | 339 |

These epochs have exactly two compilations per resident lifecycle. Epsilon is slower and retains more resident memory. A separate growth probe completes four targets, reaching 648 MiB RSS; the fifth attempt exhausts its 768 MiB Java heap and exits 12 with an OutOfMemoryError/fatal detach diagnostic. The failure is retained. Both primary short-epoch endpoints exit normally and pass the same output guards. Native Image selects Epsilon at build time; its no-reclamation behavior and runtime heap flags are documented in [GraalVM memory management](https://www.graalvm.org/jdk25/reference-manual/native-image/optimizations-and-performance/MemoryManagement/).

Additional allocation/page preparation is a possible explanation for the CPU increase, but this experiment has no allocation or page-fault counters to establish that cause. The observed CPU, RSS growth and capped failure are sufficient to reject Epsilon as an unbounded compiler-pool default here.

## Native SDK interface and setup cost

The native runtime's default jrt resource filesystem cannot supply the target SDK's complete class bytes. The adapter supplies all 77 SDK modules through the public [StandardJavaFileManager module-location interface](https://docs.oracle.com/en/java/javase/25/docs/api/java.compiler/javax/tools/StandardJavaFileManager.html). This uses the exact SDK class bytes. JVM endpoints use the same representation. A named java.sql module must match CLI output; missing readability and an unexported JDK package must be rejected.

SDK extraction costs 7.31 s and 161.1 MiB of class files. The final Serial image builds in 75.54 s with 2.89 GB peak builder RSS and a 38.93 MB executable; Epsilon builds in 70.48 s with 2.81 GB peak RSS and a 37.10 MB executable. Both use optimized O2 builds, fallback disabled, four native compilation threads and a 4 GiB builder heap. The compiler-thread setting is not a total CPU quota for the builder. The actual runtime CPU affinity is shared across all candidates.

EA recording costs 4.11 s. Code-cache assembly costs 6.88 s/56.53 MB; code-disabled assembly costs 1.07 s/33.98 MB. Toolchain downloads, Java compilation, SDK generation, reachability training and cache/image construction are admission costs, outside runtime tables. The earlier quick-build prototype uses different instrumentation and is preserved as exploratory evidence with its actual source hash; it supplies no final O2-versus-Ob throughput comparison.

## Validation and useful next tests

All 51 primary cases pass 654 complete-target bytecode checks and 45 deliberate syntax-error/recovery checks. Four independent JVM consumers parse real emitted Picocli classes and verify both versions. A retained native file manager rereads a same-path, same-size, mtime-preserving source edit. SDK/module probes pass. The 128 additional convergence compilations also match their CLI oracle.

The next useful work is a broader source corpus and isolated follow-ups: a longer convergence study before selecting a persistent-pool JIT policy; Native Image PGO/target-feature controls before drawing code-generation conclusions; and a packed SDK/JavaFileManager input representation before attempting reuse of parsed platform metadata. Generic SDK metadata is especially interesting because it repeats across compilation tasks. It needs fresh task bindings and correctness checks, rather than sharing mutable javac symbol objects.

This proof covers one source graph, target 25, disabled annotation processors and selected module behavior. Arbitrary processors/plugins, release targets, module graphs and pooled native contexts remain open. See [reproduction](../../variants/README.md), [summary](summary.json), [validation](validation.json), [provenance](provenance.json), and the ignored raw observations for [flags](flags/results.json), [runtime comparison](head/results.json), [Epsilon](epsilon/results.json) and [diagnostics](diagnostics/results.json).
