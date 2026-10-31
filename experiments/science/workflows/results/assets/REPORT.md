# Sharing image preparation does not automatically beat an existing pipeline

Three actual QEMU/GnuTLS/Ogg PNG icons and diagrams each produce three square bilinear/RGBA/PNG outputs. Five blocks contain sixty complete operations. Every output is independently decoded and its RGBA hash compared; all sixty operations match. Source/tool/input pins remain unchanged.

| Arrangement | Median complete operation, pooled across the three assets |
| --- | ---: |
| Three independent processes, sequential | 270.45 ms |
| Three independent processes, parallel | 94.82 ms |
| Existing combined ffmpeg graph | 93.19 ms |
| Decode RGBA once, copy to three parallel encoder processes | 197.12 ms |

Combined ffmpeg and independent parallel execution are close; the combined path wins eight of fifteen matched input/block pairs. Three small icon/diagram assets do not establish a general image/video winner. Existing ffmpeg already shares an input through its graph. The Python raw-buffer bridge pays a separate decoder process plus three encoder processes and pipe copies, so avoiding repeated decode does not compensate for its boundary cost here.

Clocks include startup, input access, transformations, encoding and output files. Output directory creation is included. Independent oracle decoding is outside the clock. PNG metadata need not be byte-identical; decoded pixel identity is the declared contract. Raw payload counts are not process or peak memory claims.

The [capability record](../capabilities.json) retains actual CUDA/Vulkan failures inside the sandbox and successful D3D12 device creation through an explicitly selected hardware adapter outside it. Device creation alone supplies no GPU throughput result. No driver or device configuration is changed.

This supports using existing programmatic/multi-output pipelines as controls before introducing a new shared representation. [Reproduction](../../README.md), [summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), ignored [observations](results.json).
