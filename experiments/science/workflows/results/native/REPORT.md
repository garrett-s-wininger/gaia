# Retain execution at a declared native module boundary

An Odin host owns scalar application state and loads two compatible Odin modules through a fixed C ABI. A forty-eight-request trace changes module version twice. Five blocks compare identical state/results across fresh hosts, an existing batched host and an online retained host.

| Arrangement | Complete 48-request session median |
| --- | ---: |
| Fresh host per request | 72.44 ms |
| Existing host with the trace supplied as a batch | 2.73 ms |
| Retained host with online request/reply | 8.13 ms |

All 720 measured successful request results match the explicit integer oracle. Compatibility checks reject a bad ABI, wrong expected version and missing image; each rejection leaves the prior module/state usable. The independent failure trace validates four successful requests around three rejected replacements.

The result demonstrates removing repeated launch/load work through an existing retained process. Batch execution is the faster competent lower-interaction control; the online path pays request/reply synchronization. This is not evidence that arbitrary applications can live-update. Replacement happens at serial quiescent points. Only the declared integer state survives; there are no outstanding module pointers, callbacks or concurrent calls, and no migration protocol. Trusted pure modules avoid external constructor effects; general dynamic-library initialization cannot be rolled back by this validation.

The [preparation observation](preparation.json) rebuilds the host and three images once into fresh outputs, with warm installed compilers. Host compile/link takes about 4.28 seconds; individual small modules take about 0.30–0.33 seconds. Those preparation costs are outside execution clocks and must be considered when a code edit needs a new module. Toolchain acquisition, arbitrary linker state and LLVM ORC are not measured.

Source and image hashes are checked before/after. [Reproduction](../../README.md), [summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), ignored [observations](results.json).
