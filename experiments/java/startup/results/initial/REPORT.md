# JVM framework startup from supplied class knowledge

Supplied Groovy/Picocli class knowledge improves ordinary bytecode startup without an application training run or native compilation. A classic static CDS archive is the strongest measured variant here. Manually enabling AOT class linking also works without training, but neither a broad list nor the first declared core list beats classic CDS. All variants still initialize the same Groovy/Picocli classes at runtime.

This is not a 257 ms floor. Separate controls put a small JVM process around 40 ms and a Java-only Picocli command around 151 ms. Merely adding Groovy to the classpath causes Picocli's default factory to initialize Groovy for optional closure support, accounting for much of the gap. The evidence identifies more work to remove; it does not establish that an entire framework heap can be safely restored by a class-name list.

## Matched complete requests

Primary run `20261031T015857.556976Z`: seven randomized paired blocks, fresh Oracle JDK 25.0.5.0.3 processes, Groovy 6.0.0, Picocli 4.7.7, normal JVM shutdown and warm filesystem pages. Every observation validates current request env/token, mode, count, version and result. Preparation/compilation/archive construction are separate.

| Workload | Default CDS | Broad classic CDS | Broad AOT-linked CDS | Declared-core AOT-linked CDS |
| --- | ---: | ---: | ---: | ---: |
| Parser, Groovy present | 341.62 ms | **263.53 ms** | 325.81 ms | 321.21 ms |
| Static Groovy computation | 342.90 ms | **257.60 ms** | 323.07 ms | 320.44 ms |
| Runtime GroovyShell expression | 908.64 ms | **734.52 ms** | 776.94 ms | 893.32 ms |

Classic explicit CDS wins all seven blocks against default in all three cases, reducing medians about 19–25%. The runtime expression constructs a `GroovyShell`, compiles/evaluates a closure/range expression and obtains the result; it includes more than framework initialization. Static Groovy is a separate control, not a substitute for measuring that dynamic runtime.

The original parser fixture has no explicit Groovy operation in its parser branch, but it is deliberately named “Groovy present,” not “Picocli only.” Picocli discovers Groovy on the classpath; the independent controls below establish the distinction.

See [summary](summary.json), [validation](validation.json) and [provenance](provenance.json). A prior seven-block [classic control](classic-control/summary.json) compared CDS off/default/explicit: parser 372/331/257 ms, static Groovy 372/330/257 ms, dynamic 930/861/684 ms. A second [broad-linking control](linking-control/summary.json) compared default/classic/linked. These remain separate runs; do not pool absolute times or compare a new variant against an old control.

## What the preparation knows

The broad archive list contains the JDK's supplied `lib/classlist` plus 5,630 class names enumerated directly from the two pinned JARs. It never runs the application, observes a workload trace, or uses `DumpLoadedClassList`. The application JAR is absent from archive construction and appended to the fixed framework classpath when launching commands.

Classic preparation uses:

```sh
java -Xshare:dump -Xmixed \
  -XX:SharedClassListFile=frameworks.classlist \
  -XX:SharedArchiveFile=frameworks.jsa \
  -cp groovy.jar:picocli.jar
```

Adding `-XX:+AOTClassLinking` creates the broad linked variant with the same provided knowledge. There is no `AOTMode=record`, application training or native executable. The declared-core variant uses all 228 Picocli class names plus 14 explicit public/core Groovy roots: Binding, Closure, GroovyObject, GroovySystem, MetaClass, MetaClassRegistry, GroovyShell, GroovyClassLoader, Script, InvokerHelper, DefaultGroovyMethods, ClassInfo, MetaClassRegistryImpl and VMPluginFactory. The list is declared in source, not selected from measured execution.

| Archive | Nominated framework classes | Archived JAR classes | Size |
| --- | ---: | ---: | ---: |
| Broad classic | 5,630 | 5,613 | 51.5 MiB |
| Broad linked | 5,630 | 4,999 | 47.6 MiB |
| Declared-core linked | 242 | 113 | 16.4 MiB |

The JDK adds its own/transitive classes; [inventory checks](archive-inventory.json) verify that all three archives are valid. Nominated, eligible, archived and actually used class counts are different. Optional absent dependencies and unlinked classes produce explicit skips in the [classic](archive-build.txt), [linked](linked-build.txt) and [core](core-build.txt) construction logs. Skipped types can still load normally when available; an archive is an optimization, not an alternate dependency resolver.

Broad classic archive construction costs about two seconds in these runs; all three measured construction costs and archive hashes are recorded in the summary. This cost and storage must be amortized. The archive binds to the JDK/framework artifacts and classpath contract, not to arbitrary future versions. `-Xshare:on` is used to fail visibly instead of silently falling back during measurement.

The [JDK 25 command documentation](https://docs.oracle.com/en/java/javase/25/docs/specs/man/java.html#application-class-data-sharing) documents supplied class lists and static dumping. Its [AOT cache options](https://docs.oracle.com/en/java/javase/25/docs/specs/man/java.html#ahead-of-time-cache) distinguish the recording workflow from `AOTClassLinking`, which is disabled by default for classic CDS compatibility. This experiment explicitly enables that linking flag with static dumping; it does not fabricate an AOT recording file.

## Linked coverage and eager loading

Class-loading logs are separate intrusive diagnostics, outside latency samples:

| Parser variant | Loaded classes | Framework classes shared | Framework initializers |
| --- | ---: | ---: | ---: |
| Default | 2,110 | 0 | 290 |
| Broad classic | 2,110 | 435 | 290 |
| Broad linked | 7,257 | 4,133 | 290 |
| Declared-core linked | 2,427 | 113 | 290 |

Broad linking eagerly loads much of the nominated universe. The smaller declared set avoids most of that but archives fewer types that the command subsequently needs. Its failure to win is evidence about this first selection policy, not a theorem about AOT linking.

The dynamic case loads 3,736 classes with default/classic versus 7,893 broad-linked and 3,930 core-linked. All four execute **814 framework initializers**; static Groovy executes 292. Classic shares 1,123 of the 1,347 used dynamic-framework classes. More shared-class hits alone do not establish faster complete startup. Classic gains also include transitive JDK metadata; they cannot be attributed solely to vendor JAR bytes.

## Why “Picocli only” was not isolated

The pinned Picocli source has `DefaultFactory.GROOVY_CLOSURE_CLASS = loadClosureClass()`. Unless `picocli.disable.closures` is true, that method calls `Class.forName("groovy.lang.Closure")`, which initializes the class. See the [official pinned source artifact](https://repo.maven.apache.org/maven2/info/picocli/picocli/4.7.7/picocli-4.7.7-sources.jar); its hash is in provenance. This is framework behavior, not an unconditional Groovy operation accidentally inserted in the parser branch.

A separate Java-only parser contains no Groovy references. Seven randomized blocks compare its classpath and feature configuration; [phase controls](phase-controls/summary.json) retain their own clocks and validation.

| Diagnostic command | Complete process | Launch to first main code | Command construction | Execute |
| --- | ---: | ---: | ---: | ---: |
| Empty token/hook control | 39.70 ms | 22.92 ms | — | 7.12 ms |
| Picocli JAR only | 151.04 ms | 28.51 ms | 97.88 ms | 12.65 ms |
| Groovy also present | 326.88 ms | 33.39 ms | 272.31 ms | 10.74 ms |
| Groovy present, closure discovery disabled | 169.34 ms | 33.98 ms | 111.35 ms | 13.97 ms |
| Groovy present, classic CDS | 255.24 ms | 38.33 ms | 197.20 ms | 9.69 ms |
| Groovy present, closure discovery disabled + CDS | 147.88 ms | 38.54 ms | 82.06 ms | 13.18 ms |

The empty control still validates a token, prints a reply and runs the diagnostic shutdown hook. It is not an absolute minimal-JVM floor. Phase medians need not sum to the total median. The remaining execute-to-hook plus hook-to-process-exit tails are recorded; the latter is roughly 5–12 ms. Java/Python monotonic-clock correlation is checked on this Linux JVM for every observation. Another runtime without that relationship is rejected.

With Groovy present, 317 Groovy classes load and 183 initialize in the plain control. Disabling closure discovery reduces both to zero. That configuration removes a capability; it is not a generic way to speed up a command that needs Groovy closures. It exposes where initialization occurs and identifies command-model construction as separate work. Do not subtract these diagnostic timings from the main fixture's medians.

## Prepared metadata versus initialized runtime

A focused [regression test](correctness-tests.txt) archives a selected application class whose initializer reads env state and writes a marker. Archive construction does not run that initializer; two fresh JVM launches execute it with different current tokens. The test also changes an archived JAR and confirms fail-fast rejection. The unchanged Groovy/Picocli initializer counts provide independent evidence that these archives do not freeze those frameworks' initialized static fields.

[JDK 25's initializer implementation](https://raw.githubusercontent.com/openjdk/jdk/jdk-25-ga/src/hotspot/share/cds/aotClassInitializer.cpp) restricts its initialized-field reuse to selected JDK-defined classes. It explains why coupled initializers and shared-object identity need coordinated validation. The stock implementation boundary is stronger than accepting a class-name list, but it does **not** establish that a cooperating framework could never expose a reusable immutable core.

The Groovy team's [separate dynamic-runtime study](https://issues.apache.org/jira/browse/GROOVY-12381) identifies additional limits: its JDK 25/26 caches still relink Groovy dynamic sites, whose mutable targets depend on runtime metaclass guards. That study used a trained application cache on different hardware, so its timings are not our controls. Its architectural observation supports separating immutable lookup data from fresh mutable dispatch state rather than declaring all framework initialization version-only.

A stronger experiment could precompute immutable reflection/DGM/command metadata and rebind small per-process classloader, extension-module, mutable metaclass and resource overlays. A declared framework-only preparation helper would differ from full application training, but still has preparation cost and a state contract. Stock CDS/AOT class lists alone do not provide that arbitrary initialized heap facility. See [research prospects](../../../../../research/java/prospects.md).

## Evidence and limits

Across the initial classic comparison, broad-linking comparison, final declared-core comparison and phase controls, all **252 measured complete processes** pass output/token checks; warmups and class-log/inventory diagnostics are additional and excluded from that count. One focused archive-initialization/identity regression passes. The 63/63/84/42 operations retain separate raw hashes and validation records.

Raw observations are ignored local artifacts: `results.json`, `classic-control/results.json`, `linking-control/results.json`, `phase-controls/results.json`. They are registered in the [evidence manifest](../../../../../research/evidence.json). Frozen measured sources, JDK/JAR identity, generated archives and raw logs remain in ignored local work directories. Compact reports and provenance are versioned; no native images or application-trained caches were built. See [reproduction](../../README.md).
