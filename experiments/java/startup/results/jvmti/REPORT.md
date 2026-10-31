# JVMTI makes Groovy startup work visible

The diagnostic agent identifies work beyond the already prepared default-method table. In particular, Groovy reconstructs Java module/package metadata during registry initialization and traverses the JDK runtime image during first-script compilation. A source-level membership index preserves behavior and improves the isolated initialization closure in all seven subsequent pairs; complete registry startup improves modestly in five of seven pairs. The initial broader command matrix is too unstable to establish a general CLI gain.

These are fresh ordinary-bytecode JVMs, with matching static CDS archives, warm filesystem pages, current environment/request inputs and normal shutdown. No application training pass, restored live heap, MethodEntry stream, code transformation or disabled Groovy functionality is involved. [Reproduction and implementation](../../jvmti/README.md).

## What the agent costs

Five randomized blocks measure complete registry initialization and the existing dynamic sum-script operation. Loading, capability setup, diagnostic work, normal process exit and JSON writing are included. Logging runs are separate.

| Mode | Registry median | Change | Dynamic script median | Change |
|---|---:|---:|---:|---:|
| No agent | 195.2 ms | — | 722.0 ms | — |
| Idle agent | 198.9 ms | +1.9% | 728.8 ms | +0.9% |
| Class load/prepare | 200.3 ms | +2.6% | 725.0 ms | +0.4% |
| CPU-weighted stacks | 220.1 ms | +12.8% | 740.9 ms | +2.6% |
| Sampled allocation | 207.1 ms | +6.1% | 751.5 ms | +4.1% |

CPU attribution uses actual platform-thread CPU deltas and stack snapshots at a 4 ms target interval. It attributes an interval's CPU to the endpoint stack, misses activity before the first sample and does not cover virtual threads. It is an approximate hotspot finder. Sampling itself adds safepoints, stack collection and symbol lookup. Native callback timers omit some of those effects; the matched complete-process table captures the observable cost. The dynamic class-events case also contains a 1007 ms outlier; five blocks are insufficient to interpret sub-percent differences.

Unified logs show exactly **259 of 295 framework class loads shared from the archive in every mode**. The agent therefore did not silently discard framework CDS sharing in this configuration. Actual initialization-log entries are 1273 for the controls and 1274 with CPU sampling; the CPU agent creates an extra Java thread. The raw count parser was corrected to exclude verification messages also logged under `class+init`; the original capture and correction provenance remain preserved.

The granted CPU capability reports a total-CPU timer. Allocation mode grants only sampled-allocation support. No mode grants MethodEntry, ClassFileLoadHook or retransformation. All final profiles report no JVMTI errors or dropped stack entries; three pre-live allocation events are explicitly skipped across the measured profiles. The exploratory first profiles contained WRONG_PHASE errors; moving the timer query to VMInit and guarding pre-live allocation stack collection resolves them. Those initial observations remain in the raw capture bundle.

## What becomes actionable

Mean closest-framework-frame CPU weights across five registry profiles include roughly 14 ms for `DgmMethodRecord.loadDgmInfo`, 12 ms for `MetaClassImpl.addProperties`, 7 ms each for SAM-method discovery and annotation lookup, and 5–6 ms each for `Java9` initialization and its export predicate. These are sampled interval weights, not exact function durations or additive savings. Allocation samples independently implicate `Java9` initialization and module predicates, alongside method/receiver setup.

Inspection finds a concrete repeated join: for every legacy Java package, upstream walks the descriptor's export/open entries using a fresh stream and linear `anyMatch`. The candidate discovers the same current system descriptors but builds unqualified export/open package sets once per module, then uses membership queries. Descriptor ownership, qualified-entry exclusion, absent-package behavior and final legacy tables remain the same. It binds to the current runtime; it does not preinitialize classes or cache live module identities across JVMs.

The larger first-script lead is **JDK runtime-image discovery**. `ClassFinder.find` receives about 45 ms of mean closest-frame CPU weight, `maybeNewFileSystem` about 19 ms and its visitor about 12 ms. The allocation sampler also finds repeated runtime-image filesystem construction. These separate endpoint categories should not be read as exact recoverable savings. They justify investigating a versioned immutable package/class-name index keyed by the actual runtime image, with fresh loader/module/extension overlays.

## Initial candidate result and its uncertainty

Each of stock, source-rebuilt control and indexed Groovy has its own matching classic CDS archive. Unchanged jar entries, including packaged DGM data, remain byte-identical. The same JDK compiler and flags rebuild the control and candidate. Seven randomized blocks include changing runtime tokens and seeds.

| Operation | Stock | Rebuilt source | Membership index |
|---|---:|---:|---:|
| DGM records | 114.9 ms | 113.9 ms | 113.7 ms |
| Registry | 245.8 ms | 242.5 ms | 239.9 ms |
| Picocli parser | 318.4 ms | 305.8 ms | 277.2 ms |
| Dynamic script | 786.7 ms | 816.5 ms | 880.9 ms |

This run has strong between-block drift and extreme outliers: the indexed dynamic case ranges from 576 to 1995 ms; stock registry ranges from 183 to 434 ms and rebuilt registry from 174 to 666 ms. Every block is retained. The parser median is not sufficient evidence of a win, nor does the dynamic median establish a stable regression. Use this table as an explicitly unstable first attempt.

Rebuilding the two source variants takes 5.55 s total. Archive creation takes 2.93/2.42/2.34 s for stock/rebuilt/indexed, each about 54 MB. These are producer costs outside fresh-request timings. The initial broad matrix cannot support a break-even claim. A deployment amortization model must include the selected variant compilation, archive rebuilds and validation; the short registry confirmation does not establish savings for arbitrary command mixes.

## Tighter uninstrumented confirmation

A subsequent seven-block run reuses the exact same rebuilt/indexed jars and archives, places each pair adjacent, and runs without the agent. It records complete-process wall time, waited child user/system CPU and system-wide CPU pressure before/after each process. No Groovy algorithm or JVM flag changes between the two runs.

| Operation | Rebuilt source | Index | Paired wall wins |
|---|---:|---:|---:|
| Complete fresh registry | 219.49 ms | 210.87 ms | 5/7 |
| Complete isolated Java9 initializer probe | 82.35 ms | 78.34 ms | 7/7 |
| Java9 initialization closure inside that probe | 28.37 ms | 20.76 ms | — |

The median paired wall saving is 7.16 ms for registry and 6.77 ms for the isolated probe; differences between independent medians need not equal median paired differences. Registry wall ranges are 209–252 ms for rebuilt and 199–222 ms for indexed, so this is a modest, still noisy result. The isolated closure includes superclass/dependency initialization as well as the classification block; it does not time only the membership loop.

Median total child CPU decreases from 531.6 to 498.3 ms for registry and 185.8 to 157.4 ms for the initializer probe. CPU is summed across JVM threads, including compilation threads, and can exceed wall time. The pressure observations are machine-wide context, not an attribution of a particular stall to this process. These controls support removal of some repeated metadata work without claiming that the unstable full dynamic operation improved.

The confirmation adds an isolated probe compilation outside request timings. It exercises a declared initialization boundary, not application-result precomputation. All normal-process semantics and dynamic behavior checks still refer to the same source variants.

## Behavior and limits

The variants retain all **2,007 DGM descriptors** and their canonical identity. For each variant, the module probe checks **1,990 predicate cases**, including actual system descriptors plus synthetic named, open and automatic modules, unqualified/qualified exports and opens, and absent packages. All produce identical complete **534-entry** legacy classification tables. Runtime named/unnamed access checks pass. These cases establish parity with the upstream policy, not a new claim that descriptor entries alone implement every Java access rule.

Separate ordinary-JVM tests preserve fresh child classloaders, metaclass replacement, and discovery/removal of an added extension module. The table algorithm does not change runtime access-check code or freeze the mutable Groovy registry. This remains one pinned JDK/Groovy/classpath configuration; it is not a proof for every loader, resource, module layer or framework plugin.

The profiler bounds its maps and strings, retains native per-thread counters rather than Java object graphs, and merges class events by binary name. Its timeline therefore does not distinguish two loaders defining the same name. Profiles are diagnostic evidence; finalists must be measured without the agent.

See [review summary](summary.json), [behavior validation](validation.json), [provenance](provenance.json), and the ignored [raw observations](results.json) and [full profiles/logs](profiles.json). The raw files are available locally and recorded in the evidence manifest; no public download is published.
