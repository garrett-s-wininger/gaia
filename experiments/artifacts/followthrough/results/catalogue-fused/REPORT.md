# A fused Python consumer keeps the representation gain

A second matched catalogue study combines Python's binary validation and queries in one row pass. It preserves the same UTF-8 checks, 64 MiB content bounds, input pin verification and six aggregate outputs. The other controls and the 4,018-file real dependency catalogue are unchanged.

| Consumer | Read, verify, validate and query median |
| --- | ---: |
| Python JSON objects | 4.791 ms |
| Python binary converted to objects | 5.844 ms |
| Python fused direct binary | 2.356 ms |
| Odin direct binary through borrowed Python bytes | 0.396 ms |
| Node JSON objects | 5.734 ms |
| Node direct binary | 2.754 ms |

Five randomized blocks again contain 15 operations per mode; all 450 outputs match. Direct Python and Node beat their matched JSON controls in all five within-block comparisons. The earlier two-pass Python result is in a [separate run](../catalogue/REPORT.md); host/run variation prevents treating the difference between those runs as an isolated fusion effect. This follow-up establishes that the representation gain remains with a fused Python control, while native execution still reduces the per-row interpreter work.

Input buffers are already owned for the separate allocation diagnostic. Traced peaks are 2,426,937 bytes for Python JSON, 1,791,603 for binary-to-objects, 384 for fused Python and 3,859 for the Odin wrapper. This does not count complete process RSS or native allocation. The format sizes remain 422,544 binary and 669,614 JSON bytes, charged in reads/hashes.

The nine correctness tests also pass with the fused Python function substituted, including malformed UTF-8, truncation, invalid name geometry and 64-bit overflow; the same vectors are rejected by Odin and Node. The wrapper records `fused_catalogue.py`/`run_fused.py` source overrides explicitly in ignored raw `results.json`. [Summary](summary.json), [validation](validation.json) and [provenance](provenance.json) retain its identity.

Reproduce the [catalogue command](../../README.md#reproduce-catalogue-sharing) with `run_fused.py` in place of `run_catalogue.py`, using a fresh work/output directory. The same ownership, process-startup and producer-cost limitations apply. This remains a bounded metadata query, not a complete toolchain speedup or a promise that every consumer can use the same schema.
