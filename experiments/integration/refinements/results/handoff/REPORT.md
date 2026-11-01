# Handoff survives protocol and restoration hardening

Seven edits to the actual production `version.cc` TU compare the measured implementation/client with the hardened path. Every paired object and fact digest agrees, and each pair matches a fresh stock CLI object. All fourteen frontend frames arrive before final build completion.

| Path | Editor receipt | Compile completion |
| --- | ---: | ---: |
| measured | 111.37 ms | 137.58 ms |
| hardened | 113.99 ms | 140.47 ms |

These are single-TU operations with source admission, not full-project editor latency or a full-matrix rerun. They validate the current actual event path without assuming the hardening is timing-equivalent. Error-path and coalesced-frame regressions are separate focused tests.

[Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), [reproduction](../../README.md).
