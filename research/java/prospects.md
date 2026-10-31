# What to test next for JVM framework startup

Supplied class knowledge already supports static CDS and manually enabled AOT linking without a full application training run. Class selection matters because broad linked archives eagerly load thousands of classes. This mechanism does not preserve arbitrary initialized Groovy static fields, registries or dispatch state in the tested stock JVM. That is an implementation boundary, not proof that framework preinitialization is impossible.

## Index runtime-image discovery before repeating filesystem traversal

The [JVMTI profiles](../../experiments/java/startup/results/jvmti/REPORT.md) exposed JDK runtime-image discovery work. The [prepared java.base index](followthrough.md#prepared-discovery-helps-lookup-without-a-complete-command-win) now improves isolated import queries but establishes no complete-command startup gain, despite the helper loading in that command. Require a profile and realistic command with meaningful discovery cost before broadening this representation. Preserve fresh loader/module identities, added extensions and mutable metaclasses; ordinary uninstrumented commands remain the performance control.

## Move beyond the already-prepared DGM decoder

The [DGM experiment](../../experiments/java/startup/results/dgm-binding/REPORT.md) established that dense restore saves about 6 ms in the decoder but does not remove the larger registry or first-script costs. Preserve its rebuilt-source and serial controls. The constructor diagnostic points next to receiver/proxy grouping, plugin-method reflection and Expando lookup construction. Prototype a prepared immutable template for one of those structures, then rebind current classes and fresh mutable overlays. Do not label another denser dictionary a complete runtime snapshot.

## Split reusable framework data from fresh bindings

The next useful experiment is a declared preparation boundary, not another blind whole-JAR archive. Profile constructor/bootstrap work to identify immutable reflection/DGM/method-selection tables and precompute a bounded versioned representation. Restore the immutable core and create fresh classloader, extension-module, mutable metaclass and resource overlays for each runtime. Include table construction, schema validation, restore/rebinding, normal shutdown, identity checks and memory in the complete operation.

JDK and Groovy versions are necessary identities but may not be sufficient. Package classpaths, extension-module inputs, loader topology and framework configuration can change the runtime view. Mutable metaclass registries and Groovy dynamic call-site guards need explicit invalidation semantics. A selected preparation helper may exercise only these declared framework components; that differs from application workload training but still executes preparation and must be charged honestly.

## Distinguish stock-JVM research from VM/framework cooperation

A prototype that archives initialized third-party heap objects needs a declared initialization closure, proof or validation of shared object identity, explicit handling of external resources and fresh runtime state. Stock JDK 25's initialized-mirror facility is restricted to selected JDK-defined classes; a supplied class-name list does not grant Groovy equivalent treatment. Either a framework-side immutable-data interface or VM cooperation would be needed for that stronger experiment.

A small immutable core plus fresh overlays is a plausible research direction. Avoid equating mutable extension points with an impossibility result. Preserve dynamic Groovy behavior and test edits to classpaths/extensions/metaclasses; do not claim that disabling those capabilities is free preinitialization.

## Keep the actual command cheap

The honest controls identify parser model construction and optional Groovy discovery as independent startup work. A reusable declared command schema could move annotation/model derivation into build-time data without freezing arbitrary application state. Picocli's closure-disable toggle is useful only when closures in annotations are not needed; it is a configuration tradeoff, not a generic Groovy runtime speedup.

See the [findings](findings.md) and [complete report](../../experiments/java/startup/results/initial/REPORT.md) before choosing the next implementation.
