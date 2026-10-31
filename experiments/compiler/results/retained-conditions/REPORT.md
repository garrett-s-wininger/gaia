# Retain condition-production structure

Retaining immutable producer structures reduces condition export from about 9.2 to 5.2 ms and removes another 4–5 ms from header builds in this experiment. Every positive backing file is still read and hashed. The emitted index is byte-identical to the reference implementation.

## Complete operations

Primary run `20261031T005712.820765Z`: seven matched blocks, Zstandard 1.5.7 portable C plus a probe, 31 objects, eight compiler workers. Warm page cache, admitted inputs and resident native compiler/checker workers. `gaia-retained` adds producer retention to the existing `gaia-rebound` linked-result path.

| Operation | Prior producer ms | Retained producer ms | Ninja ms | Ninja + ccache ms |
| --- | ---: | ---: | ---: | ---: |
| Unchanged | 2.55 | 2.52 | 2.99 | 3.10 |
| Implementation | 58.53 | 54.69 | 65.43 | 97.19 |
| Shared audit header | 37.00 | 32.37 | 41.02 | 62.21 |
| Generated audit header | 37.16 | 32.90 | 41.83 | 62.74 |
| Unused header | 2.40 | 2.39 | 3.06 | 3.05 |
| Edit/revert | 9.67 | 9.26 | 64.37 | 23.91 |

Retained production wins six of seven paired implementation blocks and all seven shared/generated-header blocks against the prior producer. Median paired differences are −2.54, −5.15 and −4.47 ms respectively; these are paired differences, not differences of medians. Source/header builds win all seven blocks against both Ninja controls. No-ops, irrelevant-header edits and whole-result reverts bypass condition export: their small shifts are not producer gains.

Implementation export falls from 9.32 to 5.32 ms, shared-header export from 9.15 to 5.12 ms and generated-header export from 9.21 to 5.11 ms. See [summary](summary.json) and [validation](validation.json). This remains one C target and establishes neither a universal advantage nor a final floor.

## Reuse exact structures, keep physical checks

The serial producer retains parsed fragments keyed by action, selected journal checksum and cwd; namespace classification keyed by exact visibility masks; and precomputed condition rows keyed by exact target/listing structure. Canonical path strings are shared. Logical SHA-256 hashes are reused only for the exact same immutable `bytes` object held by a strong reference; mutable buffers are rehashed. Cwd, namespace and shape changes invalidate the corresponding structures.

A typical edit reparses one of 31 fragments, retains the namespace and row plan, computes one logical content hash and reuses 186. All 187 positive physical inputs are still statted, read and hashed (about 3 MiB). Negative lookups, directory/ancestor kinds, visibility, tool/request identity, native validation, copied-artifact hashes and stability guards remain in place. Roughly 4.2 ms remains in physical verification and row emission.

Wire formats remain `GAIACQ01` and `GAIACF01`. Persistent fragment encoding and publication remain inside the complete-operation clock. After every actual retained export the parent independently rebuilds the original reference index and compares exact bytes outside that clock, alongside artifact/runtime/work-count checks.

The benchmark restores an immutable producer snapshot alongside on-disk seed caches before each observation, outside timing. Baseline and edited seeds are distinct; clean builds reset the producer to empty. This represents an ongoing warm session without letting one variant silently warm another. Cold/restarted producers reconstruct their structures.

## A separate reader-allocation issue

The initial pilot exposed a bounded reader that requested the full 8 MiB limit for a roughly 37 KiB cache. The shared reader now obtains the file size, checks bounds and reads exactly that size plus one byte, rejecting size changes and malformed checksums/framing. Both primary controls were remeasured with this fix.

The [initial pilot summary](initial-control/summary.json) and [validation](initial-control/validation.json) preserve the earlier comparison; do not pool its absolute times with the primary run. Its intrusive [allocation profile](initial-allocation-profile.json) reports about 8.53 MiB versus 0.47 MiB peak traced allocation, largely the avoidable read reservation. With the shared fix, the [publication profile](publication-profile.json) shows 626,140 versus 469,938 bytes. Retained initialization/live state is excluded: these are per-call allocation diagnostics, not whole-workflow RSS or a total-memory saving claim.

With the fixed reader, prefix walks fall from 4,924 to zero and SHA-256 calls from 380 to 192 in that diagnostic. Backing/journal file reads remain 188 in both paths. The diagnostic uses unchanged logical bytes and one missing fragment, so all 187 logical hashes are reusable; a real edit computes one. Profiling/tracemalloc timings are intrusive and are not latency evidence.

## Bounds and limitations

Retention is one current request, not arbitrary history. Existing limits include 64 fragments/8 MiB serialized fragment data, 4 MiB serialized namespace data, 100,000 files, 200,000 namespace nodes, an 8 MiB/65,536-row index and 100,000 canonical paths. Oversized optional metadata disables retention without invalidating a valid index. Immutable body references are shared rather than copied, but Python object overhead and those references are outside serialized-byte accounting; there is no strict process-RSS bound here.

State advances only after a valid index. Optional disk-publication failure can leave valid memory state available; restart still validates the disk cache. Native binaries are unchanged by this experiment. Existing residency, single-writer, crash durability and broader-workload limitations from the [linked-result study](../linked-results/REPORT.md) continue to apply.

## Verification and reproduction

All [135 tests](correctness-tests.txt) pass with the optional native providers enabled. They include reference-wire equivalence, randomized masks/action reorder, native invalidation, immutable versus mutable buffer reuse, corrupt disk/restart behavior, failed physical validation, eviction of unused references, metadata bounds and cache-reader size races. The pilot and primary each validate 168 complete builds; six further [boundary builds](BOUNDARIES.md) cover high fanout, flags and clean reconstruction. All 342 libraries and 10,602 object checks pass independent CLI references and runtime probes.

Use the [benchmark instructions](../../README.md#retained-condition-production), [producer](../../retained_conditions.py), [tests](../../test_retained_conditions.py) and [profiling tool](../../profile_retained_conditions.py). Raw observations are ignored local artifacts: `results.json`, `initial-control/results.json`, `boundary-raw/results.json`; their hashes are registered in the [evidence manifest](../../../../research/evidence.json). Frozen sources and native/tool digests are recorded in the raw runs; a clean checkout contains reports and compact evidence, not generated SDKs, binaries or machine-specific raw observations.
