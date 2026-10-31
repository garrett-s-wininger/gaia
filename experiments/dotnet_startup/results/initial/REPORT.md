# Roslyn cold-process startup: composite R2R modestly improves an optimized baseline

Application-only composite ReadyToRun reduces a complete real Roslyn CLI compilation from **457.65 to 440.27 ms**, winning **six of seven paired blocks**. This is a modest **3.8%** reduction against the shipping compiler, which already uses ReadyToRun. The shared runtime and ordinary tiered/JIT behavior remain enabled and unchanged.

## Work and controls

Run `2026-10-31T03:12:45.871623+00:00`; observations are in the [summary](summary.json). The pinned .NET SDK is **10.0.403**, runtime and Crossgen2 **10.0.14**, Linux x64. The actual SDK `csc.dll` compiles changing C# source with records, generics, immutable collections, LINQ, spans and JSON use. It emits deterministic implementation PE, portable PDB and reference assembly files. The emitted program is independently executed and its changing request value, ordered names and sum are checked.

This is a small controlled three-file compiler workload, not a large published C# application or an MSBuild/server benchmark. It performs actual source/reference loading, full semantic compilation and filesystem output, rather than a version or empty startup command. Reference assemblies come from the pinned SDK.

The stock `csc.dll`, `Microsoft.CodeAnalysis.dll`, `Microsoft.CodeAnalysis.CSharp.dll` and runtime `System.Private.CoreLib.dll` already contain ReadyToRun headers. [The PE inspector](../../pe_info.py) verifies their actual `RTR` signatures; the experiment never manufactures an unoptimized IL-only baseline by disabling shipping R2R. Stock assembly bytes are copied unchanged.

The candidate jointly recompiles only the three Roslyn application assemblies into one composite owner plus component images, using the matching official Crossgen2. Existing runtime assemblies are references, not recompilation inputs. Runtime R2R, server-GC configuration, tiered compilation and JIT fallback remain at stock settings; no measured-request training profile or NativeAOT conversion is used.

## Whole-operation result

Seven randomized paired blocks; **14 fresh compiler processes**, warm filesystem pages:

| Compiler representation | Median ms | Range ms | Candidate wins |
| --- | ---: | ---: | ---: |
| Shipping individual R2R | 457.65 | 439.75–498.66 | — |
| Application composite R2R | **440.27** | 434.69–460.37 | **6/7** |

The clock includes fresh runtime startup, command/response-file reading, source/reference access, checking, deterministic writes, normal exit and parent wait. Input changes, removal of old outputs, hashes and independent emitted-program execution are outside it. No persistent compiler server or result cache supplies the win. Mapping and memory probes are separate observations and are not pooled into this table.

The candidate receives an **executable mapping** of its composite owner during an independently monitored real compilation. This confirms the runtime actually loads the new native image. All PE/PDB/reference bytes, diagnostics, exit statuses and program behavior match the stock control. A type-error case emits no compiler artifacts and produces the same `CS0029` diagnostic.

This is promising, not a universal startup improvement or a final floor. Six paired wins on one small workload do not establish arbitrary project, architecture or runtime-version performance.

## Producer, storage and memory costs

Joint compilation takes **13.33 s** at producer parallelism two. The selected stock assembly closure totals **28.37 MB**; the candidate distribution, including components, composite owner and small runtime/dependency descriptors, totals **29.60 MB**. The native owner is about 19 MB. These figures compare an already-R2R baseline; they are not the much larger IL-to-R2R size multiplier sometimes quoted for other applications.

At the measured 17.39 ms difference of medians, producer compilation alone amortizes over approximately **770 invocations**. This is a model, not a measured long-lived deployment distribution. SDK/tool acquisition and storage remain additional producer costs. The SDK download is 240 MB and is a build prerequisite, not a per-consumer transfer requirement. [Official pins](toolchain-provenance.json) record artifact versions, SHA-512 identities and sources.

Separate `wait4` diagnostics observe roughly **111 MiB peak RSS** for each compiler, with about 0.1 MiB difference. Those are single observations, not a memory improvement or strict bound. The diagnostic launcher measures the real exec'd child and is excluded from latency observations; no fast-exit path is introduced.

Composite components must be distributed together. Compiler/runtime/target identities govern rebuild and compatibility. Ordinary source input changes do not rebuild the compiler image. [Microsoft's documentation](https://learn.microsoft.com/en-us/dotnet/core/deploying/ready-to-run) explains the optimization/distribution tradeoff and continued JIT behavior; this prototype selects no cross-version servicing protocol.

## Evidence and reproduction

All **14 timed compilations**, two mapping warmups, two semantic-error checks and two separate memory probes validate. Both [PE/header regression tests](correctness-tests.txt) pass, including actual R2R images and an emitted IL-only counterexample. The main observations compare **42 generated artifact hashes**, plus actual emitted-program behavior. Runtime and compiler input hashes, reference-assembly pins, producer commands and frozen experiment sources are retained in the ignored raw run.

Use [tool acquisition](../../fetch_tools.py), [preparation](../../prepare.py), [benchmark](../../benchmark.py) and [reproduction](../../README.md). Reflection-metadata precomputation is intentionally not added: this first CLI experiment has no established reflection-discovery bottleneck, so adding one would misrepresent the tool.

The raw `results.json` is an ignored local artifact registered in the [evidence manifest](../../../../research/evidence.json). Reports and compact evidence are versioned; SDK archives, binaries, references, compiler copies and `_work` remain ignored.
