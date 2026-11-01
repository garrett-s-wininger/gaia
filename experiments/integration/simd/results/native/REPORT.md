# Vector unions versus optimized loops and sparse lists

The operation unions masks of changed observations. Values are nanoseconds per warm native operation, median of seven shuffled blocks; the portable loop may already auto-vectorize. Generated cases are labelled. Every mode produces the same complete output for all prepared queries.

| Fixture | Optimized loop | Word tiled | SIMD 4 lanes | SIMD 8 lanes | CSR lists |
| --- | ---: | ---: | ---: | ---: | ---: |
| captured-1 | 9.9 | 9.9 | 13.3 | 13.4 | 16.9 |
| captured-8 | 27.0 | 9.8 | 10.4 | 10.3 | 80.7 |
| sparse-4096-1 | 16.1 | 79.7 | 33.0 | 22.1 | 9.2 |
| sparse-4096-8 | 104.9 | 248.8 | 44.5 | 46.4 | 25.7 |
| sparse-4096-64 | 1018.1 | 2313.9 | 643.5 | 579.9 | 283.9 |
| dense-8192-1 | 42.5 | 171.4 | 61.3 | 52.0 | 2580.8 |
| dense-8192-8 | 187.6 | 817.9 | 111.0 | 194.2 | 22859.8 |
| dense-8192-64 | 1473.1 | 4991.4 | 1647.8 | 1278.9 | 181655.5 |
| sparse-16384-1 | 47.9 | 199.4 | 56.3 | 46.1 | 19.1 |
| sparse-16384-8 | 401.7 | 1349.3 | 262.3 | 243.6 | 143.9 |
| sparse-16384-64 | 7976.8 | 21224.1 | 8791.3 | 6947.2 | 1651.0 |

The captured graph contains only 33 targets, so each row fits one 64-bit word and explicit wider kernels use their scalar tails. Dense generated relations test contiguous mask work; sparse CSR is a separate, strong algorithm/representation control. A vector improvement on wide masks does not establish a complete compiler speedup.

Fixture construction and CSR conversion are separately charged in metadata. Timed native batches cycle prepared queries and consume output values, amortizing Python ABI crossings. Validation, output clear and a small checksum remain inside those clocks. Payload sizes are not process-memory limits. Read the native-target matrix alongside the generic build before attributing a win to hand-written SIMD. The generic eight-lane source lowers into narrower instructions; native code generation includes actual ZMM instructions (see the build evidence in the reproduction guide).

[Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), [reproduction](../../README.md).
