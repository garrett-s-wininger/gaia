# Real Django loading experiment

Run: `20261029T014251.176632Z`. Status: **complete**.

Published pure-Python wheels, pinned by URL/version/SHA-256. No dependency source edits. Core starts admin/auth/contenttypes/sessions/messages/staticfiles, forms and a tiny ORM app. REST adds Django REST framework and django-filter. Each process initializes WSGI, runs all Django system checks, seeds two rows in in-memory SQLite, serves a filtered JSON request and renders the admin login page through WSGI. No network listener, external service, dependency installation, migrations or production database. I18N is disabled; static assets are checksum-validated but not served.

## Size and input preparation

| Scenario | Projects | Files | Python files available | Unpacked MiB |
| --- | ---: | ---: | ---: | ---: |
| core | 3 | 3739 | 938 | 22.91 |
| rest | 5 | 4018 | 1026 | 25.68 |

Producer extraction, bytecode compilation, stored-ZIP packing and binary index admission are outside consumer clocks and recorded separately. Source and bytecode are separate inputs; every reader within a mode sees equivalent dependency code/resources. Native extensions come only from the host interpreter/stdlib, including SQLite. The existing Odin extension is reused and its hash is checked.

## Startup and first responses

15 randomized fresh `python -I -S -B` processes per case after one correctness warmup. Warm filesystem cache. Medians, ms. Ready includes dependency/provider open, framework/WSGI initialization and system checks. Workload additionally includes the separately reported test-database setup and first API/admin responses. Complete process includes common adapter imports, validation and cleanup; parent JSON decoding is excluded. Independent column medians need not add.

| Scenario | Input | Reader | Ready | DB fixture | API | Admin | Workload | Process | Modules | RSS MiB |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| core | source | directory-stock | 845.520 | 17.922 | 5.660 | 30.309 | 895.401 | 1124.663 | 394 | 55.05 |
| core | source | directory | 825.357 | 18.417 | 5.762 | 34.206 | 879.429 | 1102.313 | 392 | 55.03 |
| core | source | zipfile | 892.943 | 17.708 | 5.937 | 23.175 | 950.041 | 1164.596 | 392 | 60.29 |
| core | source | python | 871.609 | 19.585 | 5.143 | 22.035 | 914.422 | 1141.058 | 392 | 64.93 |
| core | source | odin | 816.583 | 17.226 | 5.129 | 23.387 | 858.966 | 1099.235 | 392 | 65.07 |
| core | bytecode | directory-stock | 227.597 | 3.377 | 2.825 | 15.569 | 249.430 | 459.916 | 394 | 50.33 |
| core | bytecode | directory | 224.063 | 3.039 | 2.908 | 18.612 | 248.870 | 456.830 | 392 | 50.39 |
| core | bytecode | zipfile | 298.225 | 3.276 | 2.405 | 16.795 | 322.183 | 534.510 | 392 | 55.61 |
| core | bytecode | python | 233.551 | 3.503 | 2.574 | 16.676 | 261.893 | 466.098 | 392 | 61.34 |
| core | bytecode | odin | 230.219 | 3.679 | 2.566 | 16.178 | 252.096 | 462.682 | 392 | 61.57 |
| rest | source | directory-stock | 944.116 | 18.013 | 6.477 | 22.448 | 994.153 | 1235.688 | 457 | 57.12 |
| rest | source | directory | 941.540 | 16.452 | 6.599 | 23.122 | 987.116 | 1219.565 | 455 | 57.20 |
| rest | source | zipfile | 1011.654 | 17.866 | 6.604 | 22.797 | 1061.912 | 1314.465 | 455 | 62.86 |
| rest | source | python | 921.557 | 18.494 | 7.675 | 23.738 | 982.859 | 1215.580 | 455 | 68.43 |
| rest | source | odin | 933.540 | 16.767 | 6.893 | 22.564 | 979.978 | 1221.509 | 455 | 68.48 |
| rest | bytecode | directory-stock | 250.889 | 2.721 | 3.660 | 16.007 | 275.898 | 502.109 | 457 | 52.34 |
| rest | bytecode | directory | 248.595 | 2.786 | 4.052 | 19.890 | 273.585 | 490.606 | 455 | 52.32 |
| rest | bytecode | zipfile | 343.545 | 2.910 | 3.826 | 22.674 | 372.085 | 605.698 | 455 | 57.96 |
| rest | bytecode | python | 264.933 | 3.149 | 4.229 | 23.769 | 297.918 | 524.495 | 455 | 65.11 |
| rest | bytecode | odin | 269.367 | 3.520 | 5.027 | 18.604 | 297.538 | 550.195 | 455 | 65.33 |

## Resource compatibility and controls

`directory-stock` uses the filesystem/app-directory template loaders. Every other case uses the same small Django template-loader adapter over `importlib.resources`; `directory` measures that adapter over ordinary files. Thus byte-reader comparisons hold template loading fixed and the stock-directory row exposes adapter effects. Form rendering uses Django’s TemplatesSetting renderer and the installed forms app in every case. Bundled cases do not silently extract dependency templates or code.

`zipfile` uses the common Python reader with ZIP metadata validation on open; `python` uses a pinned binary sidecar/mmap reader; `odin` supplies sidecar/mapped reads through the existing in-process extension. Python still builds module lookup objects and executes the loader, compiler and framework. Sidecar cases use trusted immutable local-admission identity checks, not whole-bundle SHA-256 on every open; reads retain CRC checks. Input byte hashes and all index admission costs are retained. Discovery/enumeration through Python/pkgutil is not replaced by the Odin byte provider.

All dependency module origins/loaders, API output, admin form markers, selected versions, three resource hashes, one provider open, matching code-read counts and zero network attempts are checked. Code/import sets must match across byte-reader controls; the stock-template baseline loads different template-loader code intentionally. Admin HTML contains random CSRF tokens, so semantic markers are checked rather than asserting byte-identical HTML. Detailed per-phase CPU/wall observations, imports, code executions and commands are retained.

The project model, in-memory database, two routes and chosen add-ons are a specified application fixture, not a claim about typical Django deployments. Template resource access is adapted explicitly; arbitrary filesystem consumers, localization, migration discovery, static-file collection/serving, autoreload, namespace packages, native wheels and remote storage are not established by this test. Dependency solving is measured separately; a large framework source tree need not imply a large dependency graph.
