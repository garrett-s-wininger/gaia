# Sharing work beyond compilation

The [first experiments](../../experiments/workflows/results/combined-control/REPORT.md) test three different sources of repeated work: independent repository scans, repeated schema interpretation and downstream work after unchanged intermediate results. A fourth probe starts the native checkpoint persistence boundary.

The [broader coverage overview](coverage.md) connects these with the parallel compiler, artifact, runtime and testing studies. The [unmodified Protobuf control](../../experiments/workflows/results/protoc-guarded/REPORT.md) tests a production schema compiler and retains a rejected descriptor-handoff case.

The most useful distinction is between sharing a good operation and replacing it with a weaker implementation. One combined ripgrep scan takes 17 ms here, versus 44 ms for six parallel ripgrep queries; our first fused Odin scanner takes 105 ms. This establishes an existing competent baseline for future repository interfaces.

The [reviewed-source confirmation](../../experiments/workflows/results/reviewed/REPORT.md) improves synthetic schema generation from 23.5 to 8.5 ms by resolving once. Stopping at unchanged emitted outputs reduces complete downstream work for reorder/description edits to about 10 ms, while a field-type edit saves no work. Neither result establishes gains for production schema tools yet. The earlier run remains separate evidence with its original source identities; input-validation and persistence-read-error regressions are now included in 15 tests.

The Odin checkpoint prototype demonstrates typed immutable objects, authenticated historical reads, explicit root publication and process-exit boundaries. Whole-file storage and flat manifests visibly amplify small changes. It does not complete the [source-control milestone](../../components/source-control/milestone-1.md).

Follow up with real heterogeneous consumers, production schemas and explicit invalidation contexts. Keep selective access, strong independent controls, admission, retained memory and failure behavior in complete-operation costs. [Code and reproduction](../../experiments/workflows/README.md), [run index](experiments.json).
