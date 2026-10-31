# .NET startup findings

For current conclusions and practical limits, start with the [research review](../../research/dotnet/findings.md). These notes retain the detailed experiment comparisons; measured reports remain under `results/`.

A Roslyn application-only composite image improves complete compiler latency about 3.8% against the already-R2R stock SDK, with six of seven paired wins and separate producer/update costs. Read the [human findings](../../research/dotnet/findings.md), [report](results/initial/REPORT.md) and [reproduction](README.md).
