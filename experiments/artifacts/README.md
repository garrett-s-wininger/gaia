# Artifact transfer research

This track measures the cost of retrieving a caller-selected set of immutable blobs. It keeps metadata separate from payload, independently verifies requested content and includes local publication in the operation clock. It is a Python standard-library transport baseline; native production implementations remain Odin work.

Start with the [findings](../../research/artifacts/findings.md), [next questions](../../research/artifacts/prospects.md) and [research design](../../components/artifact-host/transfer-research.md). The first [report](results/initial/REPORT.md) records measured results, scope and limits.

## Reproduce

Python 3 with standard-library HTTP/multiprocessing support is sufficient. No package installation or external infrastructure is required. The harness generates deterministic bytes, starts a separate loopback server process and tears it down afterward. Local socket creation must be permitted.

```sh
python3 -B -m unittest discover -s experiments/artifacts -p 'test_*.py' -v
python3 -B experiments/artifacts/benchmark.py \
  --corpora small mixed --delays 0 2 --trials 7 \
  --output experiments/artifacts/_work/runs/first
```

Choose a fresh output directory each run. The initial matrix has two corpora, two injected delays, six scenarios, five modes and seven randomized blocks: 840 fetches. `--corpora large` adds eight 1 MiB blobs. `--input-dir /path/to/inputs` adds an arbitrary regular-file corpus, deduplicated by content; symlinks and collections beyond the experiment bounds are rejected. Source discovery, corpus creation and immutable server admission are setup costs, not hidden in a payload-only number.

For a short functional check rather than a timing conclusion:

```sh
python3 -B experiments/artifacts/benchmark.py \
  --corpora small --delays 0 --trials 1 \
  --scenarios metadata-only cached-all \
  --modes objects-serial pack-coalesced \
  --output experiments/artifacts/_work/runs/smoke
```

## What is compared

| Mode | Mechanism |
| --- | --- |
| `objects-serial` | Persistent HTTP connection, one GET per missing blob. |
| `objects-parallel` | Up to eight concurrent persistent connections, one GET per missing blob; executor and connections start inside the fetch. |
| `pack-exact` | One single-range GET per missing nonempty blob. This controls for packing without reducing request count. |
| `pack-coalesced` | Merge nearby missing regions with a 64 KiB gap budget and 4 MiB span target. Requested blobs are individually verified; gap bytes are not admitted. |
| `pack-full` | Fetch the full pack, verify its digest, then verify/admit requested blobs. |

All modes fetch and verify a cold manifest first. Previously trusted cached manifests are rehashed and parsed locally. `metadata-only` requests no payload. `cached-all` seeds both the pinned manifest and every blob and must issue zero network requests. `cached-90` seeds 115/128 blobs; `sparse-10` requests 12/128 blobs from an empty cache; `one-missing` needs exactly one blob. Cache seeds and random selections are identical across modes, independently restored before every sample.

The manifest is a private, versioned JSON fixture with explicit SHA-256 tagging, logical blob digest/size and a separate pack digest/size/offset layout. URLs and cache paths are algorithm-namespaced. This is not a public Gaia protocol, OCI manifest, REAPI implementation or a global digest decision. Unsupported algorithms fail.

## Timing and correctness

A fetch includes cache-directory setup, manifest acquisition or local lookup, digest/version/geometry checks, local cached-content verification, missing payload transfer, requested-object hashing, atomic object publication, completion receipt publication and connection closure. Client Python process startup and resident server startup are excluded. Manifest, cache-validation, payload-plus-verification/publication and receipt subclocks are reported; they are not network-only timings. File writes use atomic rename without fsync, so the result does not establish power-loss durability.

The server holds immutable payloads in memory in a separate process. ETags are computed during server admission, avoiding a whole-pack hash per range request. Client and server disable Nagle. Server request/payload counters independently check client counters after every timed fetch. A separate parent check compares all requested local bytes and the completion receipt against the generated collection after timing.

The two delay cases are plain loopback and a 2 ms sleep before each response. That sleep is an application-delay sensitivity test, not a WAN RTT, packet-loss, bandwidth, TLS or HTTP/2/3 model. Parallel HTTP/Python overhead is visible in the loopback results and cannot be generalized to a native multiplexed implementation.

Tests cover manifest/schema bounds and algorithm rejection, empty/deduplicated content, coalescing bounds, atomic-write failure, all five successful transfer paths, fully pinned offline reuse, corrupt-cache repair, ignored-Range full-pack fallback, incorrect manifest/payload digests, truncation, validators, range geometry, content encoding and retention/reuse of already verified objects after a failed fetch.

## Evidence

[summary.json](results/initial/summary.json) retains medians/ranges, phase clocks, exact byte/request counts and paired comparisons; [validation.json](results/initial/validation.json) binds the ignored raw run. [correctness-tests.txt](results/initial/correctness-tests.txt) records the test outcome. Full `results.json`, generated bytes, per-run caches and frozen measured source copies stay ignored. The [run index](../../research/artifacts/experiments.json) and [evidence manifest](../../research/evidence.json) locate retained evidence and local-only raw identities.

## Binary framing with matched plans

The [binary framing experiment](../../components/artifact-host/binary-framing.md) adds a bounded versioned TCP envelope while retaining HTTP. Both adapters use the same JSON manifests, trusted descriptors, SHA-256 checks, plans, cache publication and receipts. A shared `selected-batch` mode also runs over both transports with identical binary request/response bodies; its batching gain is separate from the envelope comparison.

```sh
python3 -B -m unittest discover -s experiments/artifacts -p 'test_*.py' -v
python3 -B experiments/artifacts/framing_benchmark.py \
  --corpora small mixed --delays 0 2 --trials 7 \
  --output experiments/artifacts/_work/runs/framing
```

A short functional check uses `--corpora small --delays 0 --trials 1 --scenarios metadata-only cold-all cached-all cached-90 --modes pack-coalesced pack-full selected-batch`. The full matrix pairs identical mode plans across both transports: 2,016 fetches. Each pair must have identical operation/payload counts, digest work, cache hits and publication counts. Envelope bytes are reported separately from content and batch-record overhead; they exclude TCP/IP, retransmission and TLS bytes.

The original HTTP driver keeps its original five default modes. `--modes selected-batch` opts into the added HTTP batching control. The framing driver includes all six modes by default. Run [the framing report](results/framing/REPORT.md) alongside [the original baseline](results/initial/REPORT.md); frozen measured sources preserve the earlier implementation even as the harness evolves.


## Bounded-buffer and vectored-write comparison

The `binary-buffered` implementation keeps the original binary wire format and transfer semantics. It reads through a bounded 64 KiB socket buffer into owned result bytes and sends prefix/payload vectors without concatenating the bulk response. It retains original binary and HTTP controls and the same verification/publication phase clocks.

```sh
python3 -B -m unittest discover -s experiments/artifacts -p 'test_*.py' -v
python3 -B experiments/artifacts/framing_benchmark.py \
  --transports http binary binary-buffered \
  --corpora small mixed --delays 0 2 --trials 7 \
  --modes pack-coalesced pack-full selected-batch \
  --output experiments/artifacts/_work/runs/buffered
python3 -B experiments/artifacts/profile_transfer.py --corpus mixed \
  --output experiments/artifacts/_work/runs/buffered-profile/profile-summary.json
```

The full comparison has 1,512 timed fetches and validates both semantic-work equality and original/buffered binary wire-length equality. The separate allocation/socket-call diagnostic uses intrusive tracing and must not be treated as randomized latency samples. The [report](results/buffered/REPORT.md), [summary](results/buffered/summary.json), [compact allocation evidence](results/buffered/allocation-profile.json) and [39-test log](results/buffered/correctness-tests.txt) retain the outcome: a clear receiver-memory improvement and selective modest latency wins, without a universal bulk win over batched HTTP. Cold operations still perform 130 common atomic publications; a local packed/indexed store would be a separate optimization for both transports.

## Verified local pack/index admission and logical access

[cache_store.py](cache_store.py) provides per-blob file and immutable pack/index cache layouts behind the same logical-byte interface. The [local representation design](../../components/artifact-host/local-cache-research.md) explains versions, ownership, transaction recovery, bounds and compatibility. The transfer protocol does not change.

```sh
python3 -B -m unittest discover -s experiments/artifacts -p 'test_*.py' -v
python3 -B experiments/artifacts/admission_benchmark.py \
  --corpora small mixed --delays 0 2 --trials 7 \
  --output experiments/artifacts/_work/runs/admission
```

The 1,344-operation matrix compares files/packed on both HTTP and buffered binary, using coalesced and selected-object-batch plans. Acquisition includes per-requested-blob verification, atomic cache publication and the receipt. The complete primary endpoint also opens the cache afresh and returns verified read-only logical views backed by owned bytes. A second measured step obtains ordinary file paths: the file layout reuses its files, while packed data pays to create requested files. Both separate and combined costs are retained. Parent checks compare every view and ordinary-file byte after timing.

Empty cache initialization, previously verified seed preparation and server/input admission occur outside timing. All measured lease/open, metadata, cache validation, transfer, logical hashing, representation sealing/index hashing, publication and fresh consumer reads remain inside. Packed extra representation work is reported separately instead of pretending total hash work is identical. The file control retains its existing no-global-disk-quota policy; the packed data/index cache has explicit 64 MiB/eight-pack limits and bounded consolidation. Common manifests retain a per-record bound without a global count/eviction policy; caller-owned materialization output is separate. Production RSS limits, eviction, durable fsync recovery and distributed writers are not implemented.

A short functional run uses `--corpora small --delays 0 --trials 1`. `--modes pack-full` optionally tests that transfer plan; all modes are covered by correctness tests, while the measured matrix focuses on coalesced and selected-batch plans. `--input-dir /path/to/inputs` adds a caller-selected bounded regular-file corpus as before.

The [report](results/admission/REPORT.md), [summary](results/admission/summary.json), [validation](results/admission/validation.json) and [49-test log](results/admission/correctness-tests.txt) retain the outcome. Logical-byte consumers gain on bulk/reuse cases on both transports; many wins disappear or reverse when ordinary file materialization is required. This shared storage/access result is separate from framing and buffering.

## One-connection request windows and progressive missing-list streams

The [GAF2 experiment](../../components/artifact-host/pipeline-research.md) compares four paths on one matched server: serial objects, eight independent pending requests, existing whole-body selected batches and progressive selected batches. A known manifest already describes availability. Both list paths send the whole missing hash list once; progressive delivery changes buffering/progress rather than saving an additional request.

```sh
python3 -B -m unittest discover -s experiments/artifacts -p 'test_*.py' -v
python3 -B experiments/artifacts/pipeline_benchmark.py \
  --corpora mixed --delays 0 2 --trials 3 \
  --output experiments/artifacts/_work/runs/pipeline
python3 -B experiments/artifacts/pipeline_benchmark.py \
  --corpora mixed --delays 2 --trials 1 \
  --profiles cold-index offline --paths batch-buffered batch-streamed \
  --output experiments/artifacts/_work/runs/pipeline-boundary
```

The first matrix has 144 operations: both cache layouts, established cold/90%-cached payloads and newly connected cold payloads with a pinned index. The eight-operation boundary separately covers cold discovery and fully cached offline access. The nonzero readiness sleep is independently scheduled per request on eight server workers and is charged once per list stream, not per record. This is an application-readiness model, not real WAN latency.

First-new-verified time means owned bytes after digest verification and before cache publication. Complete timing retains all cache/receipt work and fresh logical consumer reopen; ordinary-file materialization remains separate and combined. The [report](results/pipeline/REPORT.md), [summary](results/pipeline/summary.json), [validation](results/pipeline/validation.json) and [56-test log](results/pipeline/correctness-tests.txt) record the result and bounds. Established connection/primer samples are retained separately; fresh pinned requests include connection setup. Fully cached pinned access opens no connection. See the report for whole-frame head-of-line blocking and mandatory connection disposal after pending-response errors or abandoned iterators.

## Trusted lock to real Python execution

[locked_python.py](locked_python.py) accepts a trusted local hash/size/name lock and streams only missing hashes without retrieving the server collection manifest. It retains the existing immutable local pack/index and exposes its bytes to the prior indexed Python import/resource provider. A separate exact name/version pinned-catalog resolver is included; no registry or dependency solver runs in the acquisition measurement.

```sh
python3 -B -m unittest discover -s experiments/artifacts -p 'test_*.py' -v
python3 -B experiments/artifacts/locked_python_benchmark.py \
  --fixture /path/to/existing-django-fixture \
  --output experiments/artifacts/_work/runs/locked-python --trials 3
```

The fixture must contain `rest-bytecode/`, `rest-bytecode.zip`, `rest-bytecode.index` and `rest-expected.json` from the [prior pinned Django experiment](../python/dependency_bundles/README.md#real-django-application). Its ordinary reproduction builds these inputs under ignored `_work/`; select the generated fixture directory explicitly rather than relying on a machine-specific default. No native library is required by this new consumer adapter, although the predecessor's full reproduction also builds/runs native controls. Bytecode is interpreter-version-specific and must be rebuilt on another interpreter as in the predecessor. ZIP/index/bytecode production is a stated producer prerequisite, not part of the new acquisition clock.

The bounded first comparison uses directory and indexed-ZIP controls plus direct packed loading, with cold and offline-reuse operations in three randomized blocks after one correctness warmup. Complete install and full child-process shutdown are timed; application/module/resource behavior must match. Physical transfer representations and per-read integrity differ explicitly. The [report](results/locked-python/REPORT.md), [summary](results/locked-python/summary.json), [validation](results/locked-python/validation.json), [60-test log](results/locked-python/correctness-tests.txt) and [contract](../../components/artifact-host/locked-python-research.md) retain evidence. It is a functional direct-consumer proof with substantial observed timing drift, not a speedup over the indexed ZIP.

## Retained binary consumer index and matched integrity

[compact_python.py](compact_python.py) builds a bounded mapped local logical-name/offset index during charged installation. The same reader loads packed and ZIP payloads with SHA-256 **and** CRC32 on every read, pinned whole-index validation and local stat binding. Original ZIP/CRC and pack/SHA remain separate controls. The [layout/trust contract](../../components/artifact-host/compact-python-research.md) explains admission, lifetime and stale-index handling.

```sh
python3 -B -m unittest discover -s experiments/artifacts -p 'test_*.py' -v
python3 -B experiments/artifacts/compact_python_benchmark.py \
  --fixture /path/to/existing-django-fixture \
  --output experiments/artifacts/_work/runs/compact-python --trials 5
```

The fixture and producer prerequisites are the same as the trusted-lock comparison above. Four readers, cold/reuse and five shuffled blocks produce 40 retained observations after eight warmup operations. New consumer-index production remains inside cold install, and complete normal Python shutdown remains inside the full operation. Setup/read/hash clocks, paired block deltas, process spread ratios, zero-network reuse and application/module/resource equality are retained. The [report](results/compact-python/REPORT.md), [summary](results/compact-python/summary.json), [validation](results/compact-python/validation.json) and [constructor diagnostic](results/compact-python/setup-profile.json) separate the setup win from cold-production and acquisition costs. The diagnostic uses intrusive profiling separately and must not be treated as randomized latency evidence.

## Generic JSON/binary resolved-lock comparison

[generic_lock.py](generic_lock.py) implements a generic already-resolved manifest with optional ecosystem/name/opaque-version identities, algorithm-tagged content descriptors, many-to-many artifact associations and independently addressed opaque metadata. Its lazy binary reader retains bounded validated tables without rebuilding record dictionaries by default. Both formats are exercised against the same packed consumer and per-read SHA-256+CRC checks.

```sh
python3 -B -m unittest discover -s experiments/artifacts -p 'test_*.py' -v
python3 -B experiments/artifacts/generic_lock_benchmark.py \
  --fixture /path/to/existing-django-fixture \
  --output experiments/artifacts/_work/runs/generic-lock --trials 5
```

The existing fixture needs `rest-bytecode/` and `rest-expected.json`; use the prior Django reproduction above to prepare interpreter-compatible pinned inputs. Two formats × cold/reuse × five blocks yield 20 retained observations plus four warmups. Cold encoding/hash production, actual JSON/binary parsing, Python adaptation and consumer-index construction are included. The separate parse CPU/wall and allocation diagnostic excludes already provided input bytes and does not replace complete-operation evidence. [Report](results/generic-lock/REPORT.md), [summary](results/generic-lock/summary.json), [validation](results/generic-lock/validation.json), [parse observations](results/generic-lock/parse-profile.json), [71-test log](results/generic-lock/correctness-tests.txt) and [format proposal](../../components/artifact-host/generic-lock-research.md) retain outcomes and bounds. No solver, registry or universal version semantics are implemented.

## Producer-preindexed portable payload/index pairs

[preindexed_bundle.py](preindexed_bundle.py) admits a portable producer-built logical/offset index plus payload as two CAS artifacts. Both flat payload and stored ZIP use the same generic binary lock, complete table admission, small local stat binding and mapped SHA-256+CRC reader. The index artifact contains no producer machine path/inode identity. Producer construction is recorded separately; the receiver creates no derived tables or loose dependency files.

```sh
python3 -B -m unittest discover -s experiments/artifacts -p 'test_*.py' -v
python3 -B experiments/artifacts/preindexed_bundle_benchmark.py \
  --fixture /path/to/existing-django-fixture \
  --output experiments/artifacts/_work/preindexed/runs/main --trials 5
```

Provide the same prior `rest-bytecode/` and `rest-expected.json` fixture. Large generated producer/cache data is stored under `_work/preindexed`; on constrained temporary filesystems, point that ignored directory at an adequately sized local disk. The local `_work` ignore covers both ordinary directories and symbolic links; no machine-specific storage link is versioned. The first matrix has 20 retained observations plus four warmups. [Report](results/preindexed-bundle/REPORT.md), [summary](results/preindexed-bundle/summary.json), [validation](results/preindexed-bundle/validation.json), [74-test log](results/preindexed-bundle/correctness-tests.txt), [lookup diagnostic](results/preindexed-bundle/lookup-profile.json) and [portable contract](../../components/artifact-host/preindexed-bundle-research.md) retain the outcome. Optional separate profiling uses `profile_preindexed_lookup.py --run /path/to/results.json --output /path/to/lookup-profile.json`; intrusive timing is not randomized benchmark evidence.

[Experiment notes](FINDINGS.md) retain the detailed comparisons behind the linked research review and reports.
