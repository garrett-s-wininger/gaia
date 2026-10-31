# Where compiler research should go next

The [shared-input comparison](../../experiments/compiler/results/shared-inputs/REPORT.md) removed repeated full publication/admission and unchanged native file digests. The [logical-generation follow-up](../../experiments/compiler/results/logical-inputs/REPORT.md) now tests the validation boundary too. Research should extend scale, lifecycle and workload coverage rather than repeat these completed small-target experiments.

## Follow authoritative collection validation into scale and lifecycle

The [logical-generation experiment](../../experiments/compiler/results/logical-inputs/REPORT.md) now tests this boundary: source edits take 42.25 versus 48.78 ms through the physical adapter, with selective publication against captured/current generations. It preserves tool/output/negative conditions and charges edit admission. Strict physical import remains separate; the API is authoritative only for admitted updates.

Next measure larger namespaces and longer concurrent edit/build traces, not another isolated replay of the completed small-map experiment. The current map copies on updates; persistent structures and indexed directory listings could matter at repository scale. Compare their admission cost, retained generations and total residency, preserving the existing condition reference and current-generation publication rules.

Develop filesystem discovery/import as its own measured adapter, including membership changes and racing writers. A mutable directory must still be imported/verified; merely caching stat results is not an equivalent proof. Preserve tests for optional-file appearance, include shadowing, hidden files and conflicting generations. Establish a generic update transport before selecting an editor/source-control protocol.

## Broaden the C++ graph beyond the integration fixture

The [initial C++ graph](../../experiments/compiler/cpp_graph/results/baseline-seeded/REPORT.md) now covers upstream fmt, a labelled integration library and two executables. It improves source/header/revert operations against Ninja + ccache across three paired blocks while preserving object/link/runtime identity. Source edits compile one TU, header edits four; whole-link history is disabled for both paths. Its six TUs do not establish broad production-project scale.

Next use a larger production graph with generated inputs, configuration changes and wider frontend pressure. Compare genuine fresh object misses separately from repeated-edit hits, preserving baseline cache seeds and recording warm input-authentication state. Explore shared admitted workspace validation across targets: this fixture's common pre/post physical input checks already make no-ops about 24 ms on both paths. Keep SDK discovery/admission, full link inputs and resource accounting explicit. Expand the `.o` handoff contract rather than relying permanently on the documented byte-identical CRT aliases.

## Measure longer traces, bounds and recovery

Run realistic edit sequences across compaction, cache eviction and the full three-candidate result-history horizon. Measure sender, compiler, checker and live lease residency together; serialized cache budgets are not process-RSS limits. Record cold first admission alongside warm updates and explain amortization.

The current shared-input cache is serial and Linux-local. Test native restart, closing publisher descriptors, explicit descriptor transfer, cancellation, orderly failure and diagnostics before selecting a service architecture. Keep active bytes alive through pool teardown and preserve all corruption/integrity guards. Concurrent writers and durable global retention remain separate work.

## Keep remaining optimizations proportional

Profile candidate screening, copied-result hashing/publication, completion records and receipt handoff in complete operations. The checker already makes unchanged decisions around 2.5 ms, while compilation still dominates heavier edits. Native verification-only and verification-plus-emission differ little; a larger rewrite has no demonstrated payoff from row emission alone.

Do not drop code-generation/ABI flags to increase reuse. The current object-only ordered link contract needs expansion for discovered libraries, linker scripts and other implicit inputs before broad result reuse. Standard source/module/diagnostic capture and negative-query semantics belong in the eventual generic tool interface.

The [compiler component](../../components/compiler/README.md) owns product design; the [immutable-input research contract](../../components/compiler/immutable-input-research.md) records the current experimental boundary. These are research prospects, not selected production protocols.
