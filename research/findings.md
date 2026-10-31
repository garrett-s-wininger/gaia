# What we have learned

The useful gains came from retaining information that tools would otherwise reconstruct: input identity, observed dependencies, loaded compiler code and verified content locations. A new container or a native implementation helped when it removed that repeated work. Existing caches often removed much of the same work already.

The comparisons below come from separate runs on one Linux developer laptop, mostly with warm filesystem pages. Read each row within its own experiment; the differences cannot be added into a combined speedup.

## Sharing and transformations have broader applications

The [science round](science/README.md) tests set/patch theory, incremental observations, shared generations, queueing, adaptation, geometry, real consumers and accelerators. Actual Clang observation refresh improves a three-TU trace from 261 to 116 ms with matching objects and depfiles. Shared sealed source mappings reduce four workers' sampled PSS from 94.2 to 59.9 MiB. These are bounded fixtures, not a production compiler service or hard memory quota.

More elaborate policies often lose to conventional controls: static clustering reads less than the tested 3D force layout, fixed delivery batching beats feedback, and speculative backend work generally adds overhead. The [coverage map](science/coverage.md) separates mathematical models from executed workloads and identifies the next integration questions.

## Compiler processes and explicit inputs are worth pursuing

The native compiler prototypes now beat the matched Ninja controls on several incremental operations while preserving artifact identity and dependency invalidation. A separate four-target C++ fixture extends the result beyond one C library. Managed Java compilation also benefits substantially from retaining initialized compiler processes.

| Measured operation | Candidate | Control | What the comparison establishes |
| --- | ---: | ---: | --- |
| C source edit, authoritative API inputs | 42.25 ms | 48.78 ms, physical adapter | Supplied edits can avoid repeated physical validation; seven of seven paired wins. |
| C++ source edit, baseline object caches | 293.49 ms | 397.91 ms, Ninja + ccache | Four-target propagation works with one actual compilation and three links; three of three wins. |
| Heavy C unit, unused typedef added | 74.58 ms, exact IR reuse | 2,265.93 ms, seeded ccache | Compiler-visible changes can preserve object bytes; three of three wins. |
| Eight Java targets, four worker slots | 0.794 s, one JVM | 1.391 s, four JVMs | Shared runtime work helps batch time; memory savings are mixed. |

The API workspace owns admitted bytes. It does not discover unreported filesystem changes. The C++ graph contains real fmt sources plus a small labelled integration fixture; its repeated-edit history hits are reported separately from object-cache misses. IR reuse is a fixed-context proof on whole translation units: the tested AST fingerprints alone produce unsafe matches, and ccache remains faster for comments and unused macros. The Java pool retains private worker state; one JVM does not automatically use less memory. See [native compiler findings](compiler/findings.md) and [JVM compiler findings](compiler/jvm/findings.md).

The [single-frontend follow-up](compiler/followthrough/findings.md) now continues the current IR directly on misses. Its heavy unused-type case takes 75.62 ms versus seeded ccache's 3,710.98 ms, while exact-input ccache remains faster. A 33-TU production Ninja graph also improves source/generated-input edits under matched single-worker controls. That runner uses fixed baseline dependencies; it does not yet integrate the stronger dynamic/negative-condition checker.

Sharing parsing mainly saves CPU in the small parallel-analysis control: about 100 to 50 ms of sampled worker CPU, while wall time is nearly unchanged against two independent parallel workers. The analysis operates on detached declaration names, not a production linter or concurrently mutable compiler AST.

## First compilation and sustained execution need different controls

Native Image reduces the first actual Java compilation to 307 ms versus cached Leyden's 737 ms; fresh complete processes take 346 and 873 ms. The advantage extends beyond launch. In a separate 32-request trace, later compiler-body medians are 281 ms native, 255 ms cached Leyden and 206 ms for the Parallel-GC JVM control. Background JIT work continues, so these are bounded observations rather than peak-throughput claims.

Collector and tiering choices also trade first use against later work. C1-only cuts the fresh command from 1.64 to 1.24 seconds but slows later compilation. Native Epsilon is slower than native Serial in the matched short test and exhausts the same 768 MiB heap on attempt five. Image/cache construction, SDK preparation, compiler versions and module compatibility remain explicit in the [JVM execution study](../experiments/java/compiler/results/variants/REPORT.md).

The [longer-session study](java/followthrough.md) exercises sampled resident-memory admission and native optimization controls. Shared JVMs complete 192 real compilations in their bounded traces; four JVMs stop at 168 after exceeding the soft gate. This is overshoot detection, not a hard memory quota. Supplied-profile O3 improves first compilation and executable size against O3 with inferred profiles, but their sustained session medians differ by less than one percent with overlapping ranges. Effective flags and substantial preparation costs matter to attribution.

## Artifact delivery benefits from fewer operations and direct access

Sending a known list of missing hashes avoids one request per object. A verified local pack can also reduce publication and open calls for consumers that accept logical byte views. Requiring ordinary files can reverse the gain, so materialization belongs in the complete operation.

A generic binary resolved lock reduces parsing CPU from 9.24 to 2.84 ms and encoded size by 43% against the same JSON data. Once both flat payloads and stored ZIP receive producer-built portable indexes, cold installation is nearly equal at about 45 ms. The flat representation sends 2.7% fewer bytes, but it has no reliable complete-startup lead. The reusable result is the admission/access contract, rather than a selected universal archive. See [artifact findings](artifacts/findings.md).

The [storage-service sensitivity study](storage/findings.md) changes a different boundary. Including installation and full sealed-memory admission, three Django starts improve from 2.72 to 0.99 seconds at 1 ms per logical request. At 16 MiB/s read/write bandwidth, eager full admission loses: 6.00 versus 6.27 seconds. Reading all 29 MB can overfetch when each process needs about 6.7 MB. This is an application I/O model with warm host pages, not a measured degraded physical disk or native compiler result.

The [demand/cache follow-up](artifacts/followthrough.md) confirms the byte/request tradeoff with verified chunks and real consumers. It also separates cheap lookup through an open packed store from expensive index reconstruction on reopening. A bounded catalogue query avoids equivalent object graphs across Python, Odin and Node: fused Python takes 2.356 ms versus JSON's 4.791 ms, and borrowed Odin takes 0.396 ms. These are read/verify/query clocks, not complete starts or physical page sharing.

## Startup depends on what is retained and on the existing baseline

| Ecosystem and workload | Result | Practical limit |
| --- | --- | --- |
| Python dependency loading and resolution | Retained indexes and less resolver bookkeeping help. | Interpreter/framework work and full installer behavior remain separate. |
| Python prepared processes | Complete core/REST requests fall from 251/256 to 105/131 ms. | A live Linux template, explicit framework preparation and repeated requests are required. |
| Node / TypeScript | Library snapshot 117 vs 202 ms for the same bundle. | Full-project snapshot 738 ms loses to the warmed stock CLI at 722 ms. |
| Ruby / RuboCop | Faster full SHA verification saves about 48 ms. | Packed startup remains 438 vs warmed Bootsnap's 428 ms, with higher RSS. |
| JVM / Groovy | Supplied class knowledge reduces dynamic startup from 909 to 735 ms; JVMTI identifies a further module-lookup improvement. | The module index saves about 9 ms in a tighter registry comparison; broader command timings are unstable. Class sharing does not restore arbitrary initialized state. |
| .NET / Roslyn | Composite R2R takes 440 vs the shipping compiler's 458 ms. | The 13.3-second producer cost needs roughly 770 such invocations to amortize. |

These are different preparation and lifetime mechanisms, not interchangeable snapshots. Details and compatibility limits live in the [Python](python/findings.md), [interpreter-state](python/interpreter-state.md), [Ruby](ruby/findings.md), [JVM startup](java/findings.md) and [.NET](dotnet/findings.md) guides.

The new Groovy runtime-image index improves isolated import-map queries from 625 to 481 ms but does not improve the complete basic command. This remains a useful negative result in the [framework follow-up](java/followthrough.md#prepared-discovery-helps-lookup-without-a-complete-command-win).

## Sharing also helps outside compiler execution

The [broader experiment overview](workflows/coverage.md) records the bounded results and gaps across the new tracks.

| Operation | Observation | Boundary |
| --- | --- | --- |
| Six repository predicates | Combined ripgrep 17.06 ms versus parallel independent ripgrep 43.87 ms | Real source corpus; existing tool wins over our first fused Odin matcher. |
| Schema interpretation | Shared 8.55 ms versus independent 23.49 ms | Synthetic 250-record model with identical emitters; production generators remain separate controls. |
| Prepared database fixtures | 24.5–27.4 ms versus 355.5 ms replay | Sixteen generated SQLite test operations with preparation/teardown charged. |
| Shared test discovery | 1,505 ms versus 1,564 ms parallel discovery | Generated JUnit suite; existing direct API does less consumer work and remains faster at 1,443 ms. |

Unchanged intermediate outputs can also suppress downstream work; field-type edits that change all outputs save nothing. An unmodified Protobuf comparison shows why parallel controls matter: combined generation loses to three parallel invocations in both workloads. Passing prepared descriptors changes exact generated bytes for one fixture, exposing explicit/implicit metadata that a shared representation must preserve. [Schema and propagation](../experiments/workflows/results/reviewed/REPORT.md), [Protobuf controls](../experiments/workflows/results/protoc-guarded/REPORT.md), [testing](testing/findings.md).

An Odin checkpoint probe establishes typed immutable content/snapshots and publication checks while exposing whole-file/flat-manifest amplification. It does not implement source discovery, ignores, symlinks, stacks, restore or automatic recovery, so the accepted source-control milestone remains incomplete.

## What this suggests for Gaia

Explicit named inputs, bounded tool sessions, observed dependencies and independently retrievable metadata are useful boundaries to develop. Compatibility adapters remain part of the cost: filesystem imports, extracted files, target SDKs and language-specific rules still matter. Integrity checks, failures, cancellation, retained memory and preparation must remain visible when comparing complete operations.

The [component designs](../components/README.md) own product decisions. Source control has an agreed MVP design; these experiments do not expand it into a compiler service, CI executor or artifact server. The [next research questions](prospects.md) follow from the remaining uncertainty.
