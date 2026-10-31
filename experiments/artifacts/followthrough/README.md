# Sharing admitted data beyond one tool invocation

These prototypes follow the [artifact-access](../../../research/artifacts/prospects.md) and [storage-service](../../../research/storage/prospects.md) studies. They ask four separate questions:

| Question | Prototype | Evidence |
| --- | --- | --- |
| Can a real consumer work before all dependency bytes are admitted? | Fresh Django processes over a shared verified range/chunk service. | [Admission report](results/admission-frozen/REPORT.md) |
| What happens after the artifact cache grows and publication fails? | Existing file/packed stores, real package objects, explicit eviction wrapper and failure injection. | [Lifecycle report](results/lifecycle/REPORT.md) |
| Can several runtimes consume the same structured representation without reconstructing object graphs? | Portable catalogue consumed by Python, Odin and Node, with owned-object controls. | [Catalogue report](results/catalogue/REPORT.md), [fused Python control](results/catalogue-fused/REPORT.md) |
| What happens when retained tools and admitted data share a machine budget? | Actual source generations and verified chunks held beside a resident JVM compiler. | [Companion interface](#mixed-memory-companion) |

The formats, service and eviction wrapper are experimental. They do not select a Gaia public protocol. The service model changes application read/write cost; it does not throttle a physical disk or emulate a network connection.

## Reproduce admission

Start from the pinned producer payload/index in the [preindexed bundle study](../README.md), whose acquisition manifest and summary identify the dependency versions. The payload and index are disposable generated artifacts, not versioned inputs. Supply their paths explicitly. Linux, Python 3.14 matching the supplied `.pyc` corpus, local Unix sockets and memfd seals are needed for the measured path.

Run commands from the repository root. Choose a fresh writable `$WORK` directory with adequate space; all caches, compiled libraries and source snapshots belong outside source history.

```sh
python3 -B experiments/artifacts/followthrough/run_admission.py \
  --payload "$PAYLOAD" --index "$INDEX" \
  --work "$WORK/admission" \
  --output experiments/artifacts/followthrough/results/admission-new \
  --trials 3 --consumers 3
```

Optional `--lock "$MEASUREMENT_LOCK"` acquires an advisory lock for each complete session, releasing it between sessions. The lock coordinates these experiments; it does not establish that the entire host is idle. Use the same external conditions for every control.

Installation is identical and charged for each policy. A producer computes version-pinned SHA-256 chunk descriptors once; its construction time and metadata bytes are separate. Demand chunks are verified before cache visibility. The consumer retains the preceding compact-index loader and per-file SHA-256/CRC32 checks. Every policy uses the same socket copying/dispatch path. No whole-payload transfer is required before demand consumers start, but index loading is still eager and charged.

## Reproduce catalogue sharing

Build the bounded native query as an Odin object and link with the host C compiler. This avoids assuming a system Clang executable is installed.

```sh
odin build experiments/artifacts/followthrough/catalogue.odin -file \
  -build-mode:obj -o:speed -out:"$WORK/catalogue.o"
cc -shared -o "$WORK/catalogue.so" "$WORK/catalogue.o"
GAIA_CATALOGUE_LIBRARY="$WORK/catalogue.so" \
  python3 -B -m unittest discover -s experiments/artifacts/followthrough -p 'test_*.py'
python3 -B experiments/artifacts/followthrough/run_catalogue.py \
  --index "$INDEX" --library "$WORK/catalogue.so" \
  --work "$WORK/catalogue" \
  --output experiments/artifacts/followthrough/results/catalogue-new
```

The catalogue has fixed-width little-endian rows and a UTF-8 name pool. Every timed operation reads and verifies its pinned representation, validates row/name bounds and computes the same aggregates. Odin borrows a Python-owned immutable bytes buffer for a bounded call; it returns six scalars and retains no pointers. Node consumes the same representation independently. This is a shared representation, not a claim that separate runtime heaps share physical pages or that filesystem reads disappear. Binary and JSON differ in size; the measured operation includes that difference.

## Reproduce cache lifecycle

```sh
python3 -B experiments/artifacts/followthrough/lifecycle.py \
  --index "$INDEX" --payload "$PAYLOAD" \
  --work "$WORK/lifecycle" \
  --output experiments/artifacts/followthrough/results/lifecycle-new
```

The probe verifies the actual package-file hashes before inserting them. File and packed stores share the same logical requests. Report open-store lookup separately from reopening/index loading. Eviction is a prototype wrapper over `Packed`, rather than a preexisting production policy. Faults test process-level atomic visibility; no new fsync/power-loss guarantee follows.

## Mixed memory companion

`hold_cache.py` retains actual repository Python source bodies, four edited source generations and a bounded LRU of verified payload chunks. Its access sequence comes from a recorded real Django consumer. Readiness includes workspace admission, producer chunk-hash preparation and the first access pass.

```sh
python3 -B experiments/artifacts/followthrough/hold_cache.py \
  --workspace experiments/compiler --payload "$PAYLOAD" \
  --trace "$ADMISSION_RESULTS" --budget 16777216 \
  --generations 4 --hold-seconds 600 --replay \
  --output "$WORK/companion.json"
```

The process prints a `READY` JSON record. Sending `STOP` on stdin or SIGTERM ends it cooperatively and writes final counters. `--replay` adds real cache reads and hash verification while the compiler runs; omit it to measure retained bytes alone. The logical budget covers unique source-body bytes and chunk bytes, not Python metadata, source-map overhead, transient buffers or compiler memory. The JVM harness samples aggregate PSS and applies its separately documented soft stop policy. That is not a strict operating-system memory quota.
