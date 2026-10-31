# GPU execution works; this graph kernel stays on the CPU

Real D3D12 dispatch and exact readback succeeded on an explicitly selected AMD Radeon 860M. All 360 dispatched repetitions across 30 fresh sessions matched the native oracle. An invalid DXIL negative control failed pipeline creation with HRESULT `0x80004005` and exit 1, before any result publication.

Retained medians in milliseconds (55 samples per row, first dispatch excluded):

| Graph / frontier | Edge sweep CPU | CSR CPU | GPU full operation |
|---|---:|---:|---:|
|Captured: 437 nodes / 1,629 edges, sparse|0.000972|0.000481|0.197143|
|Captured, dense|0.000732|0.000942|0.202043|
|Generated: 1.05M edges, sparse|2.214010|0.454511|1.695750|
|Generated: 1.05M edges, dense|2.086180|1.250890|3.977980|
|Generated: 8.39M edges, sparse|19.443300|6.840570|25.550900|
|Generated: 8.39M edges, dense|26.727800|18.109500|50.611200|

The GPU beats the edge sweep on one generated case, but loses to CSR everywhere. There is no measured crossover against the stronger CPU control. This is a memory/atomic-heavy one-step frontier operation, with driver submission and synchronization costs; it does not rule out compute-heavy graph geometry, device-resident multi-step algorithms, or other hardware backends.

For the real sparse graph, median initialization 165.3 ms includes file loading, reference/CSR setup, device/queue creation, pipeline and buffers. Pipeline creation 0.529 ms and buffer allocation/upload filling 6.39 ms are components, not additional costs. Retained recording/submission 0.020 ms, sync 0.168 ms, readback-map/validation 0.0006 ms. First dispatch 2.19 ms versus retained 0.197 ms. Generated 8.39M sparse initialization 420.5 ms includes CSR 114.6 ms, pipeline 0.458 ms, buffer/upload 29.1 ms. Its retained submit 0.364 ms, sync 24.82 ms and readback/validation 0.253 ms explain most of the full operation. Component medians need not sum to the median total.

Driver caches are already warm from the capability/smoke attempts; these are fresh processes, not a machine-cold driver-cache experiment. The exploratory first successful smoke took 1.19 s initialization and 56 ms pipeline creation. DXC frontend compilation is separately preserved in [shader-compile.json](shader-compile.json), outside runtime measurements. No GUI, compiler or complete developer workflow acceleration is established.

See [summary.json](summary.json), [raw-identity.json](raw-identity.json), [validation.json](validation.json), [provenance.json](provenance.json) and [implementation/reproduction](../README.md). The ignored raw stores all per-session phases and stderr, including the driver's `Dropped Escape` diagnostic. Phases use CPU wall time; no GPU timestamp is available in this prototype.

Generic-ML capability filtering exposes the same GPU. NPU/compute-accelerator filters expose no additional adapters through this WSL runtime; physical host accelerators remain untested. [Capability evidence](capabilities.json). A bounded capability enumeration overlapped the final matrix; five-block medians are not a controlled idle-host latency guarantee.
