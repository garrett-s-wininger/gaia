# Reviewed schema and checkpoint confirmation

Independent review found two correctness gaps outside the original measured fixture: a HEAD read error other than absence could be treated as an empty store, and accepted schema names could shadow Python's decorator/scalar names or collide under SQLite's case-insensitive identifiers. Current sources reject those cases. Fifteen tests include the regressions, generated Python declaration execution, prior invalidation checks and native persistence/query checks.

This frozen confirmation reruns the affected operations with the corrected sources. The source hashes and native binary identity are recorded in [provenance](provenance.json), with before/after source checks. [Summary](summary.json), [validation](validation.json), [raw identity](raw-identity.json) and ignored [observations](results.json) preserve the result. Repository-query source is unchanged and was not rerun. The [original experiment](../combined-control/REPORT.md) remains a separate historical measurement with its original source identities.

## One interpretation still removes repeated work

Eleven shuffled blocks use the same synthetic 250-record schema and identical output emitters.

| Generation | Median wall time |
| --- | ---: |
| Independent sequential | 23.49 ms |
| Independent threads | 25.56 ms |
| Shared sequential | 8.55 ms |
| Shared threads | 10.68 ms |

All output bytes match. Threads remain slower in these Python implementations. These timings should be compared within this run; changes in host conditions and validation prevent attributing differences from the original run to one cause.

| Edit | Execute all downstream consumers | Stop at unchanged outputs |
| --- | ---: | ---: |
| Key order | 33.51 ms | 10.20 ms |
| Description | 28.52 ms | 10.39 ms |
| Field type | 28.74 ms | 30.84 ms |

The field-type case executes all consumers and saves no work. Output digests and downstream summaries match the full-work control throughout. This remains an experimental schema subset and fixed consumer context, not a production generator comparison.

## Native persistence remains a structural probe

| Operation | Admission + native process | Additional stored bytes |
| --- | ---: | ---: |
| Initial | 1,591.39 ms | 4,832,475 |
| Unchanged | 80.54 ms | 0 |
| Small edit | 60.87 ms | 45,115 |
| One-byte large-file edit | 93.25 ms | 4,239,411 |

These are single observations, not latency rankings or a Git comparison. The private directory is prepared outside operation clocks. Additional stored bytes include the initial 64-byte HEAD; they do not count all rewritten bytes, metadata, temporary files or device writes. Whole-file and flat-manifest amplification remain visible. Source discovery, ignore support, symlinks, stacks, restore and automatic recovery are still absent from this prototype.

Reproduce after building current hosts as described in the [guide](../../README.md):

```sh
python3 -B experiments/workflows/reviewed_checks.py \
  --work "$WORK/reviewed" --output "$OUTPUT/reviewed" \
  --checkpoint-host "$WORK/checkpoint" --lock "$MEASUREMENT_LOCK" \
  --trials 11 --records 250
```
