# Real D3D12 frontier propagation

An actual compute shader executes through the WSL D3D12 runtime on the explicitly selected **AMD Radeon(TM) 860M Graphics** adapter. DXCore reports hardware=true. The host has no CPU fallback path: device creation, shader compilation, fence timeout and unequal readback all fail the operation. Automatic D3D12 adapter selection fails with `DXGI_ERROR_UNSUPPORTED`; explicit DXCore selection succeeds. Sandbox device masking also prevents this host-only experiment from running inside the restricted sandbox.

This is a bounded device API experiment, not a proposed service or graphics dependency. The narrow C++ shim uses Microsoft's native API headers; all computation is native. SDK extraction stays in ignored storage. No drivers or host settings change.

## Reproduce

From the repository root, provide an absolute ignored working directory, the captured Django coaccess JSON, and the shared timing lock:

```sh
python3 experiments/science/workflows/devices/prepare.py --work "$WORK"
python3 experiments/science/workflows/devices/run.py --work "$WORK" --graph "$CAPTURED_COACCESS_JSON" \
  --lock "$MEASUREMENT_LOCK" --output "$OUTPUT"
```

Run the second command in a host context with access to `/dev/dxg`. It requires the existing WSL `libdxcore.so` and `libd3d12.so` under `/usr/lib/wsl/lib`; it does not create a portable device backend. The preparation script pins official DXC and DirectX-Headers archives and supplies two missing SAL annotation macros for the released headers' Linux stubs. The native host is GCC `-O3 -DNDEBUG`, HLSL is DXC `cs_6_0`. [Results](results/REPORT.md) explain the boundary and controls.

The captured graph has 437 chunks and 1,629 directed training coaccess pairs. Integer weights are intentionally unused: the operation propagates a Boolean frontier one step, not a weighted graph model. Generated fixtures have 1,048,576/8,388,608 edges and 131,072/1,048,576 nodes; their mixed-high/low LCG endpoints are labelled synthetic. Sparse activates node IDs divisible by eight; dense activates every node. Five fresh native sessions per condition each run twelve repetitions; the first is reported separately, leaving 55 retained samples per condition. Workloads and all measured source/binary files are hashed before/after.

Edges/frontier remain in upload heaps visible to the GPU. This removes a separate explicit upload-to-default copy; it does not prove absence of driver paging/copies. Output uses a default UAV, is cleared each repetition, copied to a readback buffer, synchronized through a fence, mapped and compared byte-for-byte. Root descriptors avoid descriptor-heap setup. Native controls include both an edge sweep and a prebuilt CSR sparse traversal. CSR construction is reported separately. GPU comparisons use retained **full operations**, including recording, clear, dispatch, sync, readback and validation. There are no isolated GPU timestamp claims.

Approximate simultaneously retained application buffer payload at largest scale is 200 MiB: CPU edges64, CSR32, offset/cursor8, frontier/expected/observed/zero16; GPU edge/frontier/zero upload72, output/readback8; allocator overhead and shader/tool/runtime allocations are **not** included. CPU RSS and device-driver committed memory are not measured; this is a payload budget, not a total-memory bound. Preparation Python additionally holds about192 MiB while writing the largest generated fixture, before native execution; that array is released before the timing loop. The `process_ms` column is a twelve-request benchmark process including CPU controls; it is not a single-request service latency.
