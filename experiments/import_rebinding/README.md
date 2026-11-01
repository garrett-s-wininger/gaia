# Rebind retained import references across namespace changes

This extends the [source-delta experiment](../delta_analysis/README.md) at its dominant remaining boundary: adding or removing a module used to rescan every source file. The new prototype separates native parsing from membership-dependent binding, then compares complete navigation/diagnostic responses against full rescans and a stronger scoped native parser control.

Read the [measured report](results/django/REPORT.md) and [research interpretation](../../research/connections/import-rebinding.md). This is a native Python import-resolution experiment; the [Clang integration](../integration/README.md) has separate controls and measurements.

## Native boundary and semantics

Grimp 3.17 already separates its Ruff-based import parser from resolution in its Rust implementation. The small [native patch](native.patch) adds `retain_references=True` to the scanner. It returns the native parser's absolute imported-object names before checking module membership. Relative-name normalization, source locations, statement text, lazy-import flags, syntax errors and import extraction remain native. The default scanner path still resolves imports normally. The patch applies to the pinned upstream source; it does not replace the parser with a simplified recognizer.

For the fixed options used here, the installed internal resolver checks **the exact object name, then its immediate parent**, and otherwise emits no internal dependency. The Python binder implements precisely that rule. It does not recursively search arbitrary ancestors or model Python's runtime attribute semantics. A wildcard reference such as `package.*` participates in the same exact/parent rule. External imports are excluded; type-checking imports are included.

Each source contributes references containing its importer, absolute imported-object name, line number, line text and lazy flag. The index records both candidate names, even when one is absent:

```text
candidate(reference) = [exact name, immediate parent]
binding(reference, modules) = first candidate present, otherwise absent
watchers[name] = source modules whose references mention that candidate
affected = watchers joined with added/removed module names
```

New/edited source still requires parsing. An unchanged source affected only by module membership can reuse its references. Both candidates are indexed conservatively, even if the exact candidate currently exists and hides the parent. Module names include namespace-package nodes discovered by Grimp. Module-file to package changes reparse the declared changed source, so relative normalization stays current.

This is a specialized indexed join over native facts, not a general Python resolver or a new dependency rule. It directly addresses the prior [missing-module cache counterexample](../delta_analysis/results/django/cache-boundary.json): an absent imported name must remain an observation, because its later appearance can change an unchanged file's answer.

## Controls

All three arms use the same locally built native scanner binary, the same native graph, the same cached native consumers and the same immutable JSON response. The unmodified Grimp wheel independently rebuilds the validation graph. Thus compiler/build differences between the local extension and wheel do not distinguish the timed arms.

| Arm | Ordinary edit | Module membership change | Additional retained state |
| --- | --- | --- | --- |
| `full_rescan` | Parse edited files | Parse all files | None beyond the prior native producer |
| `scoped_native` | Extract references and update the name index | Reparse only unchanged files selected by the index | Candidate-name index; discard parsed references |
| `rebind` | Extract references and update the name index | Bind selected unchanged files' retained references | Same index plus complete reference records |

For both indexed arms, initial and edited-file extraction produces references once, binds them, and updates the index. The scoped control discards references after deriving the index; it is not charged for keeping an unused copy. On membership changes it calls the native scanner for selected unchanged files. The rebinding arm instead runs the small binder on their stored references. Selection is at source-file granularity; it currently rebinds all references in an affected file, not just the individually affected references.

The response contract is inherited unchanged: dependency-navigation sets for three targets, current-generation forbidden-rule violations for exact `django.utils.*` source modules, and one shortest explanation with current line numbers for each violation. The actual Import Linter contract uses the prior single-explanation adapter. A fresh **unmodified full contract** checks the violation set and shortest explanation length. This is an editor response, not equivalence to the full multi-chain CLI report. The diagnostic is an experimental policy, not a Django policy or a claim of Django defects.

`producer.py` adapts the prior session through a factory substitution confined to a serialized worker request. The earlier experiment's measured source files remain unchanged. This is not a concurrent extension API or production integration.

## Workload and checks

The original 16-event Django trace is reused without modification: initialization, unchanged requests, location/comment edits, import changes, absent-module appearance, cyclic dependencies losing/regaining an exit, module removal, original-source restoration and a diagnostic-target change.

Two additional stress events create and remove `django/utils/translation/gettext_lazy.py`. This intentionally changes the binding of a name already used by 62 unchanged modules. It is a constructed shadowing case over real source, not an upstream patch, executable application change, or sampled developer behavior. The report separates these events from the original trace.

Seven shuffled blocks run the three arms in fresh processes. Every one of the 378 responses must match a fresh uncached Grimp graph's complete module/edge set and all line/text/lazy metadata. The native full linter checks current violation sets, minimum witness lengths and every witness edge/location. The test suite checks 360 randomized source-update batches across the three arms, relative/aliased/multiline/star/nested/type-checking/lazy imports, absent names appearing/disappearing, stale index removal after import retargeting, namespace packages, file/package replacement, syntax-failure rollback before publication and generation rejection.

The request clock includes source writes, rediscovery, parsing, reference export, binding, index maintenance, graph mutation, native consumer work and full JSON serialization. Initial extraction/index construction is charged. Native extension compilation, package acquisition, interpreter/library startup, corpus copying, validation and logical-state counting are preparation or separate spans. Source/tool identities are checked again after the matrix.

All arms still call Grimp's full package discovery on membership changes; this costs time even when parsing is avoided. Requests come from one client with declared edits. No filesystem watcher, automatic change detection, altered parser-option context, new top-level package, concurrent publication or general failure-atomic graph mutation is implemented. The same fixed parser options and query roots apply throughout.

Validation between measured requests can perturb allocator/GC/cache state. Trace totals are sums of event spans, not uninterrupted session times. The shared advisory lock excludes cooperating measurements, not all system load. Seven-block ranges are descriptive, not confidence intervals. A separate [GC diagnostic](diagnostics/gc_profile.py) instruments one extra trace per arm; it is not pooled with the timing matrix. Logical retained counts are reported; peak process RSS includes oracle allocations and is not attributed retained memory.

## Reproduce

Use CPython 3.14 with Grimp 3.17 and Import Linter 2.15, the [prior pinned environment](../delta_analysis/results/django/acquisition.json), trusted Django 6.1.2 source, a pinned Grimp 3.17 source archive, `patch`, and a working Rust toolchain. The measured build used Rust 1.99.1 and the archive's Cargo lockfile. Its exact input URL, checksums, compiler version and native binary identity are in [native build provenance](results/django/native-build.json).

```sh
# If using a private rustup installation, set CARGO_HOME and RUSTUP_HOME
# to that installation's directories before running the build helper.
experiments/_work/delta-analysis-env/bin/python experiments/import_rebinding/build_native.py \
  --archive /path/to/grimp-3.17.tar.gz \
  --work experiments/_work/import-rebinding-build \
  --cargo /path/to/cargo --rustc /path/to/rustc

PYTHONDONTWRITEBYTECODE=1 experiments/_work/delta-analysis-env/bin/python \
  experiments/import_rebinding/run.py \
  --corpus /path/to/django \
  --native experiments/_work/import-rebinding-build/grimp-3.17/rust/target/release/lib_rustgrimp.so \
  --work experiments/_work/import-rebinding-reproduction \
  --output experiments/import_rebinding/results/reproduction \
  --lock /path/shared/measurement.lock --blocks 7 --seed 4913

experiments/_work/delta-analysis-env/bin/python \
  experiments/import_rebinding/analyze.py experiments/import_rebinding/results/reproduction
```

Build, matrix work and output directories must be fresh. The build helper verifies the source archive's SHA-256, applies only the recorded patch, uses `cargo --locked`, and records its build. `--offline` is available after dependencies have been acquired. For standalone tests, set `GAIA_IMPORT_NATIVE` to the local `.so` and run `test_rebinding.py`. No global Python package or existing compiler installation is replaced.

Primary implementation source: [Grimp source release 3.17](https://pypi.org/project/grimp/3.17/) and its `rust/src/import_parsing.rs` / `rust/src/import_scanning.rs`; the [upstream project](https://github.com/python-grimp/grimp) is BSD-2-Clause licensed. The accompanying archive hash pins the inspected code. The broader connection is [incremental maintenance of derived relations](https://www.vldb.org/pvldb/vol16/p1601-budiu.pdf); this prototype implements only the bounded binding relation above.
