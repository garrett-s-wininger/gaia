# Compilation became faster; stock development settings still won

Changing the machine-code policy reduced actual changed-file compilation time by **17.0% and 20.5%** versus stock `-O2`, while separately emitted optimized LLVM IR remained byte-identical. The candidate uses existing LLVM fast instruction selection and disables optimized register allocation. It won all fourteen paired compile comparisons against `-O2` across two real algorithm edits.

That is a demonstrated compile-time tradeoff, not a new compiler algorithm or a uniformly better backend. The resulting eight-suite test execution was about **51% slower**, and the changed object's size grew roughly **2.4×**. Stock `-O0` gave the shortest edit-to-test time for both tested execution demands, beating every other policy in all paired comparisons. Stock `-Og` also had better complete-operation medians than the custom policy. This run does not justify selecting the custom policy for Gaia.

## Uninstrumented complete requests

Each request writes a genuine edit to Zstandard 1.5.7's `zstd_lazy.c`, compiles it, links it with unchanged `-O2` library objects, launches the executable, and runs 168 compression/decompression cases. These are medians in milliseconds across seven shuffled blocks. Compile time is a subspan of the short complete operation. Phase medians are independently aggregated and need not sum to the endpoint median.

| Edit | Policy | Compile | Compile/link/one suite | Eight suites alone | Build + eight-suite component sum |
| --- | --- | ---: | ---: | ---: | ---: |
| Halve search budget | `-O0` | 472.49 | 586.89 | 629.21 | 1,136.79 |
| Halve search budget | `-Og` | 1,572.71 | 1,634.79 | 188.05 | 1,795.77 |
| Halve search budget | `-O1` | 1,719.31 | 1,780.75 | 192.13 | 1,946.10 |
| Halve search budget | `-O2` | 2,045.27 | 2,104.13 | 183.46 | 2,259.54 |
| Halve search budget | `-O2`, fast machine passes | 1,697.90 | 1,771.56 | 277.70 | 2,019.03 |
| Increase lazy depth | `-O0` | 475.43 | 593.68 | 645.98 | 1,157.63 |
| Increase lazy depth | `-Og` | 1,561.00 | 1,625.41 | 203.02 | 1,800.68 |
| Increase lazy depth | `-O1` | 1,651.99 | 1,720.22 | 202.82 | 1,890.75 |
| Increase lazy depth | `-O2` | 2,034.50 | 2,095.89 | 193.08 | 2,267.56 |
| Increase lazy depth | `-O2`, fast machine passes | 1,618.42 | 1,691.67 | 292.08 | 1,939.50 |

The custom policy reduces the short complete-operation median by 15.8% and 19.3% against `-O2`, with seven of seven paired wins for each edit. It also wins all paired eight-suite component sums against `-O2`, but loses all short comparisons against `-Og` for the search-budget edit and five of seven for the lazy-depth edit. Its comparison with `-O1` is mixed. The experiment retains all blocks, including several large timing outliers; it provides no general ranking of `-Og` versus `-O1` across projects.

The last column substitutes a separately measured eight-suite execution span for the short suite. It is a component sum, not an uninterrupted measured build-and-eight-suite endpoint. The short suite ran before it and can affect cache warmth. One and eight suites are explicit demand scenarios, not observed user behavior, and no unmeasured crossover is asserted.

All policies use the same pinned compiler and fixed dependencies. No compiler cache is enabled: this experiment measures forced genuine compilation misses, not repeated-version history hits or a build-system replacement. Only the changed TU's policy varies. Source discovery, dependency graph scheduling and clean preparation are outside these warm operations. Link spans are roughly 34–36 ms.

## What the profile says

Separate intrusive diagnostic traces on stock `-O2` place approximately 2–3% of compiler time in the frontend, 51–55% in LLVM optimization and 42–46% in machine-code passes for these edits. The frontend is not the main opportunity here. These figures belong to one profile per edit/policy, not to the unprofiled timing matrix.

For the search-budget edit, observed stage times were:

| Diagnostic stage | Stock `-O2` | Fast machine policy |
| --- | ---: | ---: |
| Frontend | 66.5 ms | 64.6 ms |
| LLVM optimizer | 1,168.3 ms | 1,266.0 ms |
| Machine-code passes | 1,044.7 ms | 512.8 ms |

The corresponding machine-code stage for the lazy-depth edit was 1,001.1 versus 521.0 ms. The candidate's optimizer time varied substantially in that diagnostic run; its whole instrumented compile was slightly slower despite the cheaper machine stage. This is why the conclusions use shuffled, uninstrumented endpoints rather than subtracting profile components to predict a speedup.

Named pass events corroborate the intervention in the search-budget profile: instruction selection took 288.7 versus 85.9 ms; greedy register allocation accounted for 135.9 ms in the control, while fast register allocation accounted for 16.9 ms in the candidate. These are inclusive diagnostic event aggregates. Pass-manager wrappers and their children overlap and must not be summed. Many specialized functions contribute; the largest individual stock machine-code function is only a small part of the module total. [Full derived attribution](attribution.json), [phase/profile summaries](profiles-summary.json).

## Cost paid in the generated program

| Edit | Stock `-O2` object | Fast machine object | `-O0` object |
| --- | ---: | ---: | ---: |
| Search budget | 190,000 B | 450,392 B | 1,180,040 B |
| Lazy depth | 190,368 B | 451,848 B | 1,179,272 B |

Eight-suite execution for the candidate is 1.51× the stock `-O2` duration for both edits. Stock `-O0` executes those suites about 3.3–3.4× slower than `-O2`, but its much smaller compilation cost still wins both measured demand scenarios. Longer-lived artifacts, different tests, debugger requirements and cache pressure could change the choice. Identical optimized IR does not guarantee identical machine-code performance or size.

## Correctness and reproducibility

All 70 measured compilations were linked and executed. All **105,840** short/long-workload round trips checked decoded bytes exactly, and every published compressed-frame archive matched the current edit's stock `-O2` reference byte for byte. Both edits changed compressed output relative to the unedited source. Per-policy object identities were stable across blocks. The two level-two policies' separately emitted optimized IR matched exactly for each edit.

The harness covers four relevant compression strategies, row matching, dictionaries, boundary sizes, source text and deterministic generated inputs. It is a constructed regression workload using real upstream APIs, not the upstream conformance suite. Streaming, multithreaded compression, sanitizers and debugger fidelity were not tested; assembly and legacy formats were disabled consistently. `-Og` ran without debug information. No general compiler-equivalence or production-readiness claim follows.

Recorded preparation took about 9.88 seconds and includes archive extraction, unchanged library/harness compilation and reference operations. It excludes the subsequent diagnostic profiling. Preparation is not charged to the warm incremental endpoint. Compiler/library/source identities and stable artifacts were verified after the run. The advisory lock excludes cooperating timed cases only; unrelated host activity and preparation remain possible. The run contains visible outliers rather than an isolated-machine claim.

[Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identities](raw-identity.json), and [implementation/reproduction](../../README.md). Raw observations and four complete compiler traces remain ignored and are registered in the repository evidence manifest.
