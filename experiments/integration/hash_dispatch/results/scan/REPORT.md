# CPU-dispatched SHA-256 improves the actual retained scan

The generated host changes only the SHA-256 helper. All cache/index digest bytes, returned declaration records and invalidation results match the original implementation. This is a real 33-TU observation/index scan, rather than a standalone hash-throughput benchmark.

| Operation | LLVM portable | OpenSSL dispatched | OpenSSL capability-masked |
| --- | ---: | ---: | ---: |
| retained | 10.35 ms | 6.06 ms | 10.56 ms |
| admit unchanged | 14.97 ms | 8.43 ms | 14.67 ms |

Each value is the median of 70 requests across seven shuffled blocks, ten requests per case. Those requests share processes and state. Paired block medians favor dispatch in 7/7 retained blocks and 7/7 unchanged-admission blocks. All 420 responses match, and three subsequent source changes replace the affected identity correctly. Warmup syntax/index work takes about 13.6–13.8 seconds per backend and is outside request clocks.

The capability mask is supplied only to the controlled child process at startup, following [OpenSSL documentation](https://docs.openssl.org/3.6/man3/OPENSSL_ia32cap/). Masking produces timings near the portable implementation. This supports a CPU-dispatch benefit; it is not a dynamic instruction trace or proof that the masked process executes only scalar instructions. Crypto ISA dispatch differs from the explicit integer-vector union experiment.

The substitution preserves SHA-256 rather than selecting another content identity format. It still rebuilds canonical identities for immutable retained facts and revalidates observations; removing unnecessary work remains a separate follow-up. No full-build or startup speedup is extrapolated. Four workspace regressions, including stock-object equality, pass with this variant, but the complete 108-operation build matrix uses the original host.

[Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), [implementation/reproduction](../../README.md).
