# Process-visible accelerator APIs

This is an enumeration diagnostic, not a performance comparison. The initial sandbox probe cannot see DXG; an approved host-local probe can. Vulkan instance creation returns `-9` in both views. OpenCL platform enumeration returns `-1001` in both views. ffmpeg's reported interfaces are build capabilities only.

Subsequent explicit DXCore adapter selection and D3D12 execution succeed on an AMD Radeon 860M. The [workflow/device experiment](../../../workflows/README.md) contains the actual dispatch and CPU control. Do not interpret the legacy Vulkan-only boolean as physical device absence.

The raw identities in [raw-identity.json](raw-identity.json) distinguish the sandbox `results.json` from host-local `outside-sandbox.json`. Both remain ignored local evidence. Rerunning enumeration on a different machine or under different isolation creates new observations, rather than a portable statement about hardware availability.

The [probe implementation](../../probe.py) and [reproduction guide](../../README.md) describe the boundary. The auxiliary GLSL shader compiled with glslang and passed `spirv-val`; it did not execute through Vulkan.
