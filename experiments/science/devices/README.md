# Device capability boundary

The initial probe examines only APIs visible to its process. Inside the managed sandbox, `/dev/dxg` is hidden. Outside it, DXG is present, but Vulkan instance creation still returns `-9` and OpenCL platform enumeration returns `-1001`. Those API failures do not establish that the laptop lacks an accelerator.

The [actual device experiment](../workflows/README.md) subsequently selects the AMD Radeon 860M explicitly through DXCore and executes a D3D12 compute shader with a native CPU oracle. Default-adapter creation initially failed too; explicit selection was necessary. Read that experiment for actual hardware timing, transfer costs and scaling.

`probe.py` records Vulkan/OpenCL status, process-visible device paths and compiled ffmpeg interfaces. Its historical `hardware_gpu_exposed` field means a hardware candidate enumerated **through Vulkan**, not through every API. The ffmpeg list reports compiled support, not working hardware. NPUs, hardware codecs, storage and network offload require their own successful capability and execution checks.

```sh
python3 -B experiments/science/devices/probe.py --output "$OUTPUT/capabilities.json"
glslangValidator -V experiments/science/devices/frontier.comp -o "$WORK/frontier.spv"
spirv-val "$WORK/frontier.spv"
```

The GLSL reverse-frontier shader compiled and passed SPIR-V validation. It was not dispatched through Vulkan here. The later D3D12 implementation uses its own HLSL source. No CPU fallback is presented as GPU execution.

The [capability record](results/capability/REPORT.md) retains both process views. No drivers, system configuration or default adapters were changed, and no toolchain binaries belong in version control.
