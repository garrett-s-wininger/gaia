# Selected-framework bytecode startup

For current conclusions and practical limits, start with the [research review](../../../research/java/findings.md). These notes retain the detailed experiment comparisons; measured reports remain under `results/`.

The [initial report](results/initial/REPORT.md) retains four matched studies: classic supplied classlists, broad AOT class linking, honest empty/parser phase controls and a declared-core linking comparison. All 252 measured processes validate.

Classic CDS is the strongest tested preparation, but framework initializers still run. Broad linking pays eager-load costs; the first smaller declared set loses metadata coverage. Picocli optionally discovers and initializes Groovy even for a Java-only command when the JAR is present. None of these results is a startup floor.

Read the [human findings](../../../research/java/findings.md), [prospects](../../../research/java/prospects.md) and [reproduction](README.md).

The [prepared DGM follow-up](results/dgm-binding/REPORT.md) makes the existing package table cheaper to restore, but shows no dependable full dynamic-startup win. All 2,007 method descriptors and dynamic extension/metaclass/loader checks remain valid. The next representation candidates are larger immutable bootstrap structures, not another claim that metadata is an initialized runtime.
