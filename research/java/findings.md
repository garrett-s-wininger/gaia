# What JVM framework preparation buys us

Supplied framework class knowledge reduces startup on the tested Groovy/Picocli workload without native compilation or an application training run. It shares class metadata; initializing mutable runtime structures remains substantial work.

## Class sharing improves fresh commands

Enumerating class names from pinned JARs and producing static CDS archives reduces parser startup from 342 to 264 ms, static Groovy from 343 to 258 ms and a GroovyShell expression from 909 to 735 ms. All seven paired blocks improve. Archive construction, skipped classes and complete process shutdown remain recorded separately. [Class-sharing report](../../experiments/java/startup/results/initial/REPORT.md).

Manually enabling AOT class linking with the supplied classlist also works, but neither the broad nor the declared core list beats classic CDS. A broad list loads thousands of unused classes; a smaller list loses sharing coverage. The runtime still executes 290/292/814 framework initializers for parser/static/dynamic operations. A class-name list does not restore an arbitrary initialized Groovy heap.

## Runtime setup remains a distinct cost

Picocli's optional Groovy closure discovery is visible in Java-only controls: adding Groovy makes the default factory initialize `groovy.lang.Closure`. Disabling that discovery reduces the CDS case from about 255 to 148 ms, but removes a capability. It is useful only for applications that do not need closures in annotations.

The phase fixture attributes roughly 148 ms to a fresh registry, 10 ms to shell construction, 400 ms to first parsing/compilation/script creation and 87 ms to first execution. Those observations identify work to investigate; they are not a universal startup floor or additive savings.

## Denser prepared tables alone have limited payoff

Groovy already packages an immutable table of default methods. A dense class-ID binding experiment preserves all 2,007 descriptors and reduces decoding from about 24 to 19 ms. Parser medians move from 267 to 259 ms with five of seven wins; full dynamic execution stays around 709–711 ms without a dependable gain. A rebuilt-source control separates the algorithm change from recompilation effects. [DGM binding report](../../experiments/java/startup/results/dgm-binding/REPORT.md).

An intrusive constructor profile points to proxy/receiver grouping, plugin reflection and ExpandoMetaClass setup as larger candidates. Mutable metaclass replacement, fresh classloaders and added extension modules still work in the tested variants. Preparation must preserve those bindings rather than freeze arbitrary live state.

## Scope and follow-up

The first study validates 252 measured processes and an initializer/changed-JAR regression; the DGM study validates 196 processes and three semantic regressions. These are one pinned JDK/framework configuration and declared workloads. JDK/Groovy versions alone may not identify classloader, extension, configuration or resource state.

The next useful direction is immutable framework data with fresh bindings. Stock JVM support and framework-side preparation are separate possibilities. See [prospects](prospects.md), [reproduction](../../experiments/java/startup/README.md) and the [run index](experiments.json). [Managed Java compilation](../compiler/jvm/findings.md) has a separate training and worker-lifetime contract.
