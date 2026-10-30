# What the Python experiments taught us

Loading dependency contents and choosing dependency versions are different operations. The research measured them separately.

## Loading: avoid rebuilding knowledge on every start

Keeping an archive/index open, reusing module/resource discovery state and leaving unused metadata mapped helped the measured loading paths. Compact native metadata mattered most when many modules were available and few were imported.

Native byte access alone did not produce a clear Django startup win. Python still has to decode/execute code, construct classes and initialize the framework. Later generic startup changes improved short commands by roughly 27–31%, while focused Django confirmation showed a smaller 3.6% median gain. These are matched results from different workloads, not one combined speedup.

Read the [loading review](dependency-formats.md) for the individual comparisons and evidence. Framework-specific tuning is paused; a representative real tool or a concrete compatibility gap is a better reason to reopen the work.

## Resolution: much of the easy-case cost was bookkeeping

Bulk metadata, cached predicates, incremental scheduling and reversible state removed repeated scans and copying. On a synthetic 4,000-leaf conflict-free graph, reversible state reduced a reused solve from about 2,171 to 180 ms. The published Django candidate set provided a smaller real-input check of metadata delivery and artifact selection.

These results do not make hard dependency search easy in general. The implementation is a local Python reference provider with pinned resolver behavior, and it does not replace pip's complete selection, installation, source-build or remote-discovery behavior. Read the [resolution review](resolution.md) for controls, candidate counts and limits.

## What remains uncertain

Native wheels, broader loader semantics, installed-state preference, arbitrary package/build behavior and a remote candidate universe are not established. Faster isolated reads or solves do not necessarily improve whole-process startup. Producer/admission work and normal shutdown still count.

The [prospects](prospects.md) identify useful follow-ups. [Run locations](experiments.json), [loading lab notes](../../experiments/python/dependency_bundles/FINDINGS.md) and [resolution lab notes](../../experiments/python/dependency_solving/FINDINGS.md) retain the detailed evidence.
