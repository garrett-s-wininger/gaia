# Share immutable source facts while preserving private workspace state

Four scripted actors consume sixteen actual CPython source files totaling 1,005,525 bytes. Each actor admits four private edits and queries detached AST names plus actual Python parse/compile validation. Five blocks verify all 240 edited-state identities and actor-specific names against equivalent operations across the three arrangements.

| Arrangement | Initialization median | Init + edits/queries median | Complete cycle including physical cleanup |
| --- | ---: | ---: | ---: |
| Materialized namespaces, private fact caches | 1,733.57 ms | 2,135.38 ms | 2,137.54 ms |
| Hardlinked namespaces, shared content/fact cache | 438.49 ms | 940.09 ms | 942.61 ms |
| Logical private overlays, shared content/fact cache | 360.85 ms | 734.49 ms | 734.58 ms |

The strong hardlink/shared-cache control already captures much of the benefit. Ordinary-file namespaces provide a compatibility interface that the logical provider omits; this is not free filesystem access for unchanged tools. Every arrangement trusts explicit admitted edits, rather than discovering unreported writes. All actors live in one provider process and follow the same ordered trace; this does not compare four independent parallel process heaps or complete AI agents.

Private edits use atomic replacement over immutable hardlinks, preserving the base file. A lock serializes expected-generation update/publication: concurrent updates with the same expected generation have one winner, older captures remain readable, and stale results cannot become the current publication. These are bounded in-memory state tests, not a durable multi-client service protocol.

Logical cached payload counts are 5,367,908 bytes for private caches versus 2,351,333 for shared caches; input Python bytes can already share object identity, so these counts are not unique allocation or physical-memory claims. A separate [fresh-process instrumented diagnostic](memory-diagnostic.json) measures roughly 48.6 MB high-water RSS for private caches versus 46.4/46.6 MB for the shared modes. Traced Python peaks are about 12.2 versus 11.5 MB. Transient parsing/interpreter costs matter, and this is not a long-lived memory bound. Instrumented runs are excluded from latency.

The bounded trace retains old changed-result cache entries; eviction, lease accounting and many concurrent source generations remain open. File-footprint collection and exact-output oracles are outside operation clocks; cleanup is separately charged. [Reproduction](../../README.md), [summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), ignored [observations](results.json).
