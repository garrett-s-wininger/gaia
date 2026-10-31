# Where scientific models helped and where simple controls won

## Set differences can reduce metadata without reducing cold CPU

The [reconciliation study](../../../experiments/science/data/results/reconciliation/REPORT.md) compares complete sorted inventories, a simple prefix-hash hierarchy and an IBLT-style sketch. For 3,931 real content IDs with three removed/three added IDs, metadata falls from 251,632 bytes to 9,030 bytes for the hierarchy and 608 bytes for the sketch. Cold construction/verification takes about 3.9, 16.6 and 31.8 ms respectively in these Python prototypes. Underestimating the sketch causes exact-list fallback; no missing content is silently accepted.

The [information model](../../../experiments/science/data/results/information/REPORT.md) separates protocol overhead from an ideal counting model with explicit assumptions. It does not turn that model into an unconditional communication or latency bound. Maintained summaries and actual network latency need a separate complete synchronization experiment.

## Feedback did not beat the best fixed batching policy

The [delivery study](../../../experiments/science/data/results/delivery/REPORT.md) runs actual persistent HTTP/1.1 and binary connections with the same content framing and verification. At the modeled 5 ms application-service latency, four concurrent batches of four objects complete in about 37/30 ms for HTTP/binary, versus 356/305 ms sequentially. The damped controller takes about 67/60 ms and does not beat that fixed policy. There is no universal protocol or adaptive-control victory; current overheads, complete readiness and first useful object remain distinct.

## Placement improves over lexical order, but nature/geometry lose stronger controls

The [actual pack reader](../../../experiments/science/data/results/locality/REPORT.md) consumes 560 held-out chunk events from another fresh Django process, with reversed order as a synthetic stress. Under an 8 MiB logical chunk budget, lexical 8-chunk grouping reads 167.3 MB; training-based static greedy clustering reads 92.7 MB. Reinforcement/decay reads 135.8 MB. Native 3D force grouping reads 150.6 MB, versus BFS at 132.4 MB. Geometry therefore improves the weak lexical arrangement while losing simpler co-access controls.

Single-chunk cost/size retention reads only 27.7 MB but makes more calls. Actual warm read/verification clocks and modeled per-call/bandwidth cost are separate. Every layout repacks the full 28.59 MB here; training, geometry construction and repacking must be amortized. The train/held-out processes repeat the same application workload and do not establish broad unseen-project generalization.

The [bounded search model](../../../experiments/science/data/results/tuning/REPORT.md) gives grid, random and mutation/selection search six evaluations each. They reach the same median held-out cost in this small space. Search CPU and hypothetical service evaluation costs are visible. There is no evidence that the evolutionary candidate is necessary.

## Environment sharing already has a competent filesystem control

The [Python environment experiment](../../../experiments/science/data/results/environment/REPORT.md) executes real framework operations in 27 fresh processes. Three-start sessions take about 5.78 seconds with copied dependencies, 1.77 seconds with a conventional directory symlink, and 1.75 seconds with direct search-root configuration. Direct binding does not establish a material advantage over the symlink baseline. Common corpus materialization costs another 3.73 seconds and is charged separately to first readiness.

The [OCI diagnostic](../../../experiments/science/data/results/oci-readiness/REPORT.md) additionally executes the same operation in three actual offline read-only containers. It costs about 1.22 seconds per ready-and-teardown observation, after 4.97 seconds preparing a 152 MB rootfs. It supplies stronger namespace isolation and is not an equal-capability speed comparison or an image-pull benchmark.

## Known values are insufficient for an exact adapter contract

The [roundtrip study](../../../experiments/science/data/results/adapter/REPORT.md) preserves opaque optional extensions and explicit/default presence metadata through JSON. All 2,560 exact roundtrips pass; a lossy known-field view retains the projected values but changes 426 of 512 records. Required unknown extensions fail closed. This bounded contract is useful evidence for future shared facts, not a repaired Protobuf format or a universal AST.
