# Prepared execution helps an actual upstream test subset

The installed CPython `difflib`, `statistics` and `fractions` documentation tests provide 189 actual upstream examples per complete module pass. Nine requests perform three passes per session. The same Decimal context is supplied in every arrangement. Five blocks contain 8,505 successful measured example attempts.

| Arrangement | Complete nine-request session median |
| --- | ---: |
| Fresh interpreter for every request | 1,272.48 ms |
| Existing doctest API with a supplied batch | 203.08 ms |
| Retained process with online request/reply | 215.49 ms |

The existing batched API is slightly faster than the online wrapper. Retaining modules/framework initialization helps relative to repeatedly launching interpreters, but this is not a new snapshot algorithm or a win over competent batch execution. Normal shutdown is included.

Each request binds to the source identity admitted when its module was loaded. A changed on-disk fingerprint or a different supplied generation is rejected rather than blessing stale loaded code. A focused mocked-fingerprint regression checks that boundary without mutating system files. A deliberately failing example is followed by successful real examples in the same process. All measured source pins remain unchanged across the run.

This is a real upstream documentation-test subset, not the full CPython regression suite or a production application. Doctest copies example globals, but no proof of arbitrary mutable framework/database/network reset follows. Source-generation changes require a new supported module/session policy; hot reload is not implemented. [Reproduction](../../README.md), [summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), ignored [observations](results.json).
