# Index-backed package discovery

Run: `20261029T025706.004897Z`. Status: **complete**.

Exact retained Django REST source/bytecode bundles, sidecars, native extension, app settings and templates from the parent run. No producer rebuild or dependency-source changes. Both controls execute the current worker; bundled cases differ only in discovery. The legacy provider remains available as a measured control.

The indexed provider installs a path-entry finder for its owned bundle paths. It builds regular-package/direct-child tables once from the existing module map, handles misses without filesystem fallback, and supplies pkgutil iteration without reparsing ZIP. Unrelated paths retain normal import hooks. Close removes its hooks and restores prior importer-cache entries where possible. The archive format and payload readers are unchanged.

15 randomized fresh processes per case after one correctness warmup. Warm filesystem cache. Indexed warmups additionally forbid stock ZIP-directory parsing; an untimed legacy negative control proves that guard detects the previous fallback. The guard is absent from timed observations. Medians, ms. Ready includes framework/WSGI initialization and checks; workload additionally includes the DB fixture and first API/admin responses. Full process includes common imports, validation and cleanup. Independent column medians need not add.

| Input | Reader | Discovery | Samples | Ready ms | Workload ms | Process ms | Enumeration calls |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| source | directory | legacy | 15 | 1187.520 | 1254.174 | 1595.055 | — |
| source | python | legacy | 15 | 1188.759 | 1245.507 | 1641.349 | — |
| source | python | index | 15 | 1146.122 | 1207.105 | 1602.318 | 18 |
| source | odin | legacy | 15 | 1179.520 | 1243.508 | 1598.331 | — |
| source | odin | index | 15 | 1153.583 | 1210.021 | 1596.510 | 18 |
| bytecode | directory | legacy | 15 | 331.118 | 363.389 | 703.504 | — |
| bytecode | python | legacy | 15 | 341.122 | 381.115 | 722.563 | — |
| bytecode | python | index | 15 | 313.897 | 345.251 | 695.682 | 18 |
| bytecode | odin | legacy | 15 | 339.421 | 370.765 | 716.333 | — |
| bytecode | odin | index | 15 | 304.682 | 333.559 | 663.651 | 18 |

Every observation matches the parent module origins, executed-code sets, API output and resource hashes, with the same 455 dependency modules and 460 code reads for bundled cases. Payload CRC, one archive lifetime, package versions, admin rendering and zero network checks stay enabled. This app has pure-Python regular packages; namespace packages, native wheels and arbitrary mutable package paths remain outside the loader experiment. Host stdlib/native-extension loading, code-object reconstruction and framework initialization are unchanged. No timings from traces/profiles are substituted into this uninstrumented comparison.
