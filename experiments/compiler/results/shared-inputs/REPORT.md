# Share immutable input bases and explicit edit overlays

A sealed base plus small edit segments removes repeated publication/admission of the full input collection and reuses unchanged file digests across compilation and dependency replay. Source/header builds improve in the matched run. All external mutable-file condition and receipt guards remain active; this is not a claim that the entire workspace validator now avoids physical files.

## Complete operations

Run `20261031T022604.254307Z`, seven randomized paired blocks, Zstandard 1.5.7 portable C plus a probe, 31 objects, eight workers. Inputs/pages and resident workers are warm. Both native controls use the same newly built host, digest providers, native condition emitter, commands and cache policies.

| Operation | Full snapshot ms | Shared segments ms | Ninja ms | Ninja + ccache ms |
| --- | ---: | ---: | ---: | ---: |
| Unchanged | 2.51 | 2.43 | 3.20 | 3.14 |
| Implementation | 55.90 | 47.82 | 65.75 | 96.92 |
| Shared audit header | 33.56 | 28.33 | 42.66 | 63.50 |
| Generated audit header | 33.59 | 28.01 | 42.14 | 64.13 |
| Unused header | 2.37 | 2.39 | 3.09 | 2.99 |
| Edit/revert | 9.85 | 9.14 | 67.80 | 24.16 |

Shared inputs win 6/7 source and 7/7 shared/generated-header blocks against the full-snapshot control; median paired differences are −8.36/−5.23/−5.49 ms. They beat both Ninja controls in all seven source/header blocks. Whole-result/gate hits bypass input publication; their differences do not establish a collection gain. See [summary](summary.json) and [validation](validation.json).

## Work removed and work retained

The base contains 263 files in 3,344,217 serialized bytes. A normal edit creates one segment: 1,825 bytes for the implementation edit and 156/163 bytes for the audit headers, plus a 146-byte manifest. Visibility masks remain a separate common control input and are still published/parsed. New payload creation, sealing, hashing and receiver admission are all inside the timed changed operation.

| Stage | Full snapshot implementation/shared/generated ms | Shared implementation/shared/generated ms |
| --- | --- | --- |
| Caller publication | 4.80 / 3.03 / 4.39 | 0.68 / 0.63 / 0.60 |
| Native input admission | 1.13 / 1.12 / 1.11 | 0.64 / 0.67 / 0.63 |
| Native file-digest setup | 0.85 / 0.84 / 0.87 | 0.025 / 0.026 / 0.026 |
| Native total setup | 4.27 / 4.32 / 4.24 | 2.89 / 3.05 / 2.96 |

The receiver retains 262 unchanged file digests and computes the changed segment's file digest once. Compilation and native dependency replay borrow the same sealed bytes/digests, retaining private mutable VFS state per compiler worker. Caller publication and native setup are the directly measured mechanism; complete-operation differences also include compilation and other variation, so not every millisecond of the wider source-build gap belongs to these stages. Independent medians do not necessarily add.

All 187 positive external backing files are still read and SHA-256-checked during condition export, about 3 MiB per changed build. Conditions remain byte-identical to the original reference, checked after every actual export outside timing. Tool identity, negative/visibility constraints, copied-output hashes, input stability and final receipt publication remain unchanged. A collection-authoritative workspace would require a separate explicit contract and change-discovery measurement.

## Admission, immutable ownership and controlled warm state

The caller starts from the same already admitted input bytes as the full-snapshot control. Initial fixture/SDK discovery is common untimed setup, not a new gain. Creating the first sealed base, authenticating it in the native worker and building per-file digests occur in recorded seed builds. Clean builds recreate/admit the full base inside timing. No cold-start or initial-admission win is claimed.

The Linux publisher writes each segment into a memfd and applies write, grow, shrink and seal locks. The native receiver independently checks size and seals, maps read-only, validates/authenticates the `GAIACIN3` segment and computes its BLAKE3 file digests. A later reference to the same digest uses the receiver's own retained mapping/FD, even if the original publisher locator has closed. Payload reuse is supported by kernel-enforced immutability, not by trusting mutable timestamps.

Before every warm observation the benchmark restores both the caller's immutable seed state and the receiver's seed segment set outside timing. It drops prior observation overlays and primes exactly the seed manifest. Thus identical repeated edits cannot silently become receiver-cache hits. The changed segment is always created and admitted inside the measured operation. Clean resets both sides to empty, with no prime. No-op/revert observations also restore seeds but bypass the producer during the actual timed build. Control IPC requests appear in resident statistics; they are not measured builds.

## Bounds, portability and residency

Experimental `GAIACIN4` manifests describe one to eight ordered sealed segments plus final tombstones. Logical file names and payload order are independent of physical segment layout. Masks and command/tool identity retain the existing caller-admitted control contract. Local `/proc/<pid>/fd/<fd>` locators are process-local Linux capabilities, not portable durable package identifiers; segment content pins are stable, manifest pins include these transient locators. See the [format/lifetime design](../../../../components/compiler/immutable-input-research.md).

The receiver cache retains at most eight entries/64 MiB of serialized data; each collection also references at most eight/64 MiB. Active pool leases can outlive cache eviction and temporarily retain additional mappings. Caller seed snapshots and Python object overhead are separate. The publisher compacts its current chain when it would exceed these bounds; cyclic edits reuse/move existing identical segments rather than creating duplicate pins. These are research data bounds, not a process RSS quota or production service-memory policy.

Final compiler RSS is about 140.1 MiB shared versus 135.0 MiB full-snapshot in this run. Peak RSS differs in the other direction, but allocator/lifetime variation and shared-page accounting prevent a general memory-saving conclusion. The lightweight checker remains a separate process. Restart requires fresh admission; multiwriter concurrency, descriptor transfer without `/proc`, crash-durable storage and non-Linux adapters are unimplemented. The serial cache API is not intended for concurrent request mutation.

## Verification and reproduction

All [201 tests](correctness-tests.txt) pass with optional providers enabled. The focused [producer rerun](producer-tests.txt) checks sealing, cyclic edits, deletion, compaction, state restoration and mutable-buffer copying; the [six native-parser tests](native-tests.txt) additionally cover pins/framing, unsealed data, UTF-8/canonical paths, independent FD ownership, eviction, live leases and algorithm gating. Real compiler/replay tests exercise optional/hidden files, historical absence, context/provider alternation, reset/prime, corruption and failed-worker recovery. Existing condition/receipt invalidation and mutation-during-build tests remain active.

All 168 main builds and six [boundary builds](boundary/summary.json) validate independently: 174 libraries and 5,394 object checks, with matching runtime probes and expected compilation/link counts. Boundary high-fanout recompiles 26 objects, flags/clean 31. Clean creates/admitted all 3,344,217 bytes and reuses zero cached digests; flags create no new segment and reuse all 263. Single boundary observations are correctness evidence, not latency rankings. See [boundary validation](boundary/validation.json).

Use the [reproduction instructions](../../README.md#shared-immutable-compiler-inputs), [publisher](../../shared_inputs.py), [native backend](../../shared_inputs.h) and [build pins](build.json). Raw `results.json` and `boundary/results.json` are ignored local observations registered in the [evidence manifest](../../../../research/evidence.json). Frozen sources and exact tool/runtime hashes remain in raw run artifacts. This is a generic input representation experiment, not an AST cache or selected public standard.
