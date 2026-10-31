# .NET startup findings

The stock SDK compiler and shared runtime already contain ReadyToRun code. A competent comparison preserves those optimizations. Jointly compiling the three Roslyn application assemblies reduces a complete fresh CLI compilation from 457.65 to 440.27 ms, winning six of seven blocks, with ordinary tiering and JIT fallback unchanged.

The operation reads changing C# source and real framework reference metadata, checks it, writes deterministic PE/PDB/reference assemblies and exits normally. Every output and semantic-error diagnostic agrees; the emitted program runs correctly. A separate probe observes an executable mapping of the composite owner, so the candidate is actually loaded.

The gain is modest: 3.8% on a small controlled compiler workload. Production takes 13.33 s and the selected distribution grows from about 28.37 to 29.60 MB. Producer compilation alone needs roughly 770 such invocations to amortize under the measured median difference. Peak RSS is roughly 111 MiB for both in separate single observations.

See the [report](../../experiments/dotnet_startup/results/initial/REPORT.md) and [validation](../../experiments/dotnet_startup/results/initial/validation.json). This supports further composite-layout tests, not a universal cold-start claim or a reason to disable the shipping runtime's R2R/JIT behavior.
