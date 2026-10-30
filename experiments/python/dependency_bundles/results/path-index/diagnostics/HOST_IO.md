# Remaining host opens and reads

Workload-scoped indexed Odin/Django REST bytecode trace. These counts exclude common worker preparation, project fixture files, the dependency bundle/index and the Gaia native extension. Host paths include the standard library, its native extensions and shared libraries.

| Host input | Opens | read/pread calls | Returned bytes |
| --- | ---: | ---: | ---: |
| Standard-library .pyc | 118 | 236 | 2,819,366 |
| Corresponding .py source | 118 | 234 | 2,409,623 |
| Native extensions/shared libraries | 22 | 22 | 22,528 |
| Directories | 12 | 0 | 0 |

Totals: **270 successful opens, 492 read calls and 5,251,517 returned bytes (5.01 MiB)**. Read counts include EOF probes. Directory enumeration additionally makes 24 getdents64 calls. The host group also makes 781 metadata calls, including 270 descriptor fstats. These are syscall counts and returned bytes, not physical storage traffic or elapsed-time attribution.

All **118 .pyc headers have flags=3**, denoting checked-hash caches. Each bytecode path has a corresponding source open. CPython’s SourceLoader.get_code reads source bytes and validates their hash for this cache mode; the relevant local implementation is /usr/lib/python3.14/importlib/_bootstrap_external.py around lines 868–877. All 118 stored source hashes match the current source files and interpreter magic. The source reads are cache validation, not fallback recompilation. This result is specific to this interpreter installation’s cache policy; timestamp caches normally validate with metadata rather than reading the entire source.

Observed imports include asyncio/concurrent.futures, subprocess, selectors, urllib/http, email, logging, zoneinfo, SSL and SQLite support. Django’s version helper imports subprocess; its handlers and asgiref import asyncio; authentication forms import mail support. Importing these modules brings their standard-library dependency closure into a fresh process.

Largest host reads include email/_header_value_parser (.pyc and .py), html/entities.pyc, logging/__init__.pyc, ipaddress.pyc, asyncio/base_events.pyc and subprocess (.pyc and .py). The JSON records exact paths, per-path opens, category totals, header flags and validated source pairs.

The next candidate is an immutable admitted pure-Python stdlib/bootstrap bundle, binding source, bytecode and interpreter identity once. That could remove per-module filesystem reads and repeated source validation while retaining source for introspection. Native extension/shared-library loading remains a separate OS-loader path. No global hash-validation setting is changed by this analysis.

[Full path breakdown](host-io.json)
