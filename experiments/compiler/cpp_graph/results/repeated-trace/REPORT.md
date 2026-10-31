# Preserved repeated-history C++ graph trace

Run `20261031T033433.890772Z`. Three paired blocks over the same real fmt plus labelled six-TU integration fixture as the [baseline-seeded comparison](../baseline-seeded/REPORT.md).

This initial run retained **edited compiled objects across blocks**. Source/header operations compile one/four TUs in block zero, then **zero** in blocks one and two because both object caches already contain those edited variants. Its medians therefore describe a repeated edit/history trace, **not ordinary fresh source/header compilation**. The corrected baseline-seeded run is the primary fresh-edit result; the observations here remain intact.

| Repeated trace, milliseconds | Ninja + ccache | Programmatic host | Host paired wins |
| --- | ---: | ---: | ---: |
| No-op | 23.10 | 23.41 | 1/3 |
| Repeat source variant | 71.67 | 54.85 | 3/3 |
| Repeat header variant | 72.57 | 57.63 | 3/3 |
| Revert | 70.65 | 56.24 | 3/3 |

The first source operation is 416.17/297.31 ms and the first header operation 433.70/376.16 ms for Ninja/host. Those are single observations and are not pooled with the two subsequent historical hits as fresh-edit evidence. All changed operations still relink three dependent targets; whole-link history restoration is disabled for both controls.

Independent CLI references, object/public-output hashes, runtime results and all four original-versus-aliased CRT link proofs pass. The same 1,363-file SDK view, 63 external link/tool pins, bounded private contexts and pre/post guards apply. [Summary](summary.json), [validation](validation.json), [provenance](provenance.json) and [helper tests](correctness-tests.txt) preserve portable evidence; exact raw observations and the original pre-seeding driver snapshot stay ignored and separately identified. The original frozen driver is intentionally older than the current default baseline-seeded runner.
