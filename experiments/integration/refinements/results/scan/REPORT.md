# Retaining immutable identities removes repeated scan work

The original and refined hosts use the same SHA-256 implementation. The refined path retains content IDs and canonical result identities rather than rebuilding them for response assembly.

| Operation | Original | Refined |
| --- | ---: | ---: |
| retained | 5.677 ms | 1.278 ms |
| admit unchanged | 8.351 ms | 1.692 ms |

These are medians of 70 requests per operation/backend in seven shuffled blocks, with retained processes. All 280 responses match the complete 33-target index and generation checks, and later source changes replace identities correctly. Initial syntax/index preparation is charged separately in provenance. This isolates work elimination from CPU-dispatched hashing; it is not a complete build or startup speedup.

The scan workload uses the legacy target-list query interface. The full refined workflow additionally sends exact current command bindings for configuration checks; its complete no-op cost is therefore a different operation.

[Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), [reproduction](../../README.md).
