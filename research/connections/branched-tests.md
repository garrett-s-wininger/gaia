# Prepared runtime state with private test resources

The sixth experiment follows the [branched-execution proposal](architectural-next.md#second-choice-branch-initialized-execution-state) into a real Django application. It composes three existing facilities: native Python process reuse/fork, a migrated and seeded SQLite database, and private attachment files. Source/configuration identities determine when initialized state is eligible for another request.

The [measured report](../../experiments/branched_tests/results/django-todo/REPORT.md) compares that composition against fresh pytest, native `--reuse-db`, and prepared fixture copies with fresh interpreters. The comparison includes construction, source edits, interrupted requests, resource rebinding, ordinary finalization and final disposal. It is deliberately a small test-selection loop, not a full application suite or a compiler benchmark.

Across seven randomized blocks, the complete ten-request trace takes a median **6.02 s with forked branches**, **6.19 s with fresh Python and native database reuse**, and **4.94 s with a warm worker**. Forking cuts 28.72% against fully fresh runs, but only 2.35% against the stronger database-reuse control, with wins and losses across blocks. Warm reuse cuts 20.21% against that control by paired median under its narrower contract. The largest sampled parent-plus-child PSS is about 105 MiB for forked execution, versus about 65 MiB for native database reuse.

All 350 timed requests agree on their supported outcomes. The separate successful-mutation probe demonstrates the warm worker's heap leak and the forked request's isolation. The useful result is a measured tradeoff between reuse, isolation and invalidation cost; it is not a robust latency win for a new snapshot runtime.

## The connection made concrete

The useful connection is between **database snapshots, virtual-memory branching, and explicit effect lifetimes**. A reusable unit needs an identity for its initialized memory and a rule for binding each mutable resource. Forking memory alone leaves committed database and file writes visible to subsequent users; a negative control demonstrates both leaks. A source key alone does not isolate effects, and copying a database alone does not reset Python globals.

The prototype admits a single-threaded parent with closed database connections and no extra descriptors. Each request receives a private SQLite file and media tree. Its fork child exits through normal Python finalization. The controller owns cleanup even after SIGKILL. On a changed source or settings generation, the initialized process and prepared fixture are reconstructed. These mechanisms are native facilities composed under a declared application contract; this is not evidence for a new general-purpose snapshot engine.

The research connection comes from systems that choose an initialized execution boundary together with resource handling. SnapFuzz combines late snapshot placement with communication and filesystem changes for network fuzzing. Faasm restores initialized state while providing isolation and controlled sharing for serverless functions. Their workloads and published speedups do not predict this test loop's result. [SnapFuzz, ISSTA 2022](https://srg.doc.ic.ac.uk/files/papers/snapfuzz-issta-22.pdf), [Faasm, USENIX ATC 2020](https://www.usenix.org/conference/atc20/presentation/shillaker).

## Why the controls matter

The first profile found that creating test users spent most of its time hashing passwords. Every measured mode therefore uses Django's normal fast test hasher. Avoiding that work would be an ordinary test configuration improvement, not evidence for Gaia's architecture. [Django testing guidance](https://docs.djangoproject.com/en/5.2/topics/testing/overview/#password-hashing).

The native database control also keeps its schema across the tested method and permission-setting edits. It retains ordinary transaction-test teardown and uses Django's flush after forced termination. Prepared snapshot arms conservatively reconstruct their fixture on generation changes. The comparison therefore exposes the cost of broad snapshot invalidation instead of forcing the native control to rebuild unnecessarily.

Warm execution has a distinct correctness limit. A successful test that commits database changes, writes a media file and mutates a Python module can leave the next warm request contaminated even when its database and media are replaced. An explicit restart restores correctness; a forked request discards that heap mutation automatically. The diagnostic and timing trace are reported separately: successful operations in the timed warm trace satisfy its bounded reuse contract, while failed/killed operations trigger restarts.

## What this establishes

The experiment supports an application-specific boundary for retaining prepared state and binding private resources. It does not establish a universal reset operation for arbitrary libraries, threads, external services, native extensions or device contexts. The Python audit guard is an observation aid, not a security sandbox. The SQLite/media files are copied on tmpfs; no persistent-storage or reflink claim follows.

The practical question for Gaia is which initialized states can be **admitted, invalidated and released correctly**, and when sharing them repays construction and lifecycle costs. The report separates a warm worker's narrower reuse contract from fresh-process isolation, and includes the cost of restoring state after source changes. A GPU/NPU backend or a replacement compiler would not address the work measured here.

The [implementation](../../experiments/branched_tests/README.md) studies runtime and resource isolation separately from the compiler pipeline.
