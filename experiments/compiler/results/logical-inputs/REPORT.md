# Validate compiler completion against an authoritative workspace

Admitting explicit changes into immutable logical generations removes repeated physical source validation from the measured compiler path. Source edits take 42.25 versus 48.78 ms and low-fanout header edits about 21 versus 28 ms against the same-host physical compatibility control. This changes the source-of-truth contract: an editor/source-control API owns the logical workspace, and unreported edits to a physical mirror do not change it. It is not a drop-in filesystem cache.

## Complete operations

Run `20261031T033053.134187Z`, seven randomized paired blocks, Zstandard 1.5.7 portable C plus a probe, 31 objects and eight workers. All controls use the same pinned compiler/linker, SDK, flags and independently validated artifacts. Native controls share the same sealed-input backend and object/three-candidate linked-result policies.

| Operation | Physical compatibility ms | Logical API ms | Ninja ms | Ninja + ccache ms |
| --- | ---: | ---: | ---: | ---: |
| Unchanged | 2.35 | 2.32 | 3.50 | 3.08 |
| Implementation | 48.78 | 42.25 | 66.35 | 98.33 |
| Shared audit header | 27.84 | 21.00 | 44.01 | 66.04 |
| Generated audit header | 27.80 | 21.19 | 42.65 | 66.72 |
| Unused header | 2.59 | 2.21 | 3.11 | 3.06 |
| Edit/revert | 9.46 | 6.53 | 66.54 | 24.73 |

Logical source/shared/generated operations win all seven blocks against the physical control, with paired median differences of −7.07/−7.24/−6.83 ms. Unchanged differences are negligible (4/7 wins). The audit headers deliberately have low fanout; a separate real high-fanout header validates wider invalidation. See [paired summaries](summary.json), [main validation](validation.json) and [boundary validation](boundary/validation.json). Compare controls within this run; do not add gains from earlier experiments.

## What changed

Each operation captures an immutable map of admitted bytes, masks, SHA-256 body digests and namespace nodes. A supplied edit packet is admitted and hashed inside the timed build. The compiler consumes that captured generation through the existing sealed-segment interface. Condition production reuses its retained structures and cached admitted digests instead of re-reading 187 positive physical files, roughly 3 MiB, on a changed build.

The separately versioned `GAIALQ01` condition wire reserves physical timestamps/mode fields as zero. Its positive size/content and negative/directory/visibility/listing conditions are compared against both the captured and current generations before completion publication. All exported conditions equal the independently generated physical reference after exactly this normalization. Relevant edits during compilation prevent current readiness; unrelated edits can remain selective. Publication holds the update lock through receipt creation.

Condition export falls from 4.43/4.32/4.37 ms to 1.59/1.48/1.33 ms for implementation/shared/generated edits. Complete edit ingress is about 0.14–0.16 ms. Export savings explain part of the end-to-end gain; removing physical namespace/receipt work and the checker transport also changes the path. The larger wall-time difference must not all be attributed to positive-file reads alone.

Tool membership and pinned bodies, command/request identity, output-role membership and copied-output integrity remain checked. The logical reference checker runs in process and unconditionally SHA-256-checks every output, including ordinary current hits. The physical control retains its existing resident checker and receipt optimizations. These are explicit implementation differences: complete wall time is decisive, while child-only CPU would omit logical parent work and is not a comparable total. This experiment does not isolate every transport or allocation contribution from the changed validation contract.

## Admission and filesystem compatibility

Initial project/SDK discovery is common untimed fixture setup. First logical hashing/map admission is charged in recorded seed builds and clean operations; warm operations charge supplied packet admission, immutable-map copying, publication, compiler work, condition export and completion. The prototype copies its map on update and does not establish large-repository update complexity. The external producer of edit packets is part of the API contract, not a free watcher.

The [physical-import diagnostic](admission.json) separately measures full known-namespace reads between before/after metadata checks, against admission of an already supplied edit packet. It verifies the mirror and never rewrites sources. Warm pages and known membership make this narrower than arbitrary filesystem discovery. Its `stat_calls` field counts the global before/after stamps only; bounded reads also make regular-file/size checks. It is a strict compatibility adapter, not an optimized watcher or a syscall trace. Full importer time includes those additional checks.

Across 21 diagnostic blocks, importing 263 files/3,319,849 body bytes takes 4.88 ms median; admitting the supplied 1,685-byte edit takes 0.050 ms and an empty packet 0.038 ms. Initial logical admission hashes those 3.32 MB in 2.51 ms in this diagnostic. These microbenchmarks explain the boundary and are not additive gains on top of the complete-operation table.

A physical directory still requires discovery/import and a concurrency contract. Metadata observations do not make a hostile mutable filesystem transactional. The logical API, by contrast, only changes through atomic admitted updates. Readiness refers to an observed generation; a future edit can invalidate it.

## Correctness, bounds and reproduction

All [213 compiler tests](correctness-tests.txt) pass with optional native providers enabled. New tests cover immutable caller buffers, compare-and-exchange, 80 randomized generation/reference comparisons, negative and hidden membership, directory listings, tool/output/request corruption, bounded history captures, publication locking, racing physical imports and relevant/unrelated updates around real native compilation. Existing corruption, sealing, eviction, live-lease and failed-worker checks remain active.

All 168 main and six boundary operations compare every object/library with independent CLI references: 174 libraries and 5,394 object checks, with runtime results, exact compiler/link work and normalized condition equality. Boundary clean/flags compile 31 objects; high fanout compiles 26. Single boundary observations establish correctness, not timing rankings. Initial admission and retained memory are separate from warm-update gains. There is no total RSS quota, durable multiwriter store or filesystem watcher in this prototype.

Use the [reproduction guide](../../README.md#authoritative-logical-compiler-inputs), [workspace/checker implementation](../../logical_workspace.py), [physical-import profiler](../../profile_logical_admission.py) and [contract](../../../../components/compiler/immutable-input-research.md#authoritative-logical-workspace-experiment). [Source identities](sources.json) match the frozen measured files; [publication checks](publication-validation.json) include a clean source copy with ignored raw data absent. Full observations remain ignored local `results.json` and `boundary/results.json`, registered by size/hash in the [evidence manifest](../../../../research/evidence.json).
