# Trusted hash lock to direct packed Python execution

Run `20261031T013718.168635Z`. Functional end-to-end proof; three randomized blocks after one correctness warmup. **Timing stability is limited by substantial within-run drift.**

The path works: a trusted local lock supplies logical names, SHA-256 hashes and sizes; the client sends only its missing hash list, receives progressive records, verifies each object and retains one immutable local pack/index. A fresh Python process imports and reads resources directly from that pack. It creates no loose dependency files. The real pinned Django REST fixture passes unchanged application validation.

## Exact input and representation controls

Django 6.1.2, asgiref 3.13.0, sqlparse 0.6.0, REST framework 3.18.3 and django-filter 26.2 are the same published pinned dependencies used in the [earlier indexed-path experiment](../../../python/dependency_bundles/results/path-index/REPORT.md). The [wheel provenance](provenance.json) records producer URLs and hashes. This run uses its existing interpreter-compatible **bytecode** fixture only: 4,018 logical files, 28,696,585 logical bytes, 455 loaded dependency modules and the same API/admin/template/resource checks. Source-only performance is not established.

| Representation | Payload hashes requested cold | Payload bytes transferred | Install behavior |
| --- | ---: | ---: | --- |
| Direct pack | 3,931 unique logical file contents | 28,590,229 | Stream directly into the existing versioned immutable pack/index cache. |
| Indexed stored ZIP | ZIP plus producer binary index | 29,661,933 | Retain downloaded ZIP; bind producer index to admitted local identity, validate index and record its new pin. |
| Directory | Same ZIP plus index control | 29,661,933 | Retain downloaded artifacts, validate exact file set and SHA-256 of each extracted file, then write ordinary paths. The index is not needed by this consumer but held identical to the ZIP transfer control. |

All cold paths use one fresh TCP connection and one streamed missing-list request, with **zero remote collection-manifest requests**. Different physical representations intentionally have different descriptor counts and bytes; this is an end-to-end representation/consumer comparison, not a matched framing benchmark. The direct lock is 599,421 bytes versus 770 bytes for the two-artifact lock. Both are already locally trusted inputs and both are parsed/verified inside acquisition. Name/version discovery is a separate contract, described below. Server corpus construction and prebuilt ZIP/index/bytecode production are excluded, explicitly pre-existing inputs. This run records 0.396 s of fixture scanning, lock construction and server collection preparation, but does not remeasure historical bytecode/ZIP production.

## Full acquisition, install and normal process lifecycle

Each cold case uses a fresh destination; filesystem pages are warm and payloads are served from loopback memory, so this is not storage-cold or WAN evidence. Acquisition includes local lock hashing/parsing, cache checks, all selected transfer/digest work, representation sealing, atomic publication and requested-set receipt. Install additionally includes extraction or binary-index rebinding/validation where needed. After the complete requested set is admitted, a fresh `python -I -S -B` process mounts the representation, runs WSGI/admin/ORM setup, checks Django, creates two in-memory SQLite rows, serves filtered JSON, renders admin login, validates versions/origins/resources, closes providers/database and exits normally. The parent waits for full shutdown; no early exit/readiness shortcut is used. Reuse repeats acquisition and execution against an unavailable endpoint and must perform zero network requests.

All three processes use the same wrapper and common adapter imports; their cost is included in process wall time. The earlier worker is reused unchanged. The packed adapter substitutes its byte reader behind the existing indexed path/import/resource APIs. Host interpreter, stdlib/native extensions and project fixture remain outside the dependency representation in every control.

**Observed medians, milliseconds; independent medians do not necessarily add:**

| Profile / representation | Acquisition | Complete install | Python process | Acquisition/install + process | Framework ready inside workload |
| --- | ---: | ---: | ---: | ---: | ---: |
| cold / directory | 39.08 | 385.42 | 414.08 | 799.55 | 160.89 |
| cold / indexed-zip | 37.34 | 46.48 | 396.23 | 442.79 | 158.77 |
| cold / packed | 98.33 | 98.33 | 579.96 | 683.26 | 272.24 |
| reuse / directory | 18.70 | 18.72 | 403.94 | 422.72 | 171.71 |
| reuse / indexed-zip | 17.44 | 17.64 | 461.05 | 478.78 | 166.86 |
| reuse / packed | 52.51 | 52.51 | 548.71 | 625.46 | 225.74 |

The direct pack avoids directory extraction and has lower cold end-to-end totals in all three same-block comparisons against directories. It **does not beat the existing indexed-ZIP control**: packed total minus indexed ZIP is **+19.29 / +248.54 / +82.54 ms cold**, and **+60.32 / +288.30 / +95.40 ms reuse**. Packed minus directory cold is **−247.24 / −108.22 / −660.46 ms**; directory reuse reverses in two of three blocks. These are paired observations, not a stable speedup estimate.

Environment drift is large: indexed-ZIP cold child processes grow from **341.54 to 396.23 to 551.20 ms**, while directory cold children grow **295.46 / 414.08 / 602.75 ms**. The uncorrected preliminary run and correctness smoke are not pooled. The final control removes a redundant hash of already pinned producer ZIP bytes when constructing local cache paths; actual acquisition integrity hashing remains. No additional optimization sweep is included.

## What the existing clocks can explain

Packed cold lock parsing alone is about **11.45 ms**, versus **0.08 ms** for the two-artifact lock. Reuse parses the direct lock in about **10.79 ms**, then cache construction/verification costs about **36.38 ms**; the indexed-ZIP lock/cache-check equivalents are **0.07/17.01 ms**. Sending the whole list once removes request amplification but does not eliminate processing thousands of descriptors.

The worker places much of the startup difference inside framework initialization (cold medians: packed **243.93 ms**, indexed ZIP **140.92 ms**), while final validation is only approximately 1–2 ms. That initialization clock includes provider open/index construction and all framework imports; it does **not** isolate locator-JSON reconstruction, module-table construction, reads or code execution. Do not attribute the entire difference to hashing or a wire protocol without a profile.

Consumer validation also differs explicitly. The packed reader verifies the pinned logical lock and local index, checks pack magic/size, retains pack file descriptors and SHA-256-verifies each requested logical file on every read. Indexed ZIP verifies its pinned admitted sidecar and stat identity, maps the ZIP and CRC-checks each read. Directory imports use ordinary Python file loading after acquisition/extraction validation. All supply matching application bytes and outputs, but they are not identical per-read integrity algorithms or syscall/memory-access implementations. No generic verified-session bypass has been established.

## Discovery, compatibility and failure limits

The [lock/consumer design](../../../../components/artifact-host/locked-python-research.md) keeps exact name/version discovery separate from hash retrieval. A minimal pinned-catalog resolver and CLI return a lock descriptor for one exact name/version, reject duplicate identities/unsupported descriptors and do no version solving. The measured operations begin with an already trusted lock; catalog download, authentication and policy are not hidden inside the reported hash-set acquisition.

The pack preserves existing 64 MiB/eight-pack limits, bounded staging, atomic head/index/receipt publication and SHA-256 corruption checks. Failed streams leave no successful receipt, and later acquisition repairs corrupt or missing content. This prototype uses rename without fsync; it is not power-loss durability. Ordinary-directory installation is an experimental extraction control, not a crash-recoverable package manager. Immutable local admission assumes no hostile concurrent writer. Native/namespace wheels, arbitrary filesystem consumers, editable installs, extension ABI management, scripts and entry points are outside this proof. No dependency files are silently extracted for the packed consumer.

All **60 correctness tests** pass. The final run validates **24 complete operations**, including six warmup operations and **18 retained timed observations**, with identical dependency module origins/executions, API result, app count and three resource hashes. [Summary](summary.json), [validation](validation.json), [correctness log](correctness-tests.txt) and the [evidence manifest](../../../../research/evidence.json) retain reviewable evidence. Raw observations and frozen measured sources remain ignored local artifacts.

The result supports direct packed execution as a working integration and a cold-install alternative to extracting thousands of files. It does not establish a startup or end-to-end advantage over a competent indexed ZIP. The next bounded investigation should profile immutable metadata construction and compare a compact portable index/permitted verified-session trust contract with equivalent consumer integrity checks; native implementation should follow evidence.
