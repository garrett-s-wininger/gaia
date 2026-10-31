# A real offline OCI rootfs executes the same framework operation

Three actual Podman containers execute the same unmodified Python/Django/DRF/template/resource consumer as the environment study. Networking is disabled, the root filesystem is read-only, cgroup management is disabled and every run exits normally with automatic container removal. The package/API/resource oracle matches in all three observations.

Median ready-and-normal-teardown time is 1,218.33 ms. The local rootfs contains 152,122,677 file bytes and takes 4,969.37 ms to prepare separately. Preparation copies the installed compatible interpreter, standard library, discovered linked libraries and package corpus, with executable modes preserved. It is not image download, OCI registry access, image layering or lazy-pull measurement.

This control supplies real process/filesystem namespace isolation that the direct Python experiment does not. Its latency is therefore not an equal-capability speed comparison. The existing SDK and package payload are already local, and the 3 observations establish readiness rather than production-scale performance confidence.

The managed sandbox could not map namespace IDs; an approved host-local capability probe and actual offline runs provided support. The private container store/runtime/rootfs paths are disposable. No remote image or network resource is used.

Runtime/app identities are checked before/after. [Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), [reproduce](../../README.md).
