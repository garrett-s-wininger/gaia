# Sharing work across consumers

These bounded prototypes broaden the research beyond compiler startup and dependency formats. They test repository queries, schema interpretation, downstream propagation and an initial native persistence boundary. They do not implement the source-control milestone or establish public interfaces.

Read the [report](results/combined-control/REPORT.md), [summary](results/combined-control/summary.json), [validation](results/combined-control/validation.json) and [provenance](results/combined-control/provenance.json).

The [reviewed-source confirmation](results/reviewed/REPORT.md) records the schema/persistence rerun after fixing rejected-name and HEAD-read-error cases. Current sources have 15 passing tests. Original query evidence remains separate and unchanged.

The [production Protobuf control](results/protoc-guarded/REPORT.md) compares existing combined/parallel generators and prepared descriptor handoff. A descriptor case that changes exact outputs is rejected before timing; source-based controls remain measured.

## Reproduce

Requirements: Linux, Odin, a C linker driver, Python 3.10+ with SQLite support, and ripgrep. Choose disposable paths for `WORK` and `OUTPUT`; checkpoint measurements require a fresh store. Choose a real source tree for `CORPUS`. The recorded study used the installed Odin core sources; raw evidence records every selected file's relative path and digest. Another version or corpus is a new measurement, not a recreation of identical inputs.

From the repository root:

```sh
mkdir -p "$WORK"
odin build experiments/workflows/repository_scan.odin -file -o:speed -build-mode:obj -out:"$WORK/repository-scan.o"
cc "$WORK/repository-scan.o" -o "$WORK/repository-scan" -lm -Wl,-z,now -Wl,-z,relro -pie
odin build experiments/workflows/checkpoint.odin -file -o:speed -build-mode:obj -out:"$WORK/checkpoint.o"
cc "$WORK/checkpoint.o" -o "$WORK/checkpoint" -lm -Wl,-z,now -Wl,-z,relro -pie
GAIA_SCAN_HOST="$WORK/repository-scan" GAIA_CHECKPOINT_HOST="$WORK/checkpoint" python3 -B -m unittest discover -s experiments/workflows -p 'test_*.py'
python3 -B experiments/workflows/benchmark.py --work "$WORK/run" --output "$OUTPUT/results.json" --corpus "$CORPUS" --scan-host "$WORK/repository-scan" --checkpoint-host "$WORK/checkpoint" --trials 11 --records 250
```

Use absolute host paths. A shared `flock` around the benchmark can serialize measurements across concurrent research lanes. This does not reserve the host against unrelated processes. Compilation/preparation is outside request clocks. Admission of the repository corpus is timed separately; pages are warmed during correctness checks. This experiment makes no cold-storage claim.

## Repository queries

Six fixed byte strings stand in for independent repository consumers. All modes return identical per-pattern occurrence counts, including binary bytes. Independent Odin processes run sequentially or with six workers. The shared-read mode opens each file once but scans its bytes for each predicate. The fused mode uses an Aho–Corasick transition table. Ripgrep controls run six independent queries sequentially/concurrently, and one combined-pattern query with output aggregation charged.

The corpus is copied into one private immutable generation. Enumerating and importing that generation is separately charged; query clocks include manifest parsing, process startup, file access, matching and captured output. This measures a common namespace, not the costs of independent ignore policies or a filesystem-watching adapter. Fixed strings have no self-overlap; this is not a general regex or license/secret-analysis interface.

## Schema sharing and propagation

`schema_pipeline.py` defines a small experimental schema language with named records, scalar/reference fields and descriptions. It accepts recursive references without recursively expanding them. Frozen Python records feed three emitters: Python declarations, SQLite DDL and Markdown documentation. SQL references use opaque text IDs. The generated fixture contains 250 records with 13 fields each; this is a synthetic experiment, not an OpenAPI implementation or a benchmark against production generators.

Generation compares independent parsing/resolution with one shared model, both sequentially and using three threads. All output bytes must match. Thread results include executor setup and Python runtime constraints; they do not establish native pass-parallelism limits.

Propagation always parses and regenerates current outputs, then hashes them. A conventional control executes every downstream consumer. The cutoff mode may retain prior consumer results only when that output's digest matches within the same fixed implementation/configuration context. Downstream consumers compile Python code, execute SQL into a fresh in-memory database, and count documentation sections. Description, key-order and field-type edits distinguish partial/full invalidation. Consumer/configuration changes would require a different context and are not modeled here.

## Native checkpoint boundary

`checkpoint.odin` accepts an explicitly admitted, sorted bundle of regular-file bytes and executable flags. It writes typed whole-file content objects and a direct snapshot manifest under SHA-256 identities. An exclusive intent file gates the single writer. New objects and their directory are synced before a temporary HEAD is synced, renamed and its directory synced. Existing content is verified before reuse. Historical reads authenticate snapshot/content objects without traversing prior roots or review metadata.

The fixture contains 500 small files and one 4 MiB file. Bundle construction/write is charged alongside the native process, although it is not atomic filesystem discovery. The private repository directory is prepared outside the operation clock. Additional stored bytes include the initial HEAD and new objects; they are not actual device-write accounting. Initial, unchanged, small-edit and large-edit operations are one-shot structural diagnostics; there is no Git speed comparison.

This private-store prototype assumes a trusted directory and one explicit recovery operator. Failpoint exits leave writer intent; tests remove that dead intent only in disposable fixtures. It has no source discovery, ignore syntax, symlink capture, stack/change records, messages, safe restore, concurrent-reader reclamation or automatic recovery. Directory entries and intermediate paths are not hardened against hostile writers. These remain required by the [source-control milestone](../../components/source-control/milestone-1.md). Process-exit probes do not demonstrate power-loss durability.
