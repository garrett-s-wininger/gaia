# Private work and immutable bytes have different sharing benefits

## Pass overlap is correct in the bounded contract, but not a clear performance improvement

The [LLVM study](../../../experiments/science/compiler/results/passes-frozen/REPORT.md) validates 108 actual Zstandard objects against stock CLI references and 54 analysis results against serial fact hashes/counts. Forked children operate on private copy-on-write snapshots from a runtime-checked single-threaded parent. The analyses compute dominators, loops and postdominators; they are not synthetic name hashing.

On unchanged large input the existing serial IR guard takes 88 ms, parallel analyses 93 ms, speculation 114 ms and both 118 ms. Large semantic misses remain near four seconds. Small semantic misses grow from 46 ms for the serial guard to 72 ms with speculation. Three-sample differences do not establish a useful general overlap win. Keep the negative result: fork/coordination and discarded work matter, while the dramatic hit benefit comes from previously established IR reuse.

CPU accounting combines coarse parent process ticks with child `wait4` usage and excludes controller CPU. Object correctness does not establish compatibility with arbitrary compiler side products or safe fork from a multithreaded host.

## Sharing source bytes reduces worker PSS without sharing compiler state

The [sealed-input study](../../../experiments/science/compiler/results/shared-inputs/REPORT.md) admits roughly 12 MB of real source once for four private Python compiler workers. Six sessions validate 1,440 module compilations and reject stale-generation requests/reclamation under active leases. Shared mappings reduce current aggregate worker PSS from 98.7 to 62.8 MB; RSS stays similar because each mapping is counted separately.

Session medians are 411 ms for private copies and 345 ms for shared mappings. Request-wave medians are 66 and 64 ms, providing no substantial compilation-throughput claim. Producer preparation costs another 2.02 seconds. Current worker samples exclude producer/transient memory and are not peaks; cooperative leases do not track arbitrary external descriptor duplication.

## Hardening follows measurement rather than silently changing its identity

Review identified side-output filtering, exception cleanup, child pipe draining and descriptor-to-generation ownership requirements. Current source/tests have been hardened separately: thirteen focused tests and two actual compiler-command/object replays pass. The performance matrix was not rerun. The published tables retain the original measured source and binary identities; their successful fixed cases do not establish the newly tested failure-boundary behavior or performance of the hardened host.
