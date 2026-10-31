# Shared work helps when the underlying operation is already efficient

The repository query result supports combining compatible queries, but does not establish an advantage for a new Gaia scanner. Ripgrep's existing combined-pattern operation beats our first fused Odin implementation. The schema fixture shows useful savings from one immutable interpretation and from stopping propagation at unchanged outputs. The checkpoint probe exposes basic storage costs before a product engine exists.

These are separate workloads on one Linux developer machine. Query/schema measurements use 11 shuffled paired blocks with warm pages; preparation may overlap other research and unrelated activity. Checkpoints are four one-shot diagnostics. The [summary](summary.json), [validation](validation.json), [provenance](provenance.json) and [raw identity](raw-identity.json) describe the evidence. Full [observations](results.json) remain ignored local data.

## Repository queries need a strong combined control

The immutable corpus contains 1,299 actual Odin core source/documentation files totaling 27,802,679 bytes. Six fixed-string predicates return identical occurrence counts in every mode.

| Complete query operation | Median wall time |
| --- | ---: |
| Six independent Odin scans, sequential | 419.87 ms |
| Six independent Odin scans, parallel | 92.68 ms |
| Odin opens once, six per-file scans | 275.23 ms |
| Odin fused automaton | 104.84 ms |
| Six independent ripgrep scans, sequential | 106.39 ms |
| Six independent ripgrep scans, parallel | 43.87 ms |
| One combined ripgrep scan, including aggregation | 17.06 ms |

Sharing a pass is valuable here, but the best implementation is an existing tool. Combined ripgrep wins against parallel ripgrep in all 11 paired blocks; our fused Odin implementation wins none. The Odin automaton has dependent table lookups and a different matching implementation; this experiment does not isolate its exact bottleneck. Replacing ripgrep with our scanner would regress this workload. A repository service must preserve selective queries and differing policies instead of forcing every query through a complete shared scan.

The next useful question is whether consumers with different predicates and lifetimes can share discovery/access while retaining these competent matching algorithms. This fixed-string test does not implement full search, licensing or secret analysis.

## One schema interpretation avoids repeated reconstruction

Three emitters consume a generated 250-record schema with scalar and named-reference fields. Output bytes are identical across controls.

| Generation operation | Median wall time |
| --- | ---: |
| Independent parse/resolve, sequential | 16.14 ms |
| Independent parse/resolve, three threads | 20.46 ms |
| Shared immutable model, sequential | 6.22 ms |
| Shared immutable model, three threads | 8.21 ms |

Threads do not improve these Python implementations. Shared sequential generation beats independent sequential generation in all 11 paired blocks. This is a declared experimental schema subset; no production generator has been modified or beaten.

## Unchanged intermediate outputs can stop downstream work

Both controls regenerate current outputs and hash them. Only cutoff may skip a downstream consumer for an identical output. SQL execution and Python compilation are included.

| Input edit | Rebuild all consumers | Stop at unchanged output | Consumers executed with cutoff |
| --- | ---: | ---: | --- |
| JSON key order only | 23.08 ms | 7.47 ms | None |
| Record description | 21.85 ms | 7.00 ms | Documentation |
| Field type | 21.75 ms | 22.10 ms | All three |

The field-type case shows the expected limit: when every output changes, equality checks save no downstream work. This prototype retains results only within a fixed tool/configuration context. Production reuse would also need environment, side-product, diagnostics and observation identities.

## Checkpoint structure exposes write amplification immediately

The Odin store captures 501 admitted files, verifies retained objects, and publishes a synced root. The current implementation uses one file per object and a complete flat snapshot manifest.

| Operation | Admission + native process | Additional stored bytes |
| --- | ---: | ---: |
| Initial checkpoint | 1,698.98 ms | 4,832,475 |
| Unchanged checkpoint | 76.52 ms | 0 |
| Small-file edit | 59.21 ms | 45,115 |
| One-byte edit in 4 MiB file | 119.89 ms | 4,239,411 |

These single observations identify structural costs, not stable latency differences. The initial byte count includes the 64-byte HEAD; later counts describe additional objects, not device writes or all rewritten bytes. Creating the private repository directory is outside operation clocks. The initial checkpoint individually syncs new objects; a small edit rewrites the flat manifest, and a large-file edit stores a complete new content object. There is no historical delta replay. The prototype supplies concrete evidence for future packing and namespace experiments, without selecting either now.

Twelve tests accompanied the recorded run. Later independent review found that non-not-found HEAD read errors could be mistaken for absence and that some accepted schema names produced invalid runtime outputs. Current sources fail closed on those reads and reject Python/SQLite name conflicts; 15 tests include the regressions and execution of generated Python declarations. The measured fixtures did not contain these cases. Original source identities remain in provenance; a separate reviewed-source confirmation records the affected operations. Before/after-root failpoints preserve readable prior states and expose an interrupted writer intent. Safe restore, source discovery/ignores/symlinks, stacks, automatic recovery and broader durability validation remain unimplemented. This is a research start toward the local engine, not completion of its accepted milestone.
