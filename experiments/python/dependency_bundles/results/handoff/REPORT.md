# Mapped bytecode handoff experiment

Run: `20261029T035745.805340Z`. Status: **complete**.

All cases use the same newly compiled Odin/C bridge, admitted dependency and stdlib archives/indexes, local immutable admission, per-read CRC, magic/flags/source-hash checks and code-type/origin checks. No payload format or interpreter modification.

* bytes: copy mapped entry to owned Python bytes, then slice off the 16-byte header.
* view: same entry copy, then use a memoryview to avoid the header-slice copy.
* native: CRC/header validation and CPython unmarshalling directly from the mapped range; no intermediate whole-entry/body bytes without audit hooks. With hooks, an owned audit payload preserves marshal.loads notification and rejection (the app has a hook). Code objects still allocate. The GIL stays held, no borrowed mapped view escapes, and returned code survives reader close.

15 randomized fresh processes per mode and workload, after correctness warmups. Warm filesystem cache; micro and application runs are separate. Compilation is outside consumer timing. Full application clock includes mount/setup; full process includes common bootstrap and identical validation.

| Workload | Handoff | Samples | Decode/ready median ms | Workload median ms | Full process median ms | Primary min–max ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| decode | bytes | 15 | 129.778 | — | 585.041 | 107.071–175.434 |
| decode | view | 15 | 131.638 | — | 595.317 | 118.455–158.495 |
| decode | native | 15 | 123.606 | — | 590.449 | 109.751–147.899 |
| application | bytes | 15 | 460.488 | 513.238 | 982.167 | 425.777–517.822 |
| application | view | 15 | 474.811 | 523.329 | 988.263 | 425.413–516.026 |
| application | native | 15 | 453.456 | 498.628 | 954.690 | 379.561–500.044 |

The decode diagnostic opens both readers before its decode clock, then loads and retains 578 code objects without executing modules. It replays the application’s 460 dependency executions as a first-seen ordered multiset (repeats adjacent), followed by 118 stdlib modules in manifest order. It checks structural code equality and filenames against the bytes control after closing the timed readers. Its full process includes that reference decode; only decode time isolates the handoff. It is not an import/startup substitute.

Every application checks identical dependency origins/execution sets, resources, responses, stdlib snapshot identity/origins, source inspection and zero network events. Counters must confirm all 460 dependency and 118 stdlib code loads use the selected handoff. Native extensions and unbundled modules/data keep their existing loaders. Timing spread is retained; compare within this run rather than against earlier absolute timings.

## Interpretation

| Workload/clock | Native reduction of medians | Native faster in trial blocks |
| --- | ---: | ---: |
| decode/decode_seconds | 4.76% | 9/15 |
| application/ready_seconds | 1.53% | 9/15 |
| application/workload_seconds | 2.85% | 11/15 |
| application/process_wall_seconds | 2.80% | 11/15 |

Small differences with broad ranges and inconsistent block wins do not establish a stable startup improvement. The memoryview-only variant has worse medians here. The native variant remains opt-in; bytes stays the default. Native fusion changes both intermediate copying and Python header-validation overhead, so even a stable gain would not measure copying alone. The application audit hook also retains one owned payload copy inside CPython. No syscall reduction or bytecode-format change is expected from this handoff test.
