# Vector unions versus optimized loops and sparse lists

The operation unions masks of changed observations. Values are nanoseconds per warm native operation, median of seven shuffled blocks; the portable loop may already auto-vectorize. Generated cases are labelled. Every mode produces the same complete output for all prepared queries.

| Fixture | Optimized loop | Word tiled | SIMD 4 lanes | SIMD 8 lanes | CSR lists |
| --- | ---: | ---: | ---: | ---: | ---: |
| captured-1 | 8.0 | 9.7 | 6.6 | 8.3 | 15.1 |
| captured-8 | 22.8 | 13.0 | 16.5 | 14.1 | 95.9 |
| sparse-4096-1 | 24.9 | 110.9 | 40.4 | 30.6 | 9.6 |
| sparse-4096-8 | 118.0 | 204.4 | 78.7 | 71.8 | 43.8 |
| sparse-4096-64 | 1033.0 | 1924.4 | 602.1 | 561.4 | 317.2 |
| dense-8192-1 | 35.3 | 187.2 | 57.2 | 46.2 | 2592.1 |
| dense-8192-8 | 227.6 | 347.9 | 172.1 | 156.3 | 19235.2 |
| dense-8192-64 | 2014.1 | 6431.8 | 2141.3 | 1624.7 | 172271.9 |
| sparse-16384-1 | 52.6 | 302.0 | 103.5 | 74.7 | 28.1 |
| sparse-16384-8 | 544.4 | 1083.3 | 393.0 | 339.7 | 144.4 |
| sparse-16384-64 | 12889.7 | 18619.4 | 7418.5 | 5649.8 | 1486.3 |

The captured graph contains only 33 targets, so each row fits one 64-bit word and explicit wider kernels use their scalar tails. Dense generated relations test contiguous mask work; sparse CSR is a separate, strong algorithm/representation control. A vector improvement on wide masks does not establish a complete compiler speedup.

Fixture construction and CSR conversion are separately charged in metadata. Timed native batches cycle prepared queries and consume output values, amortizing Python ABI crossings. Validation, output clear and a small checksum remain inside those clocks. Payload sizes are not process-memory limits. Read the native-target matrix alongside the generic build before attributing a win to hand-written SIMD. The generic eight-lane source lowers into narrower instructions; native code generation includes actual ZMM instructions (see the build evidence in the reproduction guide).

[Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), [reproduction](../../README.md).
