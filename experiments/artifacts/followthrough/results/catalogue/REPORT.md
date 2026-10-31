# Keep catalogue rows native across runtime boundaries

A 4,018-file catalogue derived from the real Django dependency bundle can be consumed by Python, Odin and Node without reconstructing an equivalent object graph. This is a bounded metadata-query experiment, not an AST-sharing result or complete dependency-installation speedup.

## What was measured

Every operation reads its representation, verifies the producer pin, validates the schema/name bounds and computes the same six aggregates: file count/bytes, `.pyc` count/bytes and `django/` count/bytes. The binary layout contains little-endian fixed-width rows and a UTF-8 string pool. Native and Node binary paths validate UTF-8 as well as geometry; all readers limit each content range to 64 MiB and the table to 100,000 rows. The resulting sums are exactly representable in the tested runtimes.

Five randomized blocks contain 15 operations per mode. Node starts fresh for each block/mode, but the table reports its operation medians across those repeated requests; process startup is separate in the raw data. Python modes run in the harness process. These clocks must not be added to our earlier startup measurements.

| Consumer | Read, verify, validate and query median |
| --- | ---: |
| Python JSON objects | 5.039 ms |
| Python binary converted to objects | 6.247 ms |
| Python direct binary queries | 3.600 ms |
| Odin direct binary query through Python C ABI | 0.420 ms |
| Node JSON objects | 5.455 ms |
| Node direct binary queries | 3.099 ms |

Within-block direct medians beat JSON in all five blocks for both Python and Node. These are prototype algorithms, not interpreter floors: Python's binary validator and query make separate passes, while native/Node validation is fused with the query. The native path also removes Python iteration and row-object construction. It is not a measurement isolating format, loop implementation and fusion into separate effects.

The binary representation is 422,544 bytes versus JSON's 669,614 bytes. This size difference is charged in reading/hashing. A separate `tracemalloc` diagnostic, with input buffers already owned, records peaks of 2,426,937 bytes for Python JSON, 1,791,603 for binary-to-objects, 336 for direct Python and 3,859 for the Odin wrapper. It does not count native allocator or process RSS. The exported Odin loop allocates no per-row objects and retains no input pointers.

## Ownership and correctness

Python owns immutable bytes for the entire native call; Odin borrows their address and returns six scalar values. Node independently opens the same representation. This does not demonstrate physical page sharing across separate processes or remove file reads. The interface makes ownership explicit without choosing a universal data model.

All 450 operations produce identical aggregates. Nine unit tests cover chunk admission and catalogue behavior; catalogue malformed vectors include truncated headers/tables, invalid bounds, invalid UTF-8 and a 64-bit size overflow. Python, Odin and Node reject those malformed binary inputs. A lifetime test verifies scalar results survive release of the source buffer.

Producer binary encoding time, library identity, source hashes, input pin, process times and per-operation observations are in ignored `results.json`; [summary](summary.json) records its hash and length. JSON producer encoding is not separately timed, so no complete preparation-amortization claim follows. The measured tools are Python 3.14.8, Node 26.12.0 and Odin dev-2026-10-nightly:84bc3fc; the Odin object is linked with GCC 16.2.1. The host is the existing 16-logical-CPU AMD Ryzen AI 7 PRO 450 Linux laptop. An advisory lock separates research timing windows; ordinary host load remains a source of variation.

## What this supports

A bounded immutable view plus small borrowed-buffer ABI is worth testing for actual diagnostics/dependency/test-result consumers. Reconstructing objects can erase the representation benefit: the binary-to-object Python control is slower than JSON here. Next isolate a fused Python pass, retained-buffer queries and a real multi-consumer operation before selecting an interface or claiming that shared buffers improve arbitrary workloads.
