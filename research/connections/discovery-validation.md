# Source discovery and validation from one native producer

This continuation moves from isolated reuse mechanisms to a concrete source/test workflow. A small workbench presents current function source, tests observed executing its body, their outcomes and the source/configuration generation that produced each observation. It uses ripgrep, Python's structural parser and pytest-testmon's existing collector and selector. The added interface is an ownership and publication boundary around native knowledge, not another test-selection engine.

The [report](../../experiments/discovery_validation/results/jinja/REPORT.md) replays three real Jinja fixes from their first-parent sources: scientific-notation integer conversion, async environment overlays and namespace tuple assignment. Each replay includes preparation, adding regression tests, applying the fix, an unchanged rerun, reverting source and restoring it. Known patches and inspection locations drive the replay. This tests mechanical work and evidence correctness; **it does not measure blind developer or agent productivity**.

All 162 validation runs preserve the expected failures, and the native/shared paths execute identical test sets and outcomes. The added evidence view costs a paired median of 3.8–13.4% over native testmon across the three workflows. Native selection helps the narrow integer fix, while full-suite validation wins both broader workflows in every block. The sample contains substantial timing outliers; these are retained in the report. This establishes the interface's mechanical cost and tested correctness boundaries, without establishing a productivity gain.

## A useful distinction: execution evidence and bug evidence

The async-overlay case makes the distinction concrete. The upstream test added with the historical fix passes before the source fix too. The original PR's reproduction—an async environment calling `overlay()` without specifying `enable_async`—does fail before and pass after. The replay retains both observations. A source-to-test link or a green test therefore cannot establish that the reported behavior was checked. [Original Jinja PR and reproduction](https://github.com/pallets/jinja/pull/2061).

The interface keeps these facts separate: this source is current; these tests executed under a particular generation; this regression failed or passed; the displayed list is not a complete impact set. On an edit, old links remain useful for investigation but become explicitly historical. Old line locations cannot silently become current anchors. A rejected late result is a publication failure, not a passing validation result.

This is a practical connection to temporal databases and provenance: retain the identity and origin of an observation, then join it with current source only under a declared interpretation. A function's unchanged AST is useful information but does not prove that its execution context or result remains valid.

## Native knowledge has more than one consumer

Testmon already collects executed code dependencies to choose later tests. Coverage.py already supports per-test execution contexts. The prototype borrows the testmon producer's existing per-test observations before fingerprint conversion and supplies a discovery projection alongside the native selector. The selector's inputs, outputs and policy are preserved. [Testmon's documented workflow](https://www.testmon.org/), [Coverage.py contexts](https://coverage.readthedocs.io/en/latest/contexts.html).

An independent pytest-cov run verifies every relationship for the functions queried in the three tasks. Across the complete graphs, a few associations differ between runs around generator and weak-reference cleanup. These observations concern execution while a test context is active; they should not be relabeled as direct call edges or complete causal dependencies. The report preserves the discrepancies.

The native baseline is essential. Any reduction from running fewer tests belongs to testmon. The separate measurement asks how much adding the source/evidence view costs, and whether retaining that knowledge could justify a later product interface. The ordinary full-suite control shows when collecting and updating dependencies costs more than the test execution it avoids.

## What remains unanswered

The replay exposes the costs of real validation, evidence production and source-generation handling. It does not establish that the interface helps a person or agent find the right implementation, choose a better regression, or finish a change sooner. The next decisive evaluation would use held-out tasks, existing search/language tools as controls, equal model/tool budgets where applicable, and outcome grading independent of the interface. Adding another index or collector before that evaluation would repeat the earlier mistake of choosing the next local optimization without demonstrating workflow value.

The prototype also lacks automatic filesystem discovery, unsaved-buffer integration, broad semantic navigation, concurrent publication and bounded long-session retention. Its history is explicitly small and session owned. The read-only CLI and retained examples are usable evidence for evaluating the interface; they are not a production service or a new Gaia protocol.

The [implementation](../../experiments/discovery_validation/README.md) joins native test observations to source discovery. It does not change the compiler pipeline.
