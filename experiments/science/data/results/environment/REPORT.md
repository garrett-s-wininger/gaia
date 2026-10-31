# Ordinary symlinks already capture most read-only environment reuse

The actual consumer initializes Django, validates a current-request DRF serializer, renders a Django template and reads a pinned package resource. Every fresh isolated Python process checks versions, API data, template output, resource hash and module-origin containment. Three shuffled blocks construct copy, one-directory-symlink and direct-search-root environments, then run three fresh processes and remove the private environment. All 27 operations match.

| Read-only environment | Setup median | First ready | Complete 3-start session + teardown |
| --- | ---: | ---: | ---: |
| Copy all dependency files | 3,349.31 ms | 4,141.69 ms | 5,775.35 ms |
| Conventional directory symlink | 2.26 ms | 619.23 ms | 1,772.25 ms |
| Direct search-root configuration | 1.88 ms | 631.62 ms | 1,750.37 ms |

Direct binding establishes no material advantage over the strong symlink control. Both avoid copying 4,018 logical files. The read-only dependency contract permits sharing; a writable private virtualenv would be a different operation. Prefix/file-path identity is not asserted equal; required observable application behavior is.

Common preparation separately reads/authenticates the existing corpus in 115.24 ms and materializes its dependency tree in 3,731.80 ms. Charging that to first readiness gives roughly 7.99 s copy, 4.47 s symlink and 4.48 s direct. Original artifact download and acquisition of the already compatible interpreter/SDK are not measured. This result is repeated local environment composition, not a full remote package installation win.

The timing includes source/config creation, connection-free fresh process readiness and normal private-tree teardown. Shared immutable dependency-tree lifetime remains separate; teardown is about 301 ms for copies and below 1 ms for the other modes. All controls use the existing compatible SDK. A separate preparation builds a local OCI rootfs from the interpreter/stdlib/runtime libraries and the same dependencies; see the offline OCI control rather than folding stronger isolation into this comparison.

The first development rootfs copy omitted executable permission on the interpreter. The corrected preparation preserves modes; the actual OCI probe passes. This report's frozen rerun source identities include that correction, and the early unsuccessful development artifacts are not primary measurements.

[Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), [reproduce](../../README.md).
