# .NET Roslyn startup and composite ReadyToRun

The stock SDK already supplies ReadyToRun compiler and runtime assemblies. This experiment keeps those competent defaults, including tiered compilation/JIT fallback, and compares the real `csc` CLI with an application-only composite image of its three Roslyn assemblies.

The workload compiles changing multi-file C# using real .NET reference assemblies, checks semantic-error behavior and validates deterministic PE/PDB/reference-assembly output plus independent execution of the emitted program. It is a small compiler workload, not a full application build or an empty startup/version command. Reflection-metadata generation is not added: this CLI offers no justified reflection-discovery bottleneck in the first experiment.

Generated SDKs, Crossgen2, compiler copies and all outputs stay in ignored `_work`; an SSD-backed symlink is supported. No machine-global SDK installation or NativeAOT application conversion is required.

## Reproduce

Acquire the pinned .NET 10.0.403 SDK/runtime 10.0.14 and Crossgen2 10.0.14, then build and measure:

```sh
python3 -B experiments/dotnet_startup/fetch_tools.py --destination /path/to/tools
python3 -B experiments/dotnet_startup/prepare.py \
  --tools /path/to/tools --output /path/to/prepared
python3 -B experiments/dotnet_startup/benchmark.py \
  --tools /path/to/tools --prepared /path/to/prepared \
  --trials 7 --output /path/to/new/dotnet-run
```

Crossgen2 receives only the three compiler application assemblies as inputs; the unmodified stock runtime assemblies are references. Compilation uses bounded parallelism and is separately charged. The framework/runtime R2R is never disabled, no tiered/JIT settings are weakened, and no training profile is created from the measured requests. The stock and composite inputs have the same IL and assembly identities.

Timed observations include fresh runtime startup, compiler source/reference loading, full checking, deterministic output writing and normal process exit. Input changes, output removal and parent checks occur outside the clock. An untimed mapping probe proves that the composite native owner actually receives an executable mapping; separate `wait4` diagnostics observe per-child peak RSS. SDK/producer cost and distribution sizes are recorded separately. Warm filesystem pages do not establish storage-cold latency.

To run the header checks against custom local outputs:

```sh
GAIA_DOTNET_TEST_RUN=/path/to/new/dotnet-run GAIA_DOTNET_TEST_PREPARED=/path/to/prepared \
  python3 -B -m unittest discover -s experiments/dotnet_startup -p 'test_*.py' -v
```

Pure malformed-header tests work without toolchain downloads; actual-image checks skip until local outputs exist. The [report](results/initial/REPORT.md) includes producer/storage costs and the already-R2R baseline.

[Experiment notes](FINDINGS.md) retain the detailed comparisons behind the linked research review and reports.
