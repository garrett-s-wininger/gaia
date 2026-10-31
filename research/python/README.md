# Python dependency and interpreter research

The work separates dependency loading, package resolution and interpreter-state reuse. Their timings are independent; the new state-reuse comparison does not rewrite earlier loading results.

- [Findings](findings.md): the conclusions in plain language.
- [Prospects](prospects.md): useful reasons to reopen this track.
- [Loading review](dependency-formats.md) and [resolution review](resolution.md): detailed comparisons and implementation maps.
- [Interpreter-state review](interpreter-state.md): resident templates versus actual disk restore.
- [Run index](experiments.json): retained reports and raw data.
- [Technical task register](follow-up.md): stable task IDs and acceptance criteria.

The original plans are retained under [designs](designs/README.md). The [loading code](../../experiments/python/dependency_bundles/README.md) and [resolver code](../../experiments/python/dependency_solving/README.md) include reproduction instructions.

Full raw observations and profiler captures are excluded from Git. Their original identities are recorded in the [evidence manifest](../evidence.json); raw files are local-only, with no published download location. Reports and validation summaries remain versioned.
