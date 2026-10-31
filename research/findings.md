# What we have learned

The useful gains came from retaining information that tools would otherwise reconstruct: input identity, observed dependencies, loaded compiler code and verified content locations. A new container or a native implementation helped when it removed that repeated work. Existing caches often removed much of the same work already.

The comparisons below come from separate runs on one Linux developer laptop, mostly with warm filesystem pages. Read each row within its own experiment; the differences cannot be added into a combined speedup.

## Compiler processes and explicit inputs are worth pursuing

The native compiler prototypes now beat the matched Ninja controls on several incremental operations while preserving artifact identity and dependency invalidation. A separate four-target C++ fixture extends the result beyond one C library. Managed Java compilation also benefits substantially from retaining initialized compiler processes.

| Measured operation | Candidate | Control | What the comparison establishes |
| --- | ---: | ---: | --- |
| C source edit, authoritative API inputs | 42.25 ms | 48.78 ms, physical adapter | Supplied edits can avoid repeated physical validation; seven of seven paired wins. |
| C++ source edit, baseline object caches | 293.49 ms | 397.91 ms, Ninja + ccache | Four-target propagation works with one actual compilation and three links; three of three wins. |
| Two complete Java targets | 448 ms, warm two-worker pool | 1,969 ms, parallel cold CLIs | Process lifetime matters; every target still performs joint source compilation. |

The API workspace owns admitted bytes. It does not discover unreported filesystem changes. The C++ graph contains real fmt sources plus a small labelled integration fixture; its repeated-edit history hits are reported separately from object-cache misses. The Java pool retains memory and pays startup on its first request. None of these is a general large-project or service guarantee. See [native compiler findings](compiler/findings.md) and [JVM compiler findings](compiler/jvm/findings.md).

## Artifact delivery benefits from fewer operations and direct access

Sending a known list of missing hashes avoids one request per object. A verified local pack can also reduce publication and open calls for consumers that accept logical byte views. Requiring ordinary files can reverse the gain, so materialization belongs in the complete operation.

A generic binary resolved lock reduces parsing CPU from 9.24 to 2.84 ms and encoded size by 43% against the same JSON data. Once both flat payloads and stored ZIP receive producer-built portable indexes, cold installation is nearly equal at about 45 ms. The flat representation sends 2.7% fewer bytes, but it has no reliable complete-startup lead. The reusable result is the admission/access contract, rather than a selected universal archive. See [artifact findings](artifacts/findings.md).

## Startup depends on what is retained and on the existing baseline

| Ecosystem and workload | Result | Practical limit |
| --- | --- | --- |
| Python dependency loading and resolution | Retained indexes and less resolver bookkeeping help. | Interpreter/framework work and full installer behavior remain separate. |
| Python prepared processes | Complete core/REST requests fall from 251/256 to 105/131 ms. | A live Linux template, explicit framework preparation and repeated requests are required. |
| Node / TypeScript | Library snapshot 117 vs 202 ms for the same bundle. | Full-project snapshot 738 ms loses to the warmed stock CLI at 722 ms. |
| Ruby / RuboCop | Faster full SHA verification saves about 48 ms. | Packed startup remains 438 vs warmed Bootsnap's 428 ms, with higher RSS. |
| JVM / Groovy | Supplied class knowledge reduces dynamic startup from 909 to 735 ms. | Class metadata sharing does not restore arbitrary initialized runtime state; denser DGM data adds no dependable full-command gain. |
| .NET / Roslyn | Composite R2R takes 440 vs the shipping compiler's 458 ms. | The 13.3-second producer cost needs roughly 770 such invocations to amortize. |

These are different preparation and lifetime mechanisms, not interchangeable snapshots. Details and compatibility limits live in the [Python](python/findings.md), [interpreter-state](python/interpreter-state.md), [Ruby](ruby/findings.md), [JVM startup](java/findings.md) and [.NET](dotnet/findings.md) guides.

## What this suggests for Gaia

Explicit named inputs, bounded tool sessions, observed dependencies and independently retrievable metadata are useful boundaries to develop. Compatibility adapters remain part of the cost: filesystem imports, extracted files, target SDKs and language-specific rules still matter. Integrity checks, failures, cancellation, retained memory and preparation must remain visible when comparing complete operations.

The [component designs](../components/README.md) own product decisions. Source control has an agreed MVP design; these experiments do not expand it into a compiler service, CI executor or artifact server. The [next research questions](prospects.md) follow from the remaining uncertainty.
