# Versioned initialized state for real Django test requests

Prepared runtime reuse helps this small test loop, but native fork branching does **not establish a robust improvement over competent native database reuse**. Its median paired reduction is only 2.35%, with wins and losses across seven blocks. A warm worker is faster under its narrower state-reuse contract; a separate diagnostic demonstrates why that contract is not general heap isolation.

## Complete trace results

Seven randomized blocks run all five modes. Each trace contains ten requests, four generation constructions, a committed-write failure, SIGKILL, recovery, a real method edit, a settings edit and restoration of the original source/settings. Full trace clocks include initial private source creation, generation validation, all template construction/reconstruction, database/media copying, test execution, validation, failure recovery, normal process exit, cleanup and final disposal.

| Mode | Median complete trace | Range across blocks | Largest observed request PSS, including live template |
| --- | ---: | ---: | ---: |
| Fresh Python + native fixture/migrations | 8.469 s | 8.150–9.061 s | 65.0 MiB |
| Fresh Python + native `--reuse-db` | 6.195 s | 5.974–6.730 s | 64.8 MiB |
| Fresh Python + prepared fixture copies | 8.333 s | 7.704–11.188 s | 59.5 MiB |
| Warm Python + prepared fixture copies | 4.943 s | 4.563–6.120 s | 63.4 MiB |
| Forked Python + prepared fixture copies | 6.022 s | 5.735–6.542 s | 104.9 MiB |

Paired comparisons use `100 × (1 − candidate_time/control_time)` within each randomized block, then take the median. They are not ratios of the table's medians.

- Fork versus fully fresh: **28.72% less time**, better in all seven blocks.
- Fork versus fresh Python with fixture copies: **27.04% less time**, better in all seven blocks.
- Fork versus native database reuse: **2.35% less time**, better in five blocks; individual reductions range from **−4.56% to +11.45%**. This small, mixed result does not establish a reliable architectural win.
- Warm versus native database reuse: **20.21% less time**, better in six blocks; reductions range from −2.44% to +29.08%.
- Fork versus warm: **23.85% more time** by paired median; fork is slower in six blocks. The warm path has a narrower isolation contract, explained below.

These are local descriptive measurements, without a population-level confidence claim. The host is a Ryzen AI 7 PRO 450 under a Microsoft Linux hypervisor, with `/tmp` on tmpfs, CPython 3.14.8 and Django 5.2.8. A cooperative measurement lock excludes the other repository thread's participating timing runs; it does not isolate the machine from all other work. Hardware, dependency versions/digests, input source hashes, order and clocks are recorded in [provenance.json](provenance.json).

## Workload and native controls

The target is the pinned **django-todo 2.7.0** source distribution. Each normal request runs one unchanged upstream test and one additional state/generation probe. The timed selection contains three unique upstream tests: moving a task into an allowed list, rejecting a move outside the user's groups, and the application's atomic-transaction utility. This is not a full-suite benchmark. The initial profile additionally runs the upstream fixture test.

The upstream fixture creates three users, two task lists and six tasks. A common adapter adds one real attachment with known contents. Native controls reconstruct that fixture; prepared controls invoke the same upstream fixture function once per generation and copy the resulting closed SQLite database and media tree. The test-project settings and root URL adapter are explicit because those files are absent from the source distribution. Test bodies remain unchanged. [Acquisition manifest](../../acquisition.json), [implementation and reproduction](../../README.md).

The original four-test profile took 2.982 s under `cProfile`, with 1.576 s in PBKDF2 and 1.348 s inside the repeated fixture. With the standard fast test hasher it took 1.275 s, with about 0.494 s in database setup. These intrusive profiles motivate the controls; they are not unprofiled speedup measurements. **Every timed mode uses MD5PasswordHasher**, so password-setting changes do not contribute to the reported architectural difference. [Attribution](attribution.json), [Django testing guidance](https://docs.djangoproject.com/en/5.2/topics/testing/overview/#password-hashing).

The strongest ordinary database control uses `--reuse-db`, retains its schema across the tested non-schema source/settings edits, and keeps verified transaction-test teardown after a failure. After SIGKILL it uses Django's native flush before rebuilding the fixture. Prepared controls rebuild conservatively on every generation change. Normal pytest-django per-test transactions/teardown remain active in all arms. [pytest-django database lifecycle and fixture APIs](https://pytest-django.readthedocs.io/en/latest/database.html).

The warm process restarts after failed/killed requests and all source/settings changes. This avoids relying on repeated `pytest.main()` to discover edited imported modules, a limitation documented by pytest. [pytest invocation documentation](https://docs.pytest.org/en/stable/how-to/usage.html#calling-pytest-from-python-code).

## Trace and validation

| Event | Observed obligation |
| --- | --- |
| Initial and permission requests | Correct upstream outcomes, pristine fixture and attachment |
| Injected failure | Commit a task-title change, write a media file, mutate a module global, then fail |
| Recovery | Original task titles/counts and attachment; no leaked file or module global |
| Forced termination | Perform the same effects, write confirmation, then SIGKILL before teardown |
| Recovery after termination | The same pristine-state assertions |
| Source edit | Change the actual overdue comparison from `>` to `>=`; due-today probe changes from false to true |
| Repeat in edited generation | Correct permissions and edited semantics |
| Settings edit | Set `TODO_STAFF_ONLY`; a nonstaff probe changes from allowed to denied |
| Restore original generation | Original source/settings behavior returns |

All **350 timed requests** match across modes in exit outcome, normal test phase reports and canonical state/generation probes. The trace includes 280 upstream test executions, 280 passing companion probes, 35 injected failing tests and 35 terminated tests. The failure probe verifies autocommit and reads the committed title back before recording its effects. Subsequent requests verify original titles, counts, media content/location and absence of the injected module global. Template database/media hashes remain unchanged after every request. Both server modes reject stale generation tokens before execution: 70 measured rejections in total.

Fresh/fork requests that return normally are waited for and must produce an `atexit` marker; killed requests must not. Their finalization and cleanup costs remain inside the clocks. A separate negative control forks against shared SQLite/media resources and verifies that both committed writes survive: ordinary fork alone does not supply the required resource isolation. [Measured validation](validation.json).

The additional [boundary diagnostic](boundary-validation.json) lets the same mutating request **succeed**. Its next forked request passes with private database, media and heap state. Its next warm request fails specifically on the leaked module global, despite receiving clean database/media copies. Restarting the warm worker restores correctness. Both modes also reject an unannounced source edit during controller admission. The failed warm diagnostic is an expected result, not a hidden failure in the timing data.

Consequently, the timed warm result is valid for the selected successful tests plus explicit restarts after failures/termination. It is not an interchangeable implementation of arbitrary private-heap requests. Fresh interpreters and forked children discard Python heap mutations between requests; a warm worker needs an adequate reset contract or a restart.

## Where the time and memory go

Across the four unchanged successful request positions per trace, pooled median request times are 615 ms for native database reuse, 577 ms for fixture copies with fresh Python, 148 ms for warm reuse and 371 ms for forked requests. These exclude generation rebuild events and are **not** the headline result.

The fork child's pytest portion takes a median 190 ms in those positions. Waiting after its result pipe closes until process exit adds another median **153 ms**. That observed wait includes normal interpreter finalization and process-exit scheduling; it is not an attribution to a particular destructor or garbage-collection algorithm. Replacing normal exit with `os._exit` would change the contract and was not used for measured requests.

Conservative generation preparation/admission consumes a median 2.54 s per fork trace and 2.68 s per warm trace. Native database reuse spends about 28 ms on the corresponding controller source/configuration checks because it can retain the schema through these edits. Warm failure recovery/cleanup adds about 665 ms per trace. Copying the small SQLite/media fixture totals only about **4.3 ms per trace** on tmpfs. Faster bulk copying or device offload would target very little of this workload. Phase medians are independently aggregated and need not sum to the median whole trace. [Derived analysis](analysis.json).

The table's memory values are the largest sampled end-of-request PSS. Fork values add near-contemporaneous child and live-parent PSS, rather than presenting the child's share alone. The largest child's private-dirty sample is 45.4 MiB; this includes new allocations and copied pages, not a pure copy-on-write fault count. Controller memory, whole-system page cache, transient peaks during setup/finalization and unmeasured concurrent processes are outside this memory comparison. Short sequential traces do not establish long-running memory stability or concurrency capacity.

## Interpretation and limits

This gives a concrete, bounded composition of initialized memory, prepared fixtures, private resources, source identity and controller-owned cleanup. It extends the earlier [interpreter snapshot experiment](../../../python/interpreter_snapshots/README.md) and [prepared database study](../../../testing/managed/README.md) with real upstream tests and generation/failure handling. It does not demonstrate a new mechanism outperforming native lifecycle APIs.

The next architectural question would be **how narrowly initialized state can be invalidated without reusing stale behavior**, and which successful operations can truthfully declare a reset contract. This is an unmeasured follow-up, not a recommendation to layer another universal snapshot runtime over the current result. The implemented fork composition already supplies the native isolation control for that question.

Only one small application, three timed upstream tests, one SQLite connection, a tiny fixture and sequential requests were measured. Dependency installation/acquisition and one-time provenance hashing are outside request clocks. Dependencies are held fixed throughout the experiment; installed Python/extension/metadata identities are checked before/after, while package data and system libraries are assumed fixed. Private app/harness identity checks are charged. Clock/entropy-sensitive application behavior beyond the explicit date probes, schema-changing tests, arbitrary native I/O, subprocesses, external database servers, threaded runtimes and GPU/NPU contexts are not covered. Bytecode writes and pytest's result cache are disabled uniformly to keep immutable source generations and writes explicit; this is not a survey of ordinary developer configurations.

The Python audit hook is a diagnostic guard, not a sandbox against arbitrary code. No reflink, persistent-storage durability result, universal runtime, compiler acceleration or POSIX-free implementation is claimed.

Evidence: [summary](summary.json), [raw identity](raw-identity.json), [ignored local observations](results.json), [provenance](provenance.json), [validation](validation.json), [boundary diagnostic](boundary-validation.json), [phase/pair analysis](analysis.json), [attribution](attribution.json). Raw observations remain local and ignored; their identity is also registered in the repository evidence manifest.
