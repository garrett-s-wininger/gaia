# Interpreter state reuse findings

For current conclusions and practical limits, start with the [research review](../../../research/python/interpreter-state.md). These notes retain the detailed experiment comparisons; measured reports remain under `results/`.

Resident CPython templates substantially reduce repeated Django requests. The first synthetic Node graph loses under disk restoration, but a real TypeScript dependency changes that conclusion: default snapshot restoration reduces a complete compiler-library operation from 201.57 to 117.28 ms versus identical ordinary bundle execution, with seven paired wins. A smaller no-code-cache blob still wins at 132.41 ms. Read the [TypeScript report](results/typescript/REPORT.md), [initial controls](results/initial/REPORT.md), [human review](../../../research/python/interpreter-state.md) and [reproduction](README.md).

The latest comparison validates 28 fresh TypeScript processes, four warmups and two source-absent restoration audits. Seven regression tests pass. Producer cost, memory accounting, runtime-version compatibility and native resource/performance hooks are explicit; no portable format or general application snapshot promise is selected.

The [full project CLI](results/typescript-project/REPORT.md) preserves a 7.7% snapshot gain against the identical API bundle, but loses to TypeScript's normal warmed Node compile cache: 737.54 versus 722.45 ms. All 35 timed builds and 29 correctness boundaries pass, including full standard-library/project checking,44 filesystem outputs, actual runtime behavior and warning-free live performance rebinding. Initialization reuse remains useful in context; beating an ordinary uncached loader is a weaker claim than beating a competent existing CLI.
