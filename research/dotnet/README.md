# .NET startup research

The first experiment compares shipping Roslyn ReadyToRun with an application-only composite image, using the real C# compiler and its normal runtime/JIT defaults.

- [Findings](findings.md): measured benefit and costs.
- [Prospects](prospects.md): next questions without weakening the baseline.
- [Run index](experiments.json): retained evidence locations.
- [Code and reproduction](../../experiments/dotnet_startup/README.md).

This is a bounded runtime/compiler representation experiment, not a new dependency protocol or full NativeAOT conversion.
