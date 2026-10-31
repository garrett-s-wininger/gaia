# Sets, delivery, locality and environment composition

These bounded science experiments use the existing real Django dependency corpus: 4,018 logical files, 3,931 distinct content hashes and a 28,590,237-byte flat payload. The work connects set reconciliation, networking/control, local reinforcement, geometry-assisted placement, bounded policy search and representation laws to actual data. Native geometry is supplied by the parallel graph study; this lane's algorithms are Python prototypes, not native performance floors.

| Question | Evidence |
| --- | --- |
| Can inventory metadata scale with disagreement? | [Reconciliation](results/reconciliation/REPORT.md), [allocation diagnostic](results/reconciliation-allocations/REPORT.md), [conditional information model](results/information/REPORT.md) |
| What do batching, persistent connections and feedback change? | [Actual loopback delivery](results/delivery/REPORT.md) |
| Can local adaptation or 3D placement improve actual reads? | [Verified pack locality](results/locality/REPORT.md) |
| Does bounded evolutionary search beat simpler choices? | [Policy search](results/tuning/REPORT.md) |
| What can environment reuse avoid? | [Real Python consumer](results/environment/REPORT.md), [offline OCI control](results/oci-readiness/REPORT.md) |
| Which metadata must survive a shared representation? | [Roundtrip contract](results/adapter/REPORT.md) |

The [scientific models](../../../research/theory/README.md) remain hypotheses outside each measured boundary. No transport, set sketch or TLV here is a selected public Gaia protocol. Source-control history remains snapshot-based.

## Inputs and preparation

Use the pinned producer index/payload from the [preindexed artifact study](../../artifacts/README.md), and the frozen real-consumer observations from the [demand-admission study](../../artifacts/followthrough/README.md). Supply `INDEX`, `PAYLOAD` and `ADMISSION_RESULTS` paths explicitly; their hashes are recorded in every relevant raw run. No source-history file depends on an original worktree/cache path. Reacquiring the corpus uses the earlier study's pinned acquisition instructions. The package bytecode requires compatible Python 3.14 for the environment consumer; metadata/byte protocols do not execute that bytecode.

Use fresh disposable `WORK` and `OUTPUT` directories. Generated packs, SDK copies, root filesystems, container state and full raw observations stay outside source history. Commands below run from the repository root.

```sh
python3 -B experiments/science/data/make_trace.py \
  --payload "$PAYLOAD" --trace "$ADMISSION_RESULTS" --output "$WORK/coaccess.json"
python3 -B experiments/science/data/reconcile.py \
  --index "$INDEX" --payload "$PAYLOAD" --output "$OUTPUT/reconciliation" --trials 3 --lock "$MEASUREMENT_LOCK"
python3 -B experiments/science/data/diagnostics.py \
  --index "$INDEX" --payload "$PAYLOAD" --output "$OUTPUT/reconciliation-allocations"
python3 -B experiments/science/data/information.py \
  --results "$OUTPUT/reconciliation/results.json" --output "$OUTPUT/information"
python3 -B experiments/science/data/delivery.py \
  --index "$INDEX" --payload "$PAYLOAD" --output "$OUTPUT/delivery" --trials 3 --lock "$MEASUREMENT_LOCK"
python3 -B experiments/science/data/locality.py \
  --input "$WORK/coaccess.json" --payload "$PAYLOAD" --work "$WORK/layouts" \
  --output "$OUTPUT/locality" --geometry "$GEOMETRY_ORDERS" --trials 3 --lock "$MEASUREMENT_LOCK"
python3 -B experiments/science/data/tuning.py \
  --input "$WORK/coaccess.json" --output "$OUTPUT/tuning" --trials 5 --lock "$MEASUREMENT_LOCK"
python3 -B experiments/science/data/environment.py \
  --index "$INDEX" --payload "$PAYLOAD" --work "$WORK/environment" \
  --output "$OUTPUT/environment" --trials 3 --starts 3 --prepare-rootfs --lock "$MEASUREMENT_LOCK"
python3 -B experiments/science/data/adapter.py \
  --index "$INDEX" --payload "$PAYLOAD" --output "$OUTPUT/adapter" --trials 5 --lock "$MEASUREMENT_LOCK"
python3 -B -m unittest discover -s experiments/science/data -p 'test_*.py'
```

`--lock` is optional outside concurrent research. Locks cover individual cases, not whole long matrices. They exclude other cooperating timing cases, not preparation or unrelated host activity. Source hashes are checked before/after primary matrices. Allocation instrumentation is separate from primary timing.

The geometry-order file is produced by the parallel graph study from exactly the same co-access input hash. It includes lexical, BFS and native 1D/3D force orders. Omit `--geometry` to run the independent physical/static/reinforcement controls. Orders must be complete permutations; held-out requests cannot train placement.

## Offline OCI control

Podman/rootless namespaces are an additional capability, not a prerequisite for the user-mode environment experiment. Its new private store uses no downloaded image. `environment.py --prepare-rootfs` copies the local compatible interpreter, standard library and discovered runtime libraries, preserves executable modes, and includes the same framework consumer/dependencies. This is a prepared root filesystem rather than an OCI image distribution or lazy-pulling test.

```sh
python3 -B experiments/science/data/oci_probe.py \
  --rootfs "$WORK/environment/oci-root" --storage "$WORK/container-state" \
  --runtime "$WORK/container-user" --runroot "$WORK/container-runtime" \
  --tmpdir "$WORK/container-tmp" --environment-results "$OUTPUT/environment/results.json" \
  --output "$OUTPUT/oci-readiness" --trials 3 --lock "$MEASUREMENT_LOCK"
```

Create the runtime directories first and use a host with working user namespaces/OCI runtime permissions. The measured managed sandbox could not create sockets or map namespace IDs; approved host-local runs supplied those capabilities. Every container has networking disabled, a read-only root and disabled cgroup management. It performs stronger isolation than direct Python, so its readiness time is not an equal-capability speed comparison.

## Boundaries

The delivery service is real TCP loopback with matched persistent HTTP/1.1 POST batches and binary frames, while latency/bandwidth phases are application-service delay models. It is not WAN or physical-device emulation. The generic blob consumer verifies every body; it does not execute Django during transfer.

The locality reader performs real warm pack reads and per-chunk verification. Its cache budget counts retained chunk payloads; producer input, Python metadata and transient group buffers are separate. No strict RSS, mapped-reader lease, concurrent compaction or power-loss guarantee follows.

The environment consumer executes actual Django setup, a DRF serializer, a Django template and a package resource read in fresh isolated Python processes. A read-only dependency contract permits sharing. This does not establish writable virtualenv isolation or remote toolchain acquisition cost.

Initial developer-only exploratory outputs remain ignored, including a no-NODELAY HTTP smoke and an early cache recency variant. Published locality/search results mark a demanded chunk as most recent after prefetch. Every published report points to its own frozen raw identity.
