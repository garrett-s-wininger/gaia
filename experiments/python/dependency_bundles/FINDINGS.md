# Dependency-loader findings

For current conclusions and practical limits, start with the [research review](../../../research/python/dependency-formats.md). These notes retain the detailed experiment comparisons; measured reports remain under `results/`.

Latest: [the generic byte-access follow-up](#generic-byte-access-follow-up) isolates positional/mapped/resident reads while retaining the same stored ZIP bytes and CRC policy. Earlier loading/lifetime results remain below in order.

Run: `20261028T203402.062015Z`. Full tables: [REPORT.md](results/REPORT.md). Raw observations and environment: results.json (local artifact, `results/results.json`). Reproduction: [README.md](README.md).

## Result

Bundling alone did not beat directory loading on this synthetic warm-cache workload. A small resource-loader hook fixed a substantial repeated-setup cost, but the ZIP module-loading path remained slower. This is useful evidence for adapting the actual consumer's access/lifetime model rather than assuming a new container is sufficient.

The run covers **30 cases and 450 timed fresh interpreter processes**, plus 30 separate syscall-traced runs and 30 separate memory observations. Each case has 15 timing trials after a warmup. Inputs are 64, 512, or 2,048 generated leaf modules, each with 24 additional package/helper modules and 32 resources. Source-only and equivalent precompiled-bytecode layouts are separate cases. Tests also exercise failure/no-fallback behavior; no packages were downloaded.

At 2,048 leaf modules, source-only inputs:

| Loader | Median process ms | Median resource ms | Metadata calls | Opens | Counted syscall set | Returned read MiB | Allocated input MiB | Peak RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| directory | 357.70 | 2.18 | 8,469 | 4,207 | 21,168 | 0.45 | 8.301 | 26.90 |
| stored | 774.62 | 296.72 | 4,264 | 4,189 | 25,607 | 527.64 | 0.711 | 28.60 |
| shared-stored | 468.68 | 12.28 | 4,213 | 4,150 | 25,095 | 519.45 | 0.711 | 28.55 |

Process wall includes common interpreter/harness setup and validation. Resource time is just the measured resource phase. Trace counts exclude setup/validation and cover the selected syscall set, not every possible syscall. Memory is a separate untraced executed-process observation, not a timing-sample median or isolated archive-memory measurement. Allocated input size excludes the shared interpreter/harness and depends on filesystem block allocation.

The shared-reader variant reduced resource time by **24.2x** against stock stored-ZIP loading, using the **same ZIP bytes** and the same built-in module/bytecode importer. It still took **31.0% longer** end to end than directories. Against directory loading it reduced metadata calls by **50.3%** and allocated input space by **91.4%**, but neither total counted calls nor returned read bytes improved. It did not establish a memory win. Compressed and precompiled cases also remain in the complete report; none should be conflated with source-only results.

## What the loading hook changed

In the observed Python standard-library implementation, `importlib.resources.readers.ZipReader.files()` constructs `zipfile.Path(self.archive, ...)` from an archive pathname. Repeated resource access recreates archive views/index setup. [shared_zip_resources.py](shared_zip_resources.py) replaces only the resource reader through a scoped path hook and reuses one lazily opened `ZipFile`. Index/open cost stays inside resource timing. Correctness checks confirm that the shared variants actually use the hook and open exactly one resource archive handle.

Module loading still uses `zipimport`. Local inspection of `/usr/lib/python3.14/zipimport.py` shows that `_get_data()` opens the archive and `get_filename()` obtains module code to determine the origin. The traces show repeated large buffered reads: the source-only shared-stored case made **4,154 reads returning 128 KiB each** during the marked workload. This explains substantial kernel-to-process byte traffic even for tiny modules; it is not evidence of that much physical disk I/O. The data was already touched/warmed.

The hook is an experimental Python adapter, not a new native storage engine or a standardized Gaia protocol. The remaining observation motivates a reusable indexed/range-readable module provider rather than replacing ZIP before understanding the access pattern.

## Preparation and compatibility costs

Archive creation and directory export were timed once per container, with exact member equivalence checked afterward. For this 2,048-module source fixture, stored-ZIP packing took 144.33 ms and compatibility extraction took 406.58 ms. A one-shot conversion from an already usable directory therefore loses further time; persistent reuse is a different scenario. Precompilation of the corresponding bytecode fixture took 1010.07 ms and is reported separately, not credited as a ZIP speedup.

These are synthetic fixture preparation/pack/export observations, not full registry download/install measurements. Pack/export timings exclude the extra correctness-validation passes, whose reads also warm caches. The report's pack-plus-process column is labeled accordingly. No compression/installation/network savings have been assumed beyond what was measured.

## Environment and limits

- Python: `3.14.8 (main, Oct  2 2026, 10:23:31) [GCC 16.2.1 20260810]`.
- Environment: `Linux-6.18.33.2-microsoft-standard-WSL2-x86_64-with-glibc2.44`, `ext2/ext3` filesystem report, 16 logical CPUs. This is the available execution environment, not independently verified as the user's physical laptop.
- Trials use fresh processes and reused/warm filesystem cache. There is no controlled cold-storage result.
- Work is intentionally import-heavy and the application loop is small. Arbitrary real packages, native extensions, namespace/install semantics, compiler workloads, and networked providers remain untested.
- Peak RSS uses `/proc/self/status` `VmHWM`. An isolated probe exposed inherited parent high-water values in `getrusage().ru_maxrss`; original values are retained under `reported_ru_maxrss_bytes` but are not used for consumer-memory conclusions. Supplemental memory observations do not replace or alter timing samples.
- Tracing runs separately because it perturbs timing. Read counts/bytes include all activity inside the workload markers, including any lazy standard-library loading, rather than dependency-only path attribution. Summed medians of individual phases need not equal median total time.
- Fifteen trials and one preparation/export sample are an initial checkpoint, not a stable cross-machine performance guarantee. Results can be reproduced without requiring exact timing equality.

## Next experiment suggested by the first run

Keep the same fixture and ZIP container while testing an input provider that shares module as well as resource access, supports precise/range reads, and avoids reopening and fetching code solely to discover names. Preserve Python import semantics, useful origins, relative imports, resource access, and explicit errors. Compare correctness and timing/traffic against these baselines before designing a new format.

Then add a small pinned real-package workload. Generalize the demonstrated input-access contract into other language/compiler adapters only after identifying the metadata and lifetime semantics those consumers actually need. This run supports the importance of the consumer integration boundary; it does not yet demonstrate the broader platform's desired speedup.

## Process-lifetime follow-up

The first hook above retained an archive only for resources. All imports already occurred in one consumer process, but standard ZIP module loading still reopened the file. There was no per-module IPC; each benchmark trial alone started a new process. Python's stock ZIP directory index was cached, so repeated module opens should not be described as repeated full index parsing.

The follow-up [persistent_zip_loader.py](persistent_zip_loader.py) uses one lazily opened archive for the entire module/resource consumer session. It parses the ZIP directory once, retains lookup tables, returns origins without reading code, reads each module once, and closes the handle during final consumer cleanup. Opening/indexing occurs inside import timing. Both modules and resources use the same handle; no custom container format was introduced.

Run `20261028T205055.233700Z`: **14 cases, 210 timed subprocesses, and 14 separately traced runs**, all at 2,048 leaf modules plus 24 package/helper modules and 32 resources. Baselines were rerun with the same common harness setup; compare within this run rather than mixing medians across runs. Raw data: results.json (local artifact, `results/persistent/results.json`). All cases: [REPORT.md](results/persistent/REPORT.md).

| Loader | Source process median ms | Bytecode process median ms | Source workload opens | Source metadata calls | Source returned read KiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| directory | 345.47 | 211.06 | 4,207 | 8,469 | 465.47 |
| stored | 750.23 | 576.96 | 4,189 | 4,264 | 540307.71 |
| shared-stored | 476.71 | 282.52 | 4,150 | 4,213 | 531920.36 |
| persistent-stored | 298.23 | 199.17 | 5 | 11 | 1893.89 |
| persistent-deflated | 300.36 | 206.46 | 5 | 11 | 1765.89 |

The persistent stored-ZIP case is **13.7% faster** end to end than the directory source case in this warm synthetic workload. Its process peak RSS is about **3.05 MiB higher**. Returned read bytes remain above the directory case, even though archive reopen/buffering overhead and metadata work fall sharply. The outcome is a limited positive result, not a general Python/application/cold-storage guarantee.

Every persistent case's trace independently shows **exactly one open of the archive path** inside the workload. The other opens in the table belong to lazy standard-library work. Every correctness-checked sample reports one archive open and exactly 2,072 module reads. Discovery is tested to perform no code reads. Source and bytecode packages, relative imports, origins, resources, and missing-input failures remain verified; incompatible bytecode headers are rejected.

This change combines lifetime reuse with eliminating code fetch/compilation during filename discovery. It does not isolate the contribution of each optimization. The persistent provider has prototype scope: regular source-only or interpreter-compatible sourceless-bytecode packages, no mixed cache policy, namespace packages, native extensions, or arbitrary environment substitution. Its shared handle is local to the process; cross-process reuse has not been implemented or measured.

The next step is a small pinned real-package workload and tests of longer-lived consumers. A source/data access protocol can take the demonstrated lifetime and metadata-versus-content distinction forward, without assuming a compiler integration or new native format has already been validated.

## Interpreter floor and remaining costs

The [diagnostic report](results/diagnostics/REPORT.md) preserves an additive breakdown of the exact original median-wall observation: 175.51 ms import, 5.44 ms resources, 8.66 ms application loop, and 108.62 ms previously unpartitioned process/harness work, totaling 298.23 ms. Those are matched-sample phases, not a sum of independent medians.

Additional unprofiled trials instrument common harness setup, request/fixture preparation, validation, cleanup, and outside-child process time. They are new observations, not a retroactive subdivision of the earlier run. A no-op isolated interpreter median was 11.93 ms and the harness's common-import/setup-only probe was 68.64 ms. The rest of the original process lifetime cannot therefore be called fixed interpreter startup.

In those new trials, the persistent provider's mean import phase was 183.75 ms for source and 84.70 ms for precompiled inputs. This comparison includes changes to decoding/representation as well as eliminating source compilation. Separate instrumented import-only profiles identify compilation as the largest single function and show substantial import-machinery and ZIP-entry work. Their overhead is material: profile durations must not be substituted into unprofiled measurements. Module initialization is tiny in this synthetic fixture, which may differ strongly from real applications.

The earlier trace still contains 6,331 `lseek` calls for the persistent source case. One process-lifetime archive eliminates reopen/index churn but does not remove all per-entry stream/header/seek work. A lower-level range/memory-backed provider with explicit integrity handling, reusable precompiled artifacts, and lightweight/persistent consumers are plausible next experiments, not measured speedup promises. The profile suggests optimizing actual repeated access and compilation work before assuming that a language rewrite of the thin adapter alone removes the remaining cost.

Installed package/module counts, modules actually imported in a startup, and module initialization weight must be measured independently. The current test intentionally imports every generated module. Before claiming ecosystem relevance or a break-even count, trace pinned real dependency/application workloads and extend the persistent-provider measurements across smaller counts.

## Generic byte-access follow-up

The next experiment holds the stored ZIP bytes, payload CRC policy, compiler, and module semantics fixed. [bundle_access.py](bundle_access.py) exposes the same entry-read API through ZipFile, positional `pread`, mapped ranges, and whole-file-resident bytes. All fast readers validate local header/name/range metadata once; all backends validate payload CRC on each read/view. No new format or compiler optimization was introduced.

Raw access run `20261028T212315.366515Z` uses **2,104 entries and 429,600 payload bytes**, lexical/shuffled order, bytes/views, 15 fresh-process trials per case, and four scans per process. It has **16 cases, 240 timed processes, and 16 separate traces**. Full raw-access tables: [REPORT.md](results/access/REPORT.md), data (local artifact, `results/access/results.json`).

| Backend | Open/index ms | First scan ms | Reused scan ms | Index + first scan ms | Read calls across 4 scans | Seek calls across 4 scans |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| zipfile | 28.330 | 19.257 | 18.542 | 48.256 | 20 | 25252 |
| pread | 37.333 | 3.750 | 3.565 | 41.169 | 8416 | 0 |
| mmap | 33.898 | 1.782 | 1.877 | 36.491 | 0 | 0 |
| resident | 35.210 | 1.748 | 1.651 | 36.870 | 0 | 0 |

These rows return copied bytes and use lexical order. Index + first-scan medians come from each complete sample, not the sum of independently computed medians. Mapped first-scan access is **10.8x faster** than ZipFile; including opening/indexing, first-use time is **24.4% lower**. Shuffled access also improves; view results are separately labeled and retain CRC validation. The Python request loop, central parser, and validation still contribute, so this is an access-layer reference, not a universal hardware or native-language floor.

The separate loader run `20261028T212433.570836Z` has **12 cases and 180 timing observations**. It rereads the exact same stored bytes (SHA-256 checked between the raw and loader experiments), compiles/executes the same inputs, and uses a common resource wrapper across the four access backends. Compared with that ZipFile control, mmap reduced the source workload interval by **17.8%** and process-wall median by **9.5%**, from **310.83 ms to 281.29 ms**. Source and bytecode results, previous-provider/directory baselines, and memory are in [the loader report](results/access-loader/REPORT.md). Native compilation/bytecode policy was unchanged.

No explicit read/seek calls occur in the mmap/resident raw read loops after setup. This is not zero I/O or zero work: mapping/page faults, CRC scanning, Python dispatch, copying in bytes mode, and initial parsing/validation remain. The tiny packed corpus is already warm, and indexing itself touches many mapped pages. Cold storage and large-entry/sparse access are unmeasured. Whole-file residency has a different scaling cost from mapping and should not be selected from this small corpus alone.

The first-use bottleneck is now the **open/index phase**: roughly 28–40 ms in this implementation. A generic next experiment would build/store a reusable range index at ingestion and test a small native accessor, preserving explicit integrity/lifetime semantics. Its benefit has not been measured, and neither an index encoding nor a platform-wide protocol is frozen by this experiment.

## Prefault follow-up

Run `20261028T214337.292713Z` compares demand paging, Linux `MAP_POPULATE`, and explicit one-byte-per-page touching. It retains the original stored ZIP and adds a deterministic 64 MiB stored bundle with 64 one-MiB entries, whose header validation leaves most payload untouched. There are **12 cases and 180 timed fresh processes**, 15 randomized trials per case, each with four scans. Population is synchronous and charged to setup. Both copied bytes and views retain payload CRC on every scan and full SHA-256 validation after timing. [Full report](results/prefault/REPORT.md), raw samples (local artifact, `results/prefault/results.json`), [harness](prefault_benchmark.py).

For the larger bundle, views isolate mapped access without allocating a copied payload:

| Policy | Open/index ms | First scan ms | Index + first scan ms | First-scan minor faults |
| --- | ---: | ---: | ---: | ---: |
| Demand paging | 5.367 | 24.518 | 30.593 | 257 |
| MAP_POPULATE | 10.600 | 23.778 | 34.591 | 0 |
| Explicit touching | 8.195 | 23.408 | 31.954 | 0 |

These are medians; combined time is computed per observation before taking its median. Prefaulting removes first-scan faults here, but moves work into setup and does not improve combined first-use time. Reused view scans are approximately 23 ms under all policies, with CRC scanning and Python dispatch retained. In copied-bytes mode combined first use is about 38–39 ms for all policies; its remaining minor faults include bytes allocations, so they should not be attributed solely to the archive mapping.

The original tiny-entry bundle has a median of **zero first-scan minor faults under every policy**: index validation has already touched its mapped payload pages. Combined first-use medians range from 33.0–34.8 ms across representations/policies, with no consistent prefault advantage. No major faults occur in any timed setup/scan, consistent with this explicitly warm-cache experiment. Minor-fault deltas are process-wide and can map multiple pages; they are not counts of file pages or physical I/O.

Retain demand paging as the experimental default and keep population as an optional access policy. Prefaulting may help move latency before a critical operation when useful work can overlap preparation, but this run does not test overlap, cold storage, sparse consumption, or memory pressure. Eager whole-bundle population should not become a requirement of the input protocol on this evidence. The Python index/parser remains the larger opportunity on the original corpus.

## Precomputed index follow-up

Run `20261028T214926.016461Z` moves ZIP parsing, namespace validation, local-header checks and directory construction into producer admission. [precomputed_index.py](precomputed_index.py) writes a versioned JSON sidecar with names, offsets, lengths, CRCs, directories, whole-bundle SHA-256 and local file identity. Building it validates every payload CRC as well as ZIP metadata. The consumer loads that sidecar and uses the same mapped payload reader and language loader. This is a prototype index representation, not a new archive or standardized protocol.

There are **24 cases and 360 timed fresh processes**, 15 randomized trials per case: source, bytecode and 64 MiB larger-entry bundles, bytes/views for raw access, and source/bytecode language-loader runs. Each corpus has 15 separately timed index builds. All consumer cases share exact archive bytes within each corpus; CRC remains on every read/view and full content equivalence is checked outside timing. Tests additionally prove the saved-index consumer does not call ZipFile. [Full report](results/index/REPORT.md), raw data (local artifact, `results/index/results.json`), [reproduction](README.md).

The caller supplies a trusted digest for the sidecar; consumers hash it on every open. Two bundle-verification policies make the remaining cost visible: `index-hash` verifies whole-bundle SHA-256 at every open, while `index-local` compares device/inode/size/mtime/ctime with the previously admitted local file. The latter assumes a trusted immutable local store; stat checks are invalidation checks, not authentication or protection against concurrent writes. A trusted index certifies name-to-range associations; accepting an untrusted index just because it contains an archive hash would not suffice. Transferred bundles can use hash mode; the prototype local mode requires admission at the new location.

Source bundle results, copied-byte API, medians:

| Reader | Open/index ms | First scan ms | Setup + first scan ms |
| --- | ---: | ---: | ---: |
| Rebuild from ZIP | 27.070 | 1.699 | 28.769 |
| Precomputed, hash bundle | 3.170 | 1.747 | 4.870 |
| Precomputed, local admission | 2.418 | 2.068 | 4.449 |

Precomputed/full-hash first use is **5.9x faster** than rebuilding the ZIP index. Read-loop costs are similar; this improvement comes from reducing startup metadata work. First-use medians are taken from complete observations rather than adding independent medians. The source index adds **134,247 bytes**, **18.0%** of this tiny-file ZIP's size, and takes a median **30.823 ms** to build including validation, hashing and buffered sidecar writing. A single use must add that producer cost back: about 35.7 ms versus 28.8 ms from the existing ZIP. A simple median-based estimate amortizes construction after about two consumers of this corpus, not a universal break-even guarantee. The JSON sidecar duplicates ZIP metadata; a compact representation could reduce that overhead but is unmeasured.

The fixed source loader's process median falls from **271.611 ms to 242.343 ms** with full-hash indexing (**10.8% lower**); bytecode falls from **183.845 ms to 156.363 ms** (**14.9% lower**). Source import time falls from 151.734 to 124.261 ms. Local-admission process medians are 246.202/159.932 ms for source/bytecode; noise outside the affected phases means this run does not establish superiority between the two saved-index policies on these small bundles. Compiler behavior and module/resource contents are unchanged.

At 64 MiB, full-file hashing dominates: view-mode first use is **72.597 ms**, versus **27.710 ms** for rebuilding the small 64-entry ZIP index and **25.748 ms** with local admission. The index itself is only 3,217 bytes, with a 74.270 ms build median. Precomputing does little for an already tiny entry table if the consumer must hash a large bundle each time. Verification and immutable local admission need an explicit lifecycle boundary; moving ZIP parsing alone does not remove content-verification cost.

This supports **validating/indexing at ingestion and reusing the resulting metadata** as an input-access design direction. Keep admission, index identity, bundle identity, payload checking and reader lifetime explicit. It does not choose a permanent encoding, establish a native floor, or justify replacing the current container. Eighteen correctness tests pass, covering pinned-index corruption, stale/replaced bundles, format/version/range errors, retained CRCs, view lifetimes, and source/bytecode/resource integration. Measurements remain warm-cache and synthetic; no syscall-trace or real-ecosystem performance claim is made for this run.

## Binary index follow-up

Run `20261028T215942.023584Z` compares JSON with [an experimental binary sidecar](binary_index.py). The binary layout uses explicit little-endian fields: a 128-byte header, 28-byte entry records (payload offset/length, CRC, directory ID, basename length), directory lengths, and a UTF-8 string pool. Directory prefixes are stored once and reconstructed when loading. Both encodings describe identical logical metadata and are pinned by a caller-supplied SHA-256. The ZIP bytes, admission checks, hash/local bundle-verification policies, range checks, per-read CRCs, payload mapping and language loader remain the same.

This is **40 cases and 600 timed fresh processes**, 15 randomized trials per case, plus **90 separately timed index builds**. Both encodings and the ZIP-parsing control are rerun together; compare within this run. Full member hashes and application/origin/resource checks pass. [Full report](results/binary-index/REPORT.md), raw samples (local artifact, `results/binary-index/results.json`), [reproduction](README.md).

For the 2,104-entry source corpus, copied-byte API, medians:

| Measurement | JSON | Binary |
| --- | ---: | ---: |
| Sidecar bytes | 134,247 | 88,872 |
| Added bytes as fraction of ZIP | 18.0% | 11.9% |
| Admission + index build ms | 31.774 | 31.616 |
| Open/index with whole-bundle SHA-256 ms | 3.510 | 3.949 |
| Open/index with local admission ms | 2.709 | 3.156 |
| Setup + first scan, whole-bundle SHA-256 ms | 5.604 | 5.677 |
| Setup + first scan, local admission ms | 4.787 | 5.133 |

Binary reduces this sidecar's storage by **33.8%**, but provides **no consistent startup improvement in this Python implementation**. Both readers still decode names and construct Python `Entry` objects and dictionaries. The binary reader streams records rather than materializing JSON's row lists, but its unpack/decode/reconstruction loop executes in Python. The installed JSON scanner is native `_json`; replacing its input with fixed records is not equivalent to a native binary accessor.

A [separate in-memory diagnostic](results/binary-index/decode-diagnostic.json) fully consumes the logical document in 100 randomized trials per encoding. It observes medians of **1.204 ms for JSON and 1.919 ms for binary** on already resident bytes. It excludes file I/O, hashing, entry construction and range validation. For this diagnostic binary rows are retained in an outer list (tuples rather than JSON lists), whereas the production reader streams them. These measurements support treating parser implementation as relevant; they are not additive subdivisions of the separately recorded startup timings or a native-format comparison.

Fixed source-loader import medians are 127.094 ms for JSON/full-hash and 126.336 ms for binary/full-hash; corresponding workloads are 138.473/137.957 ms. Source process-wall medians differ more (259.144/247.171 ms), largely outside that affected workload, so that difference is not evidence of an encoding-only speedup. Bytecode/full-hash import medians are 48.303/50.183 ms, again without a consistent binary advantage. All process and phase observations are retained in the report. Large-entry startup remains dominated by whole-bundle hashing, around 47–48 ms under either encoding.

Keep binary as an available experimental encoding, with its measured storage benefit. The larger performance question is direct table access and native implementation without reconstructing every name/object/dictionary at startup; that has not been implemented or measured. This trial does not freeze the layout, require its directory representation for the platform protocol, or establish an Odin/native floor. All **24 correctness tests** pass, including cross-encoding logical equality, Unicode/root/nested paths, format/version/flags/table/string bounds, directory IDs, stale bundle identity, payload corruption, views, and source/bytecode/resource integration. Cache conditions remain warm and the corpus synthetic.

## Native Odin accessor

Run `20261028T221649.126132Z` implements [a Linux Odin accessor](native/main.odin) over the **unchanged binary sidecar and ZIP bytes**. It maps the sidecar and archive, checks the pinned index digest and table/string/range/UTF-8 structure, and reads record fields directly. It builds a basename-position array and directory views at setup, but no Python-style per-entry objects. Named access additionally constructs full names and a native lookup map. Ordinal access uses row IDs scoped to the pinned index and bypasses that map; its speedup includes changing the request API.

The compiler is **Odin dev-2026-10-nightly:84bc3fc**, built with `-o:speed`, bounds checks retained. Odin emits an object and the installed GCC 16.2.1 C driver links it, because automatic Odin linking expects absent Clang. No toolchain download or privileged action was needed. CRC uses **system zlib 1.3.2** and SHA-256 uses **OpenSSL 3.6.5**, also used by Python here. Primitive initialization is outside access setup but inside native process wall. Compiler/link commands, build duration and executable hash are retained.

There are **51 cases and 765 timed fresh processes**: 585 native and 180 Python observations, 15 randomized trials per case, four scans each. The source, bytecode and larger-entry corpora have identical bytes across readers. Per-read CRC remains; after timing, the parent independently verifies the native aggregate of per-member SHA-256 digests against the expected bytes. Python independently verifies each member hash. [Full report](results/native/REPORT.md), raw samples (local artifact, `results/native/results.json`), [reproduction](README.md).

For the 2,104-entry source corpus (429,600 payload bytes), copied-byte named reads:

| Accessor | Binding | Setup ms | First scan ms | Setup + first scan ms |
| --- | --- | ---: | ---: | ---: |
| Native known-path directory | Manifest + per-read CRC | 0.990 | 17.228 | 18.274 |
| Python binary reader | Whole-bundle SHA-256 | 3.932 | 1.754 | 5.989 |
| Python binary reader | Local admission | 3.032 | 1.949 | 4.906 |
| Odin binary reader | Whole-bundle SHA-256 | 1.225 | 0.476 | 1.711 |
| Odin binary reader | Local admission | 0.598 | 0.537 | 1.134 |

Setup + first-scan medians are computed from each combined observation, not sums of phase medians. Under local admission, Odin's named copied-byte first use is **4.3x faster than the Python binary reader** and **16.1x faster than native known-path directory reads**. Both native byte-returning paths allocate/copy/release a payload buffer per request and verify CRC. Directory paths are prepared during setup; no directory walk or dependency discovery is charged, and it has no whole-directory admission hash. This compares consumption of a trusted known input set, not general filesystem behavior.

Mapped source views further reduce Odin named/local first use to **1.008 ms**. Ordinal/local mapped views take **0.567 ms**, with **0.136 ms setup** and a **0.338 ms reused scan**. This is a measured direct-table reference point, not a universal native/hardware floor or a language-only speedup: ordinal requests skip name-map construction and lookup, and mapped views skip payload copies. All retain per-read CRC. Native generic process-wall medians for these small-input cases are about 7–12 ms, but include four scans, primitive/runtime bootstrap and extra full-content validation; they must not replace the previous 247 ms CPython source-loader result. No compiler/interpreter hookup was added.

Native metadata parsing is already relatively cheap. The restricted ZIP control rebuilds central/local ranges and checks every row against the pinned manifest; its named/local copied-byte first use is **1.504 ms**, versus **1.134 ms** for the saved index. It is not an independent general native ZIP parser: startup also loads the certified sidecar as a request/identity manifest, and it supports ordered plain stored entries rather than arbitrary ZIPs. The observed extra work is a few tenths of a millisecond on this corpus; do not attribute all native-versus-Python improvement to binary encoding or ZIP avoidance alone.

For 64 one-MiB entries, Odin and Python reused mapped-view scans are both about **24 ms**. Named/local copied-byte first use is 32.342 ms for Odin, 34.755 ms for Python and 33.348 ms for native file reads. A **44–45 ms full-bundle SHA-256 setup** remains in native hash mode. Removing Python request/object overhead helps many tiny entries far more than large payloads whose CRC, copy and hashing costs dominate. This also preserves the earlier result that trusted immutable admission and its verification lifecycle matter independently of encoding.

The native interface remains an experimental in-process accessor driven by a CLI benchmark, not per-entry IPC, a production untrusted-input service, or an open protocol declaration. Tests cover Unicode/root/nested/empty entries, full content equivalence across modes, pinned-index corruption, malformed header/table/string/range fields, stale/copied bundle identity, payload CRC rejection, local-header validation, and missing/corrupt directory files. **Thirty correctness tests pass** across Python and native paths. Measurements remain warm-cache/synthetic; native RSS, syscall counts, random/sparse access, pressure and real package startup were not measured. The next architectural question is how a real tool receives the input set and chooses named versus prebound-entry access, rather than assuming this scan becomes an end-to-end language speedup.

## Odin connected to Python and a real tool

Run `20261028T223649.522893Z` connects Odin to the existing CPython module/resource loader through [a small C-extension shim](native/python_shim.c), [a checked Odin C ABI](native/python_api.odin), and [a Python adapter](native_loader.py). Every module is compiled/unmarshaled/executed by the same CPython loader as before. Odin verifies/maps the sidecar and bundle, returns a catalog in bulk, and validates each requested payload CRC. The GIL-held shim copies that payload into an owned Python bytes object in-process. No per-entry IPC or native worker is involved. Correction discovered later: original pip provider setup occurred before its workload clock because a lazy host import triggered early opening; process totals include it, while the original pip workload phases do not. Synthetic phase timing is unaffected. The original report is annotated, and the worker's timing boundary is corrected in the resolution diagnostics below.

The library returns input failures as Python exceptions rather than exiting the interpreter. Explicit close and capsule destruction release mappings, descriptors and native allocations; returned bytes survive close. Index pinning, full-hash/local binding and per-read CRC are preserved. The extension is CPython/Linux-specific and holds the GIL; it is a tested bridge, not a frozen platform ABI or zero-copy compiler integration.

The representative workload uses the locally bundled **pip 26.2.1** wheel, SHA-256 **`71138adf1f4ca900cdb7d289c21b7494329f2332b6d85f0e1c42108c0384ed3e`**. Its 404 Python files, vendored dependencies, resources and license/metadata files are preserved. A fresh process invokes pip's CLI through `runpy` for offline `install --dry-run --ignore-installed --no-index --find-links ... --report ...`. Twenty-two generated wheels force resolver backtracking from A 2.0 to A 1.0, producing a known 12-package solution. The wheel graph is synthetic; pip's actual implementation is unmodified. No package is installed and an audit hook rejects network operations.

Pip executes **312 distinct controlled code files** in either mode and retains **310 unique module origins plus 32 aliases** afterward. All source/bytecode layouts agree on execution maps, module origins and aliases, selected versions, full normalized resolver-report hash, vendor resource hash and missing-module failure. All bundle providers open once and perform the same 312 code reads. Some executed code (including CLI main) is not represented as a retained module, so sys.modules size alone would miscount reads. Host standard library/native modules, normal distribution metadata/wheel access and any resource-to-path materialization remain on their usual paths and their costs are included.

There are **24 cases and 360 timed fresh interpreters**, 15 randomized trials per case plus warmups: synthetic/pip, source/bytecode, directory/ZIP-rebuilding/Python-index/Odin-index, with full-hash/local policies. [Full report](results/python-native/REPORT.md), raw samples (local artifact, `results/python-native/results.json`), [harness](python_native_benchmark.py), [reproduction](README.md).

Matched **process-wall medians**, ms, using full-bundle SHA-256 for both saved-index readers:

| Workload | Input | Directory | Python binary index | Odin binary index |
| --- | --- | ---: | ---: | ---: |
| Synthetic, 2,072 modules | Source | 364.416 | 251.278 | 244.388 |
| Synthetic, 2,072 modules | Bytecode | 225.695 | 170.637 | 168.067 |
| Offline pip resolution | Source | 920.262 | 922.463 | 914.174 |
| Offline pip resolution | Bytecode | 471.435 | 458.546 | 440.797 |

The synthetic source process improves **33% versus directory inputs**, but only **2.7% versus the Python binary reader**. Its timed import/resource/application workload falls from 140.297 to 132.975 ms against that Python control. The dramatic raw native-access ratios do not survive intact once Python compilation, import machinery, object construction and execution are included.

The real pip case shows **no compelling, consistent end-to-end advantage for Odin over the Python binary reader** in these observations. Source full-hash workload medians are 710.503 ms for Python and 720.773 ms for Odin; process medians differ by only 8.3 ms in the other direction. The bytecode/full-hash process favors Odin (458.546 → 440.797 ms), but local admission reverses that comparison (437.296 → 460.768 ms), and tail variation is large. Do not turn these isolated median differences into a general native speedup claim. Directory and bundled source cases are all roughly 0.9 seconds end to end here. Precompiled inputs make a much larger difference, but that changes representation/import behavior and is not a clean measurement of compilation alone.

The bridge exposes additional costs directly: Odin/local pip setup phases have medians of approximately 0.303 ms extension load, 0.180 ms native open and 0.159 ms Python catalog construction; these are separate phase medians, not a combined-sample estimate. The synthetic catalog phase is approximately 5.2 ms in its heavier harness, so Python metadata/object construction cannot be treated as free or replaced with the native-only ordinal benchmark. Full-hash verification of the larger pip bundle remains charged to the native open. Python still owns the module lookup structures; this is an actual integration result rather than an extrapolation from native scans.

All **34 tests pass**, including extension byte/resource equivalence, source/bytecode imports/origins, pinned/malformed-index Python exceptions, per-read CRC rejection, bytes surviving reader close, idempotent close, and repeated failed-open/GC cycles without descriptor leaks. Measurements remain Linux/CPython 3.14.8, warm-cache and workload-specific. This validates the in-process byte-provider boundary and supplies one real-tool result; it does not establish representative counts across the ecosystem, real-world dependency-graph performance, or a general language-loader speedup. Broader tool/compiler integration and protocols remain open.

## Resolution diagnostics

There are two meanings of resolution here: **module discovery** maps imported names to code locations, while **dependency-version resolution** selects a compatible package set. The real pip command already exercised the latter with backtracking; its timing was not isolated. Run `20261028T230639.248141Z` now separates discovery from code loading/execution and collects independent whole-CLI profiles. [Report](results/resolution/REPORT.md), raw data (local artifact, `results/resolution/results.json`), [harness](resolution_benchmark.py).

The unprofiled discovery test uses the **312 actual pip code files**, supplying explicit parent search paths so no parent packages need to be imported. It performs 312 successful queries and 312 distinct same-parent misses per scan, four scans per fresh process. It checks origins/package flags and proves no pip imports or per-module code fetches occurred. Bundle setup still includes index verification/module-table creation, and full-hash mode reads archive bytes for integrity. The one-to-one hit/miss mix is deliberately controlled, not a measured miss rate from pip. There are **12 cases and 180 randomized timing observations**, 15 per case.

Source discovery medians, ms:

| Provider | Setup | First 312 hits | First 312 misses | Setup + first hits |
| --- | ---: | ---: | ---: | ---: |
| Directory PathFinder/FileFinder | 0.002 | 6.096 | 1.988 | 6.097 |
| Python binary, local admission | 1.135 | 0.476 | 0.033 | 1.562 |
| Odin binary, local admission | 0.782 | 0.472 | 0.034 | 1.307 |
| Odin binary, whole-bundle hash | 5.078 | 0.625 | 0.044 | 5.843 |

Indexed discovery is already much faster than repeated directory probing, but **Python and Odin indexed readers share the same Python module-name map and spec construction**. Their successful discovery loops are nearly identical. The native accessor has not replaced that resolver. The remaining finder work on this corpus is a few milliseconds, not the hundreds of milliseconds seen in the full source command. This is a pure-discovery test: it bypasses ordinary sys.modules/parent-import behavior, and repeated scans measure finder caches rather than repeated Python import speed.

Six **separate instrumented CLI runs** (source/bytecode × directory/Python-local/Odin-local) retain matching selected versions, resolver-report hash, module origins and code/resource checks. Their source-compilation self time is roughly **447–473 ms**; bytecode runs record roughly **41–45 ms** in bytecode decoding. Import machinery/discovery self time is roughly 49–68 ms in source profiles, but includes spec/lock/loading bookkeeping and profiler overhead rather than pure path lookup. Disjoint self-time buckets and all per-function observations are retained; profile times must not replace or be added to unprofiled samples.

Pip's inclusive dependency-resolution phase is approximately **63–75 ms** across these profiles. It includes candidate/provider callbacks, wheel metadata and imports triggered during solving. Exclusive self time in resolvelib plus pip's resolver integration is approximately **5–6 ms**, not a measurement of the complete solving phase. Nested vendor resolver rows overlap; do not add them. This is still a small generated graph, not solver-scale or difficult-real-graph evidence. The earlier byte-provider work mainly optimized loading pip's implementation, not how pip reads candidate-wheel metadata or its constraint algorithm.

The diagnostic exposed a timing-boundary mistake: temporary-directory setup could lazily import a host module and cause the registered provider to open before the workload timer. The original pip process totals include this setup and remain valid; original pip workload columns exclude it. The worker now delays publishing both root and provider until after the timer starts and checks that the provider is unopened. The profiler is also imported before registration. The corrected profiles now include provider open/catalog/module-table work (about 1.5–2.0 ms inclusive for Odin-local and 5.9–6.2 ms for Python-local under profiling). The [superseded profile run](results/resolution-before-timing-fix/REPORT.md) and original observations are preserved, with correction notes. No corrected original process-matrix claim is inferred from these profiles.

All **36 correctness tests pass**, including discovery against deliberately invalid Python bodies (which must not be compiled/executed) and checks that self-time buckets partition profile time. These diagnostics establish where resolution is already covered and what remains untested: larger/realistic candidate graphs, metadata-access costs at scale, and any native module/dependency resolver implementation. They do not justify replacing a resolver algorithm from a full-command timing alone.

## Real Django application

Run `20261029T014251.176632Z` tests real, unmodified published wheels: Django **6.1.2**, asgiref **3.13.0**, sqlparse **0.6.0**, plus Django REST framework **3.18.3** and django-filter **26.2** in the extended case. [Report](results/django/REPORT.md), raw observations (local artifact, `results/django/results.json`), [pinned artifact provenance](results/django/provenance.json), [reproduction](README.md#real-django-application). There are **300 randomized timed fresh processes**, 15 per case, after one correctness warmup per case. The existing Odin extension is reused with its hash checked; no native rewrite is introduced.

The core input has **3 distributions, 3,739 files and 938 Python source files**, about **22.9 MiB unpacked**. The REST input has **5 distributions, 4,018 files and 1,026 Python source files**, about **25.7 MiB**. Actual common-adapter application paths import **392** and **455** dependency modules respectively; the stock filesystem template control imports two additional loader modules. A framework can therefore have substantial code and initialization while selecting very few packages. This is one specified app, not an ecosystem-wide import/dependency-size distribution.

The fixture initializes WSGI/admin/ORM, runs Django system checks, creates a two-row in-memory SQLite table, serves an actually filtered JSON query, then renders the admin login page and its form widgets. The REST path uses real DRF serialization/generic views and django-filter. Startup consumes a frozen selected package set; it does not run dependency resolution. Resource hashes, module origins/loaders, code executions, API results, admin output markers, versions, a single provider open and zero network attempts are validated. Code/import sets match across all byte readers and source/bytecode modes within each scenario.

### Startup measurements

Medians, ms. Ready includes framework/provider initialization and system checks. The complete process additionally includes common adapter preparation, database fixture creation, first API/admin responses, independent validation and cleanup. Producer extraction, compilation, packing and index admission are recorded separately.

| Scenario | Input | Reader | Ready | Complete process |
| --- | --- | --- | ---: | ---: |
| core | source | directory-stock | 845.520 | 1124.663 |
| core | source | directory | 825.357 | 1102.313 |
| core | source | zipfile | 892.943 | 1164.596 |
| core | source | python | 871.609 | 1141.058 |
| core | source | odin | 816.583 | 1099.235 |
| core | bytecode | directory-stock | 227.597 | 459.916 |
| core | bytecode | directory | 224.063 | 456.830 |
| core | bytecode | zipfile | 298.225 | 534.510 |
| core | bytecode | python | 233.551 | 466.098 |
| core | bytecode | odin | 230.219 | 462.682 |
| rest | source | directory-stock | 944.116 | 1235.688 |
| rest | source | directory | 941.540 | 1219.565 |
| rest | source | zipfile | 1011.654 | 1314.465 |
| rest | source | python | 921.557 | 1215.580 |
| rest | source | odin | 933.540 | 1221.509 |
| rest | bytecode | directory-stock | 250.889 | 502.109 |
| rest | bytecode | directory | 248.595 | 490.606 |
| rest | bytecode | zipfile | 343.545 | 605.698 |
| rest | bytecode | python | 264.933 | 524.495 |
| rest | bytecode | odin | 269.367 | 550.195 |

For REST with the common resource adapter, ordinary files reach ready in **941.5 ms from source** versus **248.6 ms from bytecode** (about **3.8x**). Complete process falls from **1,219.6 to 490.6 ms** (about **2.5x**). This source-to-bytecode comparison is ordinary precompilation, not an Odin or bundling speedup; normal installations can already use bytecode caches. Input layouts deliberately isolate source-only and matching-interpreter sourceless bytecode.

The REST bytecode bundle with the Python sidecar reaches ready in **264.9 ms**, and Odin in **269.4 ms**, versus **248.6 ms** for ordinary files with the same adapter. Full process is **524.5 ms Python**, **550.2 ms Odin**, and **490.6 ms ordinary files**. The ZIP-parsing reader reaches ready in **343.5 ms**. Avoiding repeated ZIP validation/index construction helps that control, but neither sidecar wins against warm ordinary bytecode files here.

There is **no consistent Odin-over-Python startup win** across scenarios/modes: core source favors Odin, core bytecode differs little, and REST slightly favors Python. All still execute module lookup/spec construction, compilation/bytecode decoding and framework initialization in CPython. Timings show that a larger real framework does not automatically make byte retrieval the dominant cost. They do not partition compilation/framework CPU or establish a native runtime floor.

### The filesystem compatibility boundary

Django template discovery normally uses filesystem app paths. Bundles need an explicit [template-loader adapter](django_fixture/template_loader.py) over `importlib.resources`. The ordinary-file common-adapter cases use the same loader, while `directory-stock` uses Django’s filesystem/app-directory loaders to expose adapter effects. Forms use the built-in TemplatesSetting renderer and the installed forms app in every case. Dependency source remains unchanged, and bundle consumers do not extract code/templates to fake directory paths. See [Django’s app path contract](https://docs.djangoproject.com/en/6.0/ref/applications/#django.apps.AppConfig.path).

This demonstrates one usable access boundary, not transparent compatibility with every filesystem API. I18N is disabled; static resources are hash-checked but not served. Migration discovery, localized catalogs, static collection/serving, autoreload, native wheels and arbitrary path consumers need separate tests or adapters. The database and routes are benchmark fixtures, not a production workload. Warm-cache results on the recorded execution environment say nothing about cold storage or a typical deployment.

### Separate dependency solving

The [real-wheel solver comparison](../dependency_solving/results/django/REPORT.md) retains three published candidate versions per project (15 wheels total). Fresh offline pip reports select the same artifact hashes as every reference-provider solve. Core selects three distributions; REST selects five. Catalog + trail brings REST **open plus first solve from 128.8 ms uncached / 52.8 ms wheel-cached to 3.6 ms**, and reused solve from **121.4 ms / 0.71 ms to 0.40 ms**. These are local metadata/constraint measurements, not framework startup or pip replacement speedups.

The REST first solve opens wheels **25 times uncached**, **14 times with wheel caching**, and **zero times with the catalog**. The large code/resource inventory makes metadata ZIP setup meaningful even though the version graph is shallow. That supports separating certified dependency metadata from payload bytes. The source-loading, solving and full-process medians remain distinct and must not be added across experiments.

All **36 existing loader/access correctness tests** and **15 solver tests** pass. The new 20-case Django smoke matrix and all 300 loading observations validate the real app paths; the separate 90-observation/270-solve matrix matches fresh pip artifact identities. No representative ecosystem-wide scaling or production filesystem compatibility claim is made.

## Native bridge diagnosis

Run `20261029T020824.661458Z` addresses whether the Django results indicate an ABI penalty or inefficient Odin code generation. It replays the exact **460 code reads** observed in the REST app, separately for source (**4.601 MiB**) and bytecode (**5.764 MiB**). Both reader implementations run in each of **30 fresh processes**, 15 per corpus, with randomized opening order and interleaved read blocks. Each of 11 blocks repeats the trace 16 times. Existing kernels/bridge code and the same native binary are unchanged. [Report](results/bridge/REPORT.md), raw observations (local artifact, `results/bridge/results.json`), [reproduction](README.md#real-django-application).

Both named APIs return owned Python bytes and retain payload CRC verification. Full payload equivalence is checked; timed loops additionally check a deterministic payload token. The common Python request/checksum loop is included in all scans. Reads are warm after validation/warmup, so they do not measure first-touch mapping faults or replace application startup timings. Separate constructor profiles add material overhead and are not used as subdivisions of unprofiled times.

Medians, ms:

| Input | Python reader open | Odin reader open | Python named scan | Odin named scan | Odin ordinal scan |
| --- | ---: | ---: | ---: | ---: | ---: |
| source | 8.472 | 3.671 | 2.370 | 2.056 | 1.938 |
| bytecode | 7.629 | 3.452 | 2.779 | 2.442 | 2.349 |

The existing Odin path is **already faster** at opening and at bridge-inclusive named reads. Bytecode open is about **2.2x faster**; the complete named read scan is about **1.14x faster**. This is not evidence that Python executes equivalent native work faster or that Odin has poor code generation. The Python reference delegates mapping, struct decoding, memory copying and CRC to compiled runtime libraries; both readers use system zlib for CRC. Most of the whole framework still executes through the same CPython loader/interpreter.

Bypassing the Python native-reader name/wrapper layer saves about **0.09 ms over 460 bytecode reads** in the ordinal diagnostic. That changes the request API and is not an ABI-only measurement: it leaves the CPython extension boundary, argument/capsule handling, Odin entry lookup, CRC and owned-byte construction in place. These results neither isolate pure ABI cost nor prove that it is zero.

Constructor profiles identify remaining native-path work primarily in Python catalog rebuilding: the C shim copies the name/directory pools, Python decodes/splits them, then builds NativeEntry objects and dictionaries. The current reader also initializes a default Odin context and decodes a validated entry on each exported read. Those are implementation choices worth measuring if optimized later; source inspection alone does not attribute the whole-application gap to them, and no such optimization is claimed here.

The original REST bytecode **application-workload** medians were **297.918 ms Python versus 297.538 ms Odin**; their complete-process medians were **524.495 versus 550.195 ms**. The application work is essentially tied at the resolution of this experiment, with broad sample variation; a difference in the outer process metric must not be attributed to the native read kernel. Readiness (a subset of that workload) had medians of 264.933/269.367 ms and also varied across samples. Independent medians cannot be subtracted to produce an exact phase decomposition.

The corrected conclusion is narrower: the native accessor wins the isolated read/open comparison, while that small affected component does not establish a measurable full-framework startup win. The diagnostics do not identify all remaining application/allocator/scheduling effects, benchmark a native interpreter, or establish an ABI/codegen bottleneck. The previous end-to-end table is a system comparison, not a Python-versus-Odin language benchmark.

## Remaining discovery and VFS work

Workload-scoped traces and separate execution profiles on the same bytecode REST app identify the next optimization target. Four controls retain identical app/import/code/resource checks; no native or production loader code is changed. [Report](results/django-diagnostics/REPORT.md), full counts/functions (local artifact, `results/django-diagnostics/results.json`), [reproduction](README.md#real-django-application). Instrumentation is bracketed around the unchanged worker workload; common wrapper/profiler imports can affect host import state. These are diagnostics, not new unprofiled speed results.

| Reader | All metadata calls | All opens | All reads | Dependency metadata | Dependency opens | Dependency reads | Host opens | Host reads |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| directory-stock | 3010 | 856 | 1450 | 2101 | 574 | 948 | 268 | 488 |
| directory | 3018 | 896 | 1464 | 2086 | 604 | 944 | 276 | 504 |
| python | 1030 | 289 | 515 | 113 | 3 | 7 | 270 | 492 |
| odin | 1029 | 290 | 514 | 111 | 3 | 5 | 270 | 492 |

Warm page cache does not eliminate path lookup, metadata calls, descriptor management or kernel transitions. The bundle payload reader already maps memory, however: there is no file syscall per payload read. First-touch mapping faults and one-time mapping work remain distinct from VFS pathname operations. Most residual opens/reads in the mapped case are for the unbundled host runtime/library, with project fixtures and the native extension attributed separately.

**First target: finish the index-backed module-discovery interface.** A stock zipimporter still reopens the already-indexed archive and parses its central directory; pkgutil then enumerates/scans that file table. The Odin profile records one `_read_directory` call (25.6 ms self, 64.6 ms inclusive) and 77 `iter_zipimport_modules` activations (17.1 ms self, 36.0 ms inclusive). Generator resumptions count as profiler activations; the later explicit counter establishes 18 distinct enumeration requests, not 77 full scans. These instrumented values overlap at inclusive scope and are not predicted savings. The duplicated work is a concrete mechanism that can mask the benefit of the faster reader.

The next controlled implementation should supply an index-backed path-entry finder with `find_spec`/`iter_modules`, direct-child enumeration and authoritative misses for its owned immutable package paths. This prevents stock zipimport fallback and repeated whole-table scans while preserving normal host behavior elsewhere. Initially, derive package/child information once from the existing module index rather than changing the archive format. Verify exact imports/outputs and absence of stock ZIP-directory reparsing before measuring uninstrumented startup. A direct-child resource table would also replace BundlePath.iterdir’s whole-entry scan, although that method was not the dominant enumeration cost in this profile.

**Second target: the remaining pure-Python stdlib loading path.** The mapped controls still make 270 host-runtime/library opens and 492 reads inside the app workload, excluding common worker setup. Host inputs include sources/bytecode, shared libraries and native modules. A closure-specific bootstrap bundle for pure-Python stdlib inputs is a separate experiment; retain native-extension loader behavior and source/introspection compatibility. Do not assume every host call can disappear.

**Third target: reduce repeated Python materialization and initialization.** The native sidecar still reconstructs full Python name/entry/module dictionaries; opaque entry IDs and lazy names/child tables can reduce that work. But the profile also records 578 marshal.loads calls and 2,034 class constructions. Byte retrieval cannot remove code-object allocation or framework initialization. Persistent project/tool workers and code-object reuse are the larger follow-up for repeated development actions; cold-process gains must be measured separately.

The recommended next experiment is module/package enumeration through the existing index, not another CRC/copy micro-optimization. No discovery fix, stdlib bundle, persistent worker or end-to-end speedup is implemented or claimed by this diagnostic. Raw traces/profile files remain in ignored `_work/`; parsed counts and function records are retained. Descriptor-based fstat is explicitly traced. Strace durations and profiler self times are not hardware-cycle estimates or partitions of earlier unprofiled medians.

## Index-backed discovery follow-up

Run `20261029T025706.004897Z` implements the previously identified discovery fix as [IndexedPathProvider](indexed_path_loader.py), a thin path-entry adapter over the existing admitted module map. It reuses the exact Django REST source/bytecode archives, sidecar pins, native extension and app fixture from the parent run. **150 randomized timed fresh processes**, 15 per case, compare the current legacy control with indexed discovery and an ordinary-file baseline. [Report](results/path-index/REPORT.md), raw observations (local artifact, `results/path-index/results.json`), [reproduction](README.md#index-backed-package-discovery).

The new finder serves regular-package lookup, direct-child enumeration and owned-path misses without stock ZIP fallback. It derives child tables once in memory without changing the archive/index encoding. Other paths retain normal import hooks. Mounting is lazy, and close removes owned hooks/cache entries and restores prior importers when possible. The payload byte readers, native ABI, CRC and local-admission checks are unchanged.

Correctness warmups forbid `_read_directory` for the owned archive. The legacy negative control must fail that same guard, proving it detects the original problem. Timed observations omit the guard and must match the parent module origins, execution sets, app count, resource hashes and API output. All retain **455 dependency modules and 460 code reads**.

Matched medians, ms:

| Input | Reader | Discovery | Ready | Workload | Complete process |
| --- | --- | --- | ---: | ---: | ---: |
| source | directory | legacy | 1187.520 | 1254.174 | 1595.055 |
| source | python | legacy | 1188.759 | 1245.507 | 1641.349 |
| source | python | index | 1146.122 | 1207.105 | 1602.318 |
| source | odin | legacy | 1179.520 | 1243.508 | 1598.331 |
| source | odin | index | 1153.583 | 1210.021 | 1596.510 |
| bytecode | directory | legacy | 331.118 | 363.389 | 703.504 |
| bytecode | python | legacy | 341.122 | 381.115 | 722.563 |
| bytecode | python | index | 313.897 | 345.251 | 695.682 |
| bytecode | odin | legacy | 339.421 | 370.765 | 716.333 |
| bytecode | odin | index | 304.682 | 333.559 | 663.651 |

Odin/bytecode readiness improves from **339.421 to 304.682 ms** (about **10.2% less time**), its application workload from **370.765 to 333.559 ms**, and its complete process from **716.333 to 663.651 ms** (about **7.4% less time**). It also beats this run’s ordinary-bytecode baseline (331.118 ms ready / 703.504 ms process). Python/bytecode improves from **341.122 to 313.897 ms ready** and **722.563 to 695.682 ms process**.

Source-mode readiness improves modestly, but Odin’s source complete-process median is effectively unchanged (1598.331 versus 1596.510 ms). The dominant source-mode work is outside this discovery change. These are matched controls in a new run; do not mix them with the older, faster absolute startup values recorded under different execution-environment conditions. Complete-process and phase medians are independent and cannot be subtracted to infer exact components.

### Mechanism confirmed separately

The [separate traces/profiles](results/path-index/diagnostics/REPORT.md) preserve identical app imports/outputs. On the Odin path, dependency-input metadata calls fall from **111 to 12**, opens from **3 to 2**, and read/pread calls from **5 to zero**. The remaining two opens map the sidecar and archive; metadata/path work is not universally zero. Host runtime/library opens/reads remain **270 / 492**, exactly as in the matched legacy control.

The indexed profile has **zero `_read_directory` and zero `iter_zipimport_modules` activations**. The new child-table iterator handles **18 distinct enumeration requests**. Its generator still has 77 profiler activations because resuming a generator is counted; those are not 77 complete scans. The older diagnosis’s “77 enumeration passes” interpretation was incorrect, while the duplicated ZIP parsing and whole-table enumeration were real. Native byte access itself is unchanged; completing the consumer’s discovery interface produces the measured improvement.

All **42 loader/access tests pass**, including six new tests for source/bytecode enumeration equivalence, no payload reads during discovery, no filesystem probes for indexed lookup/misses, recursive package walking, outside-path behavior, lazy/idempotent installation, cache restoration, overlapping mounts and failure cleanup. Namespace packages, native wheels and arbitrary mutable package paths remain outside this prototype; the archive describes an immutable snapshot.

The next remaining targets are the unbundled pure-Python stdlib path, avoiding repeated Python catalog construction, and runtime reuse for bytecode/framework initialization. This follow-up implements package discovery only; it makes no claims for those later changes. Trace/profile timings are diagnostic and are not substituted for the uninstrumented startup observations.

## What remains in host I/O

The indexed Django trace’s 270 host opens / 492 reads break down into **118 bytecode opens / 236 reads**, **118 matching source opens / 234 reads**, **22 native-extension/shared-library opens / 22 reads**, and **12 directory opens** (plus 24 getdents64 enumeration calls). Returned read bytes total **5.01 MiB**. All 118 bytecode caches use checked-hash flags=3; their source hashes match, so full source reads validate current bytecode rather than triggering recompilation. This is an interpreter-installation cache-policy detail, not a universal Python requirement. [Exact breakdown and mechanism](results/path-index/diagnostics/HOST_IO.md), [per-path records](results/path-index/diagnostics/host-io.json). An admitted immutable stdlib/bootstrap bundle is the next candidate; no validation policy is globally disabled here.

## Admitted stdlib snapshot

The [snapshot experiment](results/stdlib/REPORT.md) implements that candidate for the observed **118-module application-phase stdlib closure**. The producer verifies checked-hash bytecode against source once, binds the exact interpreter/build/platform/optimization identity, retains both source and code, and relocates code filenames to stable snapshot URIs. Consumers mount an explicit module table; normal native-extension loaders and unbundled module/data fallbacks remain. This changes admission policy for one immutable environment, without changing Python’s global cache-validation settings.

In run `20261029T034650.363732Z`, 15 randomized fresh processes per provider use the same Django REST bytecode/dependency bundle, native reader and indexed discovery. All providers perform the same post-workload module/function/class source-inspection checks. Medians:

| Stdlib provider | Ready ms | Workload ms | Full process ms |
| --- | ---: | ---: | ---: |
| Installed host | 496.714 | 541.979 | 992.417 |
| Admitted directory | 467.106 | 521.401 | 967.432 |
| Python mapped bundle | 477.123 | 526.906 | 997.983 |
| Odin mapped bundle | 464.270 | 516.196 | 976.361 |

Odin readiness improves **6.5%**, workload **4.8%**, and full process **1.6%** by these medians. Broad overlapping readiness ranges (host 367–555 ms; Odin 372–495 ms) limit confidence in the ranking and precise gain. Do not compare absolute values with prior runs. The directory snapshot is essentially tied with Odin here: fewer syscalls do not establish a further end-to-end mapped-reader advantage. Admission/packing/index construction costs **441 ms** separately and stores source as well as bytecode.

The [matched workload traces](results/stdlib/diagnostics/REPORT.md) give stronger evidence for the mechanism. Host → Odin totals are **930 → 219 metadata calls**, **289 → 44 opens**, and **509 → 41 reads**. The host’s **118 pyc opens/236 reads** and **118 source opens/234 reads** both become zero. The directory snapshot still opens 119 manifest/code files and performs 238 reads; the mapped snapshot/index uses two opens and no read syscalls in Odin (Python uses two reads). The descriptor, native shared libraries, directories, project and dependency activity remain in the totals. Mapping still requires pages and CRC, marshal decoding still creates code objects, and Python/framework execution remains.

All 60 timed applications preserve dependency execution/origin sets, resources and responses; every snapshot observation loads all 118 modules with zero startup source reads. **47 loader/access tests pass**, including admission rejection for stale source or interpreter identity, unchanged admitted behavior after host-source mutation, source inspection, native/unbundled-child/data fallbacks, and no host probes for bundled lookup. Earliest interpreter/common harness imports are outside this snapshot, and broader stdlib resource/process/debugger compatibility remains untested. These results support admission plus indexed loading as a useful interface; they do not establish that VFS removal alone dominates this application’s startup.

## Mapped bytecode handoff

The [handoff experiment](results/handoff/REPORT.md) tests the remaining intermediate byte copies with unchanged archive/index inputs and the same newly built bridge for all cases. The bytes control copies an entry into Python bytes and slices off its header. The view variant retains the entry copy and replaces the body slice with a memoryview. The native variant checks CRC, bytecode magic/flags and optional admitted source hash, then calls CPython's marshal API on the mapped range. Code-object allocation/decoding remains. This fuses header checks as well as avoiding intermediate copies, so it does not isolate copying alone.

CPython's direct API emits `marshal.loads` itself. Without audit hooks, the mapped path avoids intermediate payload bytes. With hooks, CPython creates an owned audit payload; our application has a hook, and the timings include it. The GIL remains held, no borrowed mapped pointer escapes, and unmapping is deferred if an audit callback or finalizer closes the reader during decoding. Source/resource reads retain their existing path.

Run `20261029T035745.805340Z` has **90 timed fresh processes**, 15 per mode per workload, after correctness warmups:

| Handoff | Decode 578 objects ms | App ready ms | App workload ms | App process ms |
| --- | ---: | ---: | ---: | ---: |
| Bytes + slice | 129.778 | 460.488 | 513.238 | 982.167 |
| Bytes + body view | 131.638 | 474.811 | 523.329 | 988.263 |
| Direct native | 123.606 | 453.456 | 498.628 | 954.690 |

Direct-native reductions of medians are **4.76% decode**, **1.53% readiness**, **2.85% workload**, and **2.80% full process**. The native path wins decode/readiness in only **9/15 trial blocks**, and workload/process in 11/15; ranges overlap broadly. These are tentative improvements, without evidence of a stable ranking. The slice-only view variant does not help by these medians. Bytes remains the default; direct native is opt-in.

The isolated diagnostic opens readers before timing, decodes the application's first-seen ordered dependency multiset followed by manifest-ordered stdlib, retains the 578 code objects without executing them, and checks equality/filenames against the bytes control after closing the timed readers. Its full process includes that reference decode and is not a decoding-only metric. Actual application counters confirm **460 dependency + 118 stdlib loads** through every selected handoff, with unchanged origins/execution sets, resources, responses, source inspection and no network activity. **49 loader/access tests pass**, including malformed headers/body/type, CRC/hash rejection, owned code after close, retained audit payloads, audit rejection, and reentrant close. Catalog/table reconstruction and code-object initialization remain more useful next candidates than assuming removed byte copies unlock a large startup gain.

## Precomputed catalog scaling

The [catalog experiment](results/catalog/REPORT.md) compares normal native name export/Python entry allocation/provider indexing against two producer-derived alternatives: a pinned name-to-row map with lazy entry wrappers, and that map plus precomputed module/package/discovery tables. The same native binary, original archive/range index, CRC policy and bytes+slice bytecode handoff apply to every mode. Django changes only its dependency catalog; stdlib loading stays fixed. Derived metadata binds the original index SHA-256 and interpreter identity, with its own SHA-256 pin and experimental version. Python marshal is a local acceleration format here, not a proposed portable protocol.

Run `20261029T040556.156420Z` contains **180 randomized fresh-process observations**, 15 per workload/mode. Each synthetic archive expands its flat package while importing the same 32 leaves plus initializer. This is a scaling fixture, not an assertion about normal application module counts.

| Available leaves | Rebuilt setup ms | Rows-only setup ms | Precomputed-table setup ms | Rebuilt → table process ms |
| --- | ---: | ---: | ---: | ---: |
| 1,024 | 10.310 | 11.218 | 11.174 | 198.416 → 187.244 |
| 16,384 | 50.545 | 55.565 | 40.881 | 246.268 → 235.637 |
| 131,072 | 470.236 | 517.307 | 314.022 | 751.775 → 560.847 |

At 131,072 leaves, tables cut setup **33.2%** and full process **25.4%**, winning both in **15/15 trial blocks**. At 16,384, setup falls **19.1%** with 14/15 wins. The smallest fixture has no setup improvement. Django likewise has no startup win: readiness medians are **465.475 / 477.844 / 488.013 ms** for rebuilt/rows/tables; full-process medians are **971.434 / 969.691 / 998.279 ms**, with broad overlapping ranges. The table path wins Django readiness in only 4/15 blocks. Rebuilt remains the default.

Table adoption creates **zero entry wrappers**, versus 4,018 for Django and 131,074 in the largest fixture. Rows-only eventually materializes all wrappers because the unchanged provider requires infolist to derive its tables; lazy allocation alone does not avoid the work. Precomputed tables remove that pass but still deserialize all dictionaries/strings. At the largest size, the per-observation provider/install remainder falls from about **289 ms to 0.14 ms**, while catalog export/allocation is replaced by about **286 ms** of catalog reading/hashing/unmarshalling. Odin's original index validation/native name-buffer construction still costs about **27 ms**. Setup remains linear in available metadata size.

The largest table artifact adds **12.50 MiB**, takes **1.50 s** to produce including validation, and raises median full-process peak RSS **100.14 → 104.56 MiB**. Its original archive/index preparation is separately recorded. Django's table artifact is 393,133 bytes with 37 ms production cost. Catalog conversion/storage are outside consumer timing; consumer file reads, hashes, decode and adoption are included. Peak RSS includes common bootstrap/validation rather than isolating metadata memory.

All application outputs, origins/execution sets, resources, source inspection and no-network checks pass. Fixed import counts, owned misses and discovery/resource boundaries also pass at every scale. **52 loader/access tests pass**, including table/resource/discovery equivalence, no reconstruction when adopting tables, digest/index/runtime/version/mode binding, mixed-module rejection and failed-open cleanup. The next useful test is direct/lazy lookup in the admitted index, so importing a small closure need not reconstruct the entire catalog as Python objects. Native validation and integrity policy remain separate costs to preserve and measure.

## Native catalog and bounded allocation

The [native bounded catalog experiment](results/native-catalog/REPORT.md) keeps metadata in Odin. Strings reference the existing mapped binary index. One fixed-capacity mmap arena holds directory views/name offsets, native file/module/directory hash slots, and file/module child links/counts. Lazy Python adapters perform lookup/enumeration without exporting or deserializing the full catalog. The same payload reader, bytecode handoff, integrity policy and existing artifacts apply across rebuilt, precomputed Python tables and native cases. No extra native-catalog artifact is produced.

Run `20261029T042442.112831Z` contains **180 randomized fresh-process observations**, 15 per workload/mode, after correctness warmups. Fixed-import cases still execute the same 32 leaves and package initializer:

| Available leaves | Rebuilt setup ms | Python-table setup ms | Native setup ms | Rebuilt → native process ms |
| --- | ---: | ---: | ---: | ---: |
| 1,024 | 8.626 | 8.748 | 1.367 | 195.196 → 169.928 |
| 16,384 | 51.873 | 37.649 | 14.813 | 248.898 → 196.982 |
| 131,072 | 436.960 | 301.811 | 146.098 | 718.886 → 315.932 |

At the largest size, native reduces setup **66.6%** versus reconstruction and **51.6%** versus precomputed Python tables. Full process falls **56.1%** versus reconstruction. Native wins setup in **15/15 blocks at every synthetic size**, and process in 15/15 at both larger sizes (12/15 at 1,024). At 131,072, setup ranges are 355–535 ms rebuilt, 245–412 ms Python tables and 116–177 ms native. Python catalog materialization is therefore a meaningful scaling cost, independent of how many modules execute.

Median peak RSS at the largest size falls **100.33 → 37.98 MiB** (Python tables: 104.70 MiB). Its arena uses **11,534,512 bytes / 11.000 MiB** of the explicit **16 MiB** capacity. The fixed Odin handle is 648 bytes outside the arena. Arena usage is constant across lookups; the scaling worker records exactly **99 module queries and 99 returned member names at every available-module count**, with zero entry wrappers. Returned-name counters measure API results rather than all intermediate Python allocations. Enumeration creates Python results for the children actually requested, while resource directory filtering stays native before matching names are decoded.

Django still shows no readiness improvement: rebuilt/Python-table/native medians are **452.871 / 447.680 / 472.598 ms**, with full processes **919.021 / 909.006 / 960.775 ms**. Native wins readiness in 7/15 blocks and process in 8/15, with broad overlapping ranges. Dependency metadata occupies only **420,960 bytes / 0.401 MiB** in its native arena; app/framework work and consumer query overhead remain. Its stdlib reader is held fixed, and all dependency origins/executions, resources, responses, source inspection and network checks match. Rebuilt remains the default.

Native total setup is still linear: it hashes/scans the whole original index and constructs native hash/child tables. At the largest size, native open takes about **145 ms**, while Python adapter construction is about **0.08 ms**. This moves the dominant metadata work into native admission/construction; it does not establish a constant-time mount. A producer-built native lookup layout or amortized admitted handles would be separate next experiments, with integrity and lifetime checks measured explicitly.

The budget covers variable-size persistent native metadata, not total memory: mapped input pages, page rounding, fixed handles/shim, temporary path/hash/OpenSSL work and CPython allocations are outside it. An insufficient budget raises `MemoryError` without growing it; this prototype does not fall back to another structure. Close releases arena and input mappings, deferred during an active native decoder. Existing magic/flags/hash/CRC checks remain, and native admission rejects duplicate canonical modules. **55 loader/access tests pass**, followed by focused tests after the native loop optimization, covering source/bytecode behavior, Unicode/resources/discovery, no bulk export or host probes, malformed inputs, ambiguity, exact/insufficient budgets, constant arena usage under lookups, cleanup and safe code execution after a reentrant close. These results support native metadata ownership and a bounded allocation interface while leaving broader package/runtime compatibility outside this fixture.

## Directly mapped producer-built lookup tables

The [mapped catalog experiment](results/mapped-catalog/REPORT.md) moves native hash/child table construction into production. Its experimental v1 file contains a fixed-width, little-endian header, original-index SHA binding, directory offset/length records, name offsets and hash/child arrays. It serializes no pointers or native strings. Consumers map the integer arrays read-only; only directory string-view descriptors are created in the bounded mutable arena. Current zero-copy array views target Linux amd64. The artifact is a local research format, not a standardized protocol.

The producer builds the existing native catalog and exhaustively checks file/ordinal, module/member and directory bindings against the admitted original index before exporting the integer tables. Lookup semantics are trusted pinned producer-derived data, matching the earlier precomputed-table admission model. Consumers still hash both metadata inputs, check their binding, validate structural table domains/counts and original ranges/UTF-8/name offsets, retain archive identity/full-hash policy, and check payload CRC per read. They do not reconstruct every file/module hash placement to prove its semantics again. Hash probes and child iteration are bounded, and malformed structural inputs fail safely.

Run `20261029T123751.173467Z` has **180 randomized fresh-process observations**, 15 per workload/mode, with identical retained inputs, new bridge, bytes+slice handoff and reconstructed stdlib reader. Fixed-import scaling continues to load only 33 modules:

| Available leaves | Rebuilt setup ms | Runtime-native setup ms | Mapped setup ms | Native → mapped process ms |
| --- | ---: | ---: | ---: | ---: |
| 1,024 | 7.856 | 1.270 | 0.947 | 149.822 → 155.466 |
| 16,384 | 41.408 | 12.315 | 4.105 | 171.338 → 160.074 |
| 131,072 | 397.880 | 124.709 | 24.787 | 278.717 → 177.334 |

Mapped setup wins **15/15 blocks at every synthetic size**. At 131,072, setup improves **80.1%** versus runtime-native construction and **93.8%** versus Python reconstruction. Full process improves **36.4%** versus runtime-native (15/15 blocks), and **72.5%** versus Python reconstruction. The smallest case shows no full-process improvement despite its setup savings; process/harness costs and variability matter. Peak RSS at the largest size stays about **38.04 MiB** in both native modes, versus 100.32 MiB rebuilt: read-only mapped table pages replace the private arena arrays rather than eliminating resident metadata.

Integrity work is explicitly included and separately measured. At 131,072, runtime-native open spends median **6.397 ms integrity / 4.186 ms structural setup / 113.190 ms construction**; mapped open spends **18.719 / 5.120 / 0 ms** respectively. Mapped integrity costs more because it hashes an additional lookup artifact. Total native-open medians are **124.076 → 24.163 ms**. The clocks preserve that cost rather than moving verification out of startup. Mount remains linear in bytes/entries through hashing and structural validation; the dominant measured remaining cost is integrity verification.

The largest lookup artifact adds **11,534,768 bytes (11.00 MiB)** and takes **787.505 ms** to produce/certify, outside consumer timing. Mapped mutable metadata uses **32 bytes** in all flat-package scaling cases, plus an 840-byte fixed Odin handle outside the logical arena; the read-only tables still occupy mapped memory. Python counters remain **99 module queries / 99 returned member names** at every synthetic size, with no entry wrappers. Allocation budgets, mapping lifetime and deferred close under native decoding remain enforced.

Django remains neutral: rebuilt/native/mapped readiness medians are **375.685 / 382.140 / 381.362 ms**, with full processes **752.437 / 754.565 / 755.130 ms**. Mapped wins readiness in 8/15 blocks and process in 7/15, so there is no demonstrated application-startup win. Its lookup artifact is 421,216 bytes with 24.571 ms producer cost; mutable descriptors use 42,640 bytes. Compare these cases within this run, not against earlier absolute timings.

**60 loader/access tests pass**, including inherited source/bytecode/resource/enumeration/lifetime checks plus mismatched pins/bindings, rehashed bad headers/counts/offsets/row references, truncation, bounded child-cycle rejection, exact/insufficient descriptor budgets and failure cleanup. All timed application outputs/origins/executions/source inspection/no-network checks and fixed-import scaling checks pass. These results strengthen the case for producer-admitted, directly mapped metadata when the available input set greatly exceeds the working set. A real industry-tool workload is the next separate validation step; it is not included here. Rebuilt remains the default.

## Unified and compact metadata

The [compact/unified experiment](results/unified-catalog/REPORT.md) compares the two-file mapped format with a wide unified control and a compact unified representation. The wide control embeds the original range index and preserves sparse 64-bit lookup tables. Compact uses 32-bit eligible offsets/ordinals/counts, independently sizes file and module hash tables, and permits up to 75% occupancy; it falls back to the wide format for references that do not fit. Both are experimental unified v1, with explicit scalar widths and no serialized pointers. Runtime adapters read both widths directly without widening into arena allocations.

The envelope SHA authenticates the embedded range-index bytes and lookup tables together. Original-index SHA in its header is producer-certified lineage, checked against the requested input rather than separately rehashed. The old separate index is not opened. This changes the authentication unit while retaining authenticated coverage, trusted producer lookup semantics, structural/range/UTF-8/table-domain/count checks, archive identity/full-hash policy and payload CRC. Standalone-index tests confirm identical embedded bytes and successful operation with the original separate index absent.

Run `20261029T131301.330434Z` contains **180 randomized fresh-process observations**, 15 per workload/mode. The same 33 modules execute in every scaling case:

| Available leaves | Two-file mapped setup ms | Wide unified setup ms | Compact setup ms | Mapped → compact process ms |
| --- | ---: | ---: | ---: | ---: |
| 1,024 | 0.874 | 0.865 | 0.842 | 154.617 → 157.995 |
| 16,384 | 4.139 | 4.303 | 2.953 | 155.737 → 161.079 |
| 131,072 | 26.124 | 29.028 | 16.583 | 184.285 → 173.848 |

At the largest size, compact metadata shrinks **17,302,167 → 9,437,760 bytes (16.50 → 9.00 MiB; 45.5%)**, setup improves **36.5%** with **15/15 block wins**, and peak RSS falls **38.00 → 30.48 MiB**. Setup ranges are 24.11–35.43 ms mapped versus 14.90–21.39 ms compact. At 16,384, setup improves 28.6% with 14/15 wins. Full-process savings are much smaller: the largest median improves 5.7%, winning only 10/15 blocks, while the smaller cases show no process improvement. Common runtime/harness initialization limits how much these metadata savings affect complete commands.

Integrity time at the largest size falls **19.969 → 10.772 ms**, while structural/setup time falls **5.144 → 4.407 ms**. The wide unified control hashes nearly the same number of bytes and does not improve setup: its integrity clock is 19.481 ms and structural/setup clock 8.604 ms. This implementation demonstrates a benefit from representation size/density, not from merely combining files. Mutable directory descriptors remain 32 bytes in the flat-package scaling cases; the fixed native handle is 1,008 bytes outside the arena, and mapped pages are included in process RSS.

Django remains neutral: mapped/wide/compact readiness medians are **368.766 / 361.896 / 374.612 ms**, with full-process medians **722.688 / 718.934 / 736.301 ms** and broad overlapping ranges. Compact wins readiness/process in only 6/15 blocks. Its metadata shrinks 686,150 → 434,712 bytes, but this does not establish application startup gains. Compare cases within this run rather than earlier absolute timings.

Additional compact conversion/certification costs **2.074 s** for the largest input and 77.961 ms for Django; the wide conversion costs 232.275 ms and 14.904 ms respectively. Those costs are outside consumer timing and come on top of the retained source-artifact production. The current compact producer rehashes metadata in Python; producer implementation speed is not an end-to-end startup result. No source archive payloads change, and no industry-tool workload is added here.

**70 loader/access tests pass**, covering both widths, source/bytecode/resources/enumeration and decoder lifetime, original-index-independent operation, full-hash archive policy, malformed/rehashed header/count/capacity/offset/reference data, bounded child-cycle rejection, exact/insufficient budgets, failure cleanup and 64-bit fallback selection. All 180 timed observations preserve application results, source inspection, origins/execution sets and fixed-import counters. Native mounting still hashes/scans all metadata, with integrity work the largest remaining setup component. Rebuilt remains the default.

## Whole-process lifecycle characterization

Run `20261029T133339.555478Z`: **300 randomized fresh-process observations**, 15 per workload/mode across five workloads and four modes, plus separate profiles and compilation/import audits. All application correctness checks pass. The six runtime source hashes and retained native binary pin were rechecked. See the [full report](results/process-characterization/REPORT.md), raw results (local artifact, `results/process-characterization/results.json`), phase profiles (local artifact, `results/process-characterization/profiles.json`), and [bootstrap diagnostics](results/process-characterization/diagnostics.json).

In this matched run the 131,072-leaf compact command takes 57.485 ms without instrumentation. Its observed workload is only 6.983 ms; common imports take 28.707 ms and the late tail 8.018 ms. The empty baseline is 7.167 ms. Much of the remaining command cost belongs to runtime/consumer bootstrap rather than archive access. Parent CPU stays below 1 ms, and child CPU nearly matches wall time: these warm-cache results point to CPU/object work rather than storage waiting.

Django takes 238.189 ms baseline and 242.143 ms observed. Its observed workload takes 130.792 ms, with readiness at 117.993 ms relative to framework bootstrap (excluding earlier consumer preparation). Validation/output/explicit close through main return costs 2.954 ms despite about 63 KB of output. Its late tail is 61.093 ms wall / 60.509 ms CPU. The fast-exit control takes 185.592 ms, 56.552 ms below observed normal exit, winning all 15 blocks. This establishes substantial finalization cost without identifying every object responsible. Skipping arbitrary finalizers does not preserve normal Python lifetime semantics.

GC batching advances Django readiness from 117.993 to 105.052 ms, but full process time worsens from 242.143 to 245.063 ms (only 5/15 block wins). Recorded collections fall from 52 to one, while their total duration rises from 13.023 to 22.124 ms. This shifts work past readiness rather than reducing whole-process cost. The deferred full collection is included in timing.

Separate profiles locate substantial bytecode/code-object and class construction: Django initialization records 28.76 ms marshal.loads self-time across 482 calls and 13.38 ms build_class across 1,790 calls. These profiled numbers are not unprofiled phase costs or independent pure-decoding floors; triggered GC can also be charged inside a profiled operation.

Next tests, in order: (1) a thin, precompiled consumer bootstrap that imports only its selected adapter, measured against the same application and correctness checks; (2) attribute teardown through isolated object/lifetime controls; (3) test immutable initialized-state or worker reuse keyed by the admitted environment, explicitly measuring creation, memory, isolation and invalidation. Native arenas already avoid bulk Python catalog objects; moving arbitrary Python classes/code into an arena is not supported by the current interpreter contract. No reuse or bootstrap speedup is claimed here. Absolute timings shifted from earlier runs despite retained inputs/binary; use within-run comparisons only.

## Generic consumer bootstrap

The [generic bootstrap comparison](results/bootstrap/REPORT.md), run `20261029T153136.058419Z`, contains **315 randomized fresh-process observations**: three workloads, seven modes, 15 blocks. It holds dependency/framework/application code, compact metadata/archive inputs, native binary, bytes+slice code handoff, admission/payload checks and normal interpreter exit fixed. Refactoring and bytecode generation occur in isolated consumer snapshots; existing defaults are unchanged. The exact diff and launch sources remain in the recorded work directory.

The thin variant separates reader-independent resources from ZIP access, loads comparison adapters and ZIP error/default paths only when needed, and imports argparse only for CLI launch. The older all-layout worker adds its sibling import path before executing adapters, preserving dynamic-file loading after that split. Producer-compiled variants use ordinary interpreter-specific sourceless `.pyc` files. Programmatic launch supplies exactly the original parser's typed arguments from an admitted, compiled configuration; it uses a fresh interpreter and initializes the application normally.

| Workload | Unchanged source process ms | Thin/precompiled CLI ms | Thin/precompiled programmatic ms |
| --- | ---: | ---: | ---: |
| 1,024 available leaves, 33 imports | 90.700 | 77.018 | 62.668 |
| 131,072 available leaves, 33 imports | 102.523 | 84.186 | 74.843 |
| Django | 503.973 | 456.064 | 454.046 |

For both fixed-import catalog workloads, programmatic launch wins **15/15 blocks** versus source control, with paired median savings **26.044 / 25.490 ms** respectively. Its additional savings over thin/precompiled CLI are 10.214 ms (14/15 wins) and 13.475 ms (12/15 wins). Precompilation alone saves paired medians 7.001 / 9.465 ms; the incremental thin/precompiled change versus unchanged bytecode saves 3.909 / 5.122 ms with 11/15 wins each. Thin imports move some initialization into the workload clock, so phase-only comparisons would undercount their cost. Full process includes that work.

Django has broad variability. In the main run, thin/precompiled CLI saves a paired median 48.433 ms versus source with 11/15 wins, but adding programmatic launch has a paired median **regression of 10.428 ms** with only 5/15 wins. Bootstrap alone falls from 56.768 to 37.255 to 24.241 ms across these three modes; that does not prove matching complete-process savings.

The [focused confirmation](results/bootstrap-confirmation/REPORT.md), run `20261029T153402.608893Z`, therefore compares only those three Django launch modes for **30 additional randomized blocks / 90 fresh processes**. Source/thin-CLI/programmatic process medians are **470.638 / 453.907 / 452.965 ms**. Thin CLI saves 3.6% by medians and 16.715 ms by paired median, winning **23/30 blocks**. Programmatic launch saves 22.942 ms paired versus source (22/30 wins), but its incremental improvement over thin CLI is uncertain: medians differ by only 0.942 ms, paired median saves 8.216 ms and it wins 19/30 blocks. Source/thin/programmatic ranges are 429.6–872.1 / 411.0–996.8 / 416.7–781.9 ms. This supports a modest bootstrap gain, not a large general Django startup claim. Worker RSS falls from about 66.17 to 64.90 / 64.72 MiB.

The untimed compile audit records **10** top-level consumer source compilations in source control, including the worker, and **zero** in all three audited bytecode modes; application fixture/dynamic compilation remains. Every timed Django observation retains **460 dependency and 118 stdlib code reads**, exact dependency execution/origin and stdlib origin sets, API/admin outputs, resource hashes and source inspection. All **405 timed observations** pass validation. The refactored source passes **70 existing tests**, covering older layouts, resources, corruption/admission rejection, bounds/budgets and decoder lifetimes. The [test log](results/bootstrap/regression-tests.txt) is retained, and tested runtime files match the timed source snapshot. All recorded source/bytecode/fixture/native hashes were verified after measurement.

Generic GC threshold experiments multiply generation-zero thresholds by four or sixteen, leaving GC enabled and normal shutdown intact. Relative to programmatic control, Django paired median changes are **+10.407 ms** (7/15 wins) and **−5.523 ms** (10/15 wins). Catalog results also lack a consistent improvement. These do not establish a policy worth adopting. Separate profiles show fewer collections can still cost more total collection time; they do not turn this into a measured global GC win.

Snapshot generation/compilation for all four comparison directories costs 0.546 s. Parser-based configuration admission plus launcher compilation costs 0.173 / 0.121 / 0.105 s for small/large/Django launches, outside consumer clocks. These are prototype producer costs, not minimum required build times. Launch configurations must be regenerated when arguments, consumer code or runtime change. No initialized worker, fork snapshot or cross-process Python object sharing is involved. Bytecode is trusted executable bootstrap code bound to this interpreter, not a new portable dependency format. Absolute timings shifted from earlier runs; only matched comparisons establish results.

The generic result is lower constant consumer/bootstrap overhead, most visible for short commands. This is useful machinery, rather than an additional archive-layout win. Django still spends most of its time constructing interpreter/framework objects and finalizing them. Generic runtime-state reuse or deeper code-object changes could be separate research, but would require explicit isolation, invalidation and lifetime semantics; they are not exhausted or disproven here. Further framework-specific startup tuning is outside this track. A reasonable next Gaia research area is programmatic native compiler invocation and bulk immutable inputs, measured through actual parsing/typechecking/compilation so removing filesystem calls is not mistaken for an end-to-end win.
