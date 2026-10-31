# Sealed shared source generations reduce sampled worker memory

A broker admits one immutable sealed `memfd` containing 664 actual Python standard-library sources: 11,957,771 encoded bytes. Four fresh workers verify the same complete pin and use private compiler/interpreter state. The control copies the entire input into private bytes; the candidate retains a read-only shared mapping. Both compile the same 20 selected modules for each of three request waves. Three shuffled blocks give six sessions, 72 worker responses and 1,440 individual module compilation checks.

Each response hashes length-delimited marshalled code objects and must equal the controller's independent compile reference under the same source filenames/options/interpreter. This verifies compiler output identity, not source execution or application readiness. Every worker rejects a mismatched generation. Every session demonstrates that an active lease prevents eviction, then exits workers before releasing leases and reclaiming the generation.

| Mode | Admission median | Four-worker ready | Complete session | Request-wave median | Current aggregate worker PSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| Private input copy | 17.26 ms | 144.43 ms | 410.72 ms | 66.35 ms | 98,734,080 B |
| Shared read-only mapping | 16.55 ms | 111.83 ms | 345.42 ms | 64.41 ms | 62,802,944 B |

The approximately 35.9 MB PSS reduction is consistent with sharing three additional copies of the roughly 12 MB generation. Aggregate worker RSS stays near 136.5–136.8 MB because RSS counts mapped pages per process. These are sequential current worker samples immediately after readiness, not atomic peaks. The producer's payload, controller, kernel accounting and transient compilation allocations are excluded; no total-memory quota or peak-RAM reduction is demonstrated. Logical input-budget tests are separate from memory sampling.

The full session charges generation admission, worker starts, full-pin verification, requests, stale-generation check, normal worker shutdown, lease release and reclamation. Common source discovery/validation/encoding costs another 2.02 seconds outside the session; the reference compile is also separate. Per-wave timing does not establish materially faster compilation from sharing inputs. The useful result is a modest local readiness/session observation and a clear sampled-input-memory benefit, with only three sessions per mode.

Seals prevent write/grow/shrink, deduplication avoids charging identical retained generations twice, and admission rejects excess retained-input bytes. Leases are cooperative broker accounting: arbitrary untracked descriptor duplication is outside this experiment. Workers keep private parse/compiler state; this is neither a shared Python AST nor process snapshotting. Only one generation is exercised in the performance matrix; long-lived multi-generation pressure and process-crash recovery remain follow-up work.

Review after measurement identified a missing broker check binding a returned descriptor to its leased generation. Current code/tests have now been hardened separately; the six-session table remains tied to the measured implementation pin. Its ordinary matching-pin releases are not evidence that the former broker safely rejected wrong-pin, duplicate or foreign descriptor releases. Frozen measured sources are retained locally for replay.

Source pins are verified after the matrix. Three baseline broker tests and six baseline native tests passed before hardening. Four hardened broker tests now pass, including wrong-generation and duplicate descriptor release rejection, alongside eight native host tests and one child-lifecycle test method. The primary performance matrix was not rerun. [Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), [reproduce](../../README.md).
