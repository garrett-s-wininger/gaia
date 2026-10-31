# Restore supplied Groovy method data with fresh runtime bindings

Groovy already ships a precomputed binary default-method table. Replacing its map-based restore with dense class-ID binding cuts the measured decoder from about 24 to 19 ms, but does not remove the much larger fresh registry and first-script costs. The complete parser shows a small, noisy improvement; the dynamic workload has no dependable win. This is useful representation evidence, not an initialized-heap snapshot or a startup floor.

## What is actually reused

The pinned Groovy 6.0.0 JAR contains `META-INF/dgminfo`: method names, generated adapter names, return/parameter class IDs and a class-name dictionary. The stock loader reconstructs maps, resolves class names through a parallel stream, creates 2,007 method records, and then the registry builds fresh proxies and receiver metadata.

This experiment leaves that immutable table byte-for-byte unchanged. It compares four runtime artifacts:

- Published stock Groovy.
- The unmodified source rebuilt with the same compiler/flags as the patches.
- A serial-binding control, changing only `parallelStream()` to `stream()`.
- A dense-binding prototype, replacing boxed integer maps with a `Class[]` indexed by the table's IDs and resolving current classes serially.

The producer is [dgm_prepare.py](../../dgm_prepare.py). It verifies the pinned source/JAR identities, compiles only `GeneratedMetaMethod` and its nested classes, and checks that unrelated JAR entries and the DGM table are unchanged. The prototype adds bounds to the trusted package-table decoder. It preserves unavailable-class skipping and the record order/signatures. No application training, native compilation, arbitrary object serialization or restored mutable metaclass registry is involved.

Every consumer gets fresh loader-resolved `Class` bindings, records, registry, extension scan and mutable dispatch state. The identity is the package bytes and modified-runtime/source build, not just a loose version label. The [provenance](provenance.json) records those identities under the research schema `GAIA-DGM-BIND-1`; this is not a proposed public Groovy format.

## Complete-process comparison

Primary run `20261031T030839.766073Z`: seven randomized paired blocks per case, warm pages, normal fresh JVM startup/shutdown. All four variants receive separately generated matching classic static CDS archives from the same supplied class-name policy. Producer patch compilation and archive creation remain separate setup costs.

| Operation | Published stock | Rebuilt control | Serial bindings | Dense bindings |
| --- | ---: | ---: | ---: | ---: |
| Read/describe DGM records | 105.31 ms | 107.47 ms | 105.26 ms | **99.42 ms** |
| Initialize Groovy registry | 207.21 ms | 209.54 ms | **199.90 ms** | 201.75 ms |
| Picocli parser, Groovy present | 267.21 ms | 268.82 ms | 268.05 ms | **258.67 ms** |
| First dynamic script | 710.96 ms | 714.87 ms | **706.64 ms** | 708.90 ms |

Dense binding wins six of seven raw-record blocks against both stock and the rebuilt control. It wins five parser blocks against either, and only four dynamic-script blocks. The parser median moves about 3%, but these observations do not establish a dependable full-runtime improvement. Serial binding also does not establish an overall advantage. See [summary](summary.json) and [validation](validation.json) for paired differences and ranges.

The record operation includes a canonical descriptor hash inside the process, so its complete time is not the isolated decoder cost. Every variant returns exactly 2,007 records with canonical SHA-256 `bd1ce6165f692ce8bf4a8b56e8eb386d16b526247533b176103932ab99c5b4a3`.

A separate initial seven-block [control](initial-control/summary.json) lacked the rebuilt-source control. It is retained rather than silently replaced. The primary comparison adds that control because changing a library method also requires rebuilding its class files; raw gains should not be attributed solely to representation without that check. Do not pool the two runs' absolute times.

## Where the rest goes

The [phase harness](../../FrameworkPhases.java) records real registry initialization, new-shell construction, first parsing/compilation/script creation and first execution. For the stock dynamic case, median phases are approximately:

| Phase | Time |
| --- | ---: |
| Registry initialization | 148 ms |
| New GroovyShell | 10 ms |
| First parse/compile/script creation | 400 ms |
| First run and dynamic dispatch | 87 ms |

The remaining complete-process time includes launch, output and normal shutdown. The decoder is only about 24 ms within a larger initialization process; dense restore reaches about 19 ms. These medians are not a decomposition of the older 257 ms command: the dynamic phase fixture has different work and does not construct Picocli first.

An additional [intrusive constructor diagnostic](registry-profile.json), implemented by [registry_profile.py](../../registry_profile.py), instruments a separately rebuilt registry class with matching CDS. Its three observations put DGM record/proxy/receiver grouping around 65 ms, VM plugin-method reflection around 25 ms and ExpandoMetaClass setup around 35 ms. Additional methods, extension scanning, MOP refresh, creation-handle setup and listener installation are smaller in that diagnostic. Source timers and altered class files make this a prioritization aid, not an uninstrumented latency comparison.

The remaining reusable-data question is therefore more concrete: can immutable receiver/proxy templates, plugin reflection selection and Expando lookup derivation be prepared while mutable registries and loader/extension bindings stay fresh? The dense dictionary alone does not perform that transformation. It would be incorrect to describe these results as restoring the whole initialized Groovy core.

## Dynamic behavior and validity

All [three focused semantic tests](correctness-tests.txt) pass across all four artifacts. They verify identical method descriptors and current registry bindings; replace a metaclass method after its first invocation; compile through a fresh child GroovyClassLoader; and discover a newly appended extension-module JAR. Removing that extension produces the expected missing-method failure. These test actual mutable and classpath-sensitive behavior rather than silently disabling it.

The existing package metadata format and runtime model are retained. This does not establish every Groovy extension, restricted loader, Java release or concurrent metaclass scenario. It also does not provide a stock-JVM facility for arbitrary third-party initialized static fields; that distinction is explained in the [earlier report](../initial/REPORT.md). The framework-side experiment is valuable precisely because immutable data can be reused without freezing arbitrary live objects.

## Cost, reproduction and evidence

The primary run spends about 5.7 seconds building three research runtime variants, then about 1.8 seconds per matching CDS archive. Archives remain around 51.5 MiB. These are separately recorded preparation observations, not free consumer work. Generated artifacts and original sources remain ignored local data.

Reproduce using the pinned JDK/JAR acquisition in the [startup README](../../README.md), then:

```sh
python3 -B experiments/java/startup/dgm_benchmark.py \
  --jdk /path/to/jdk --downloads /path/to/pinned-jars \
  --trials 7 --output experiments/java/startup/_work/runs/dgm-binding
GAIA_DGM_RUN=/path/to/results.json GAIA_JDK=/path/to/jdk \
  python3 -B -m unittest discover -s experiments/java/startup -p test_dgm.py -v
```

Include the pinned Groovy source JAR alongside the binary JARs. The optional source-timer diagnostic takes `--run`, `--jdk` and a fresh `--output` directory. It must be run separately from performance measurements.

All 112 primary and 84 initial timed processes validate; warmups, semantic tests and three intrusive diagnostics are additional. Full raw observations are ignored local artifacts `results.json` and `initial-control/results.json`, registered by size/hash in the [evidence manifest](../../../../../research/evidence.json). Frozen source identities, producer/runtime hashes and validation summaries accompany the reports. No production Groovy runtime replacement or general snapshot format is selected.
