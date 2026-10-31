# Allocation diagnostics are separate from request timing

A tracemalloc pass uses the same 3,931-ID corpus with 39 removed/39 added IDs. Input sets are already owned. The diagnostic includes the algorithm, cryptographic reconstruction and independent correctness/update-rebuild assertions; it is intentionally outside the primary timing comparison.

| Algorithm | Python traced allocation peak |
| --- | ---: |
| Full inventories | 865,181 B |
| Prefix hierarchy | 1,260,061 B |
| IBLT-style summary | 1,057,857 B |

These are Python-traced temporary allocations, not total process RSS, input residency or native allocator use. Instrumented CPU observations must not replace uninstrumented request times. The table does not establish that a maintained native summary would require the same memory.

All three diagnostic results match exact difference/update oracles. [Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), [reproduce](../../README.md).
