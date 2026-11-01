# Shared observations, earlier handoff and precise reuse

The [frozen-policy follow-up](generalization/README.md) adds xxHash, spdlog, re2c and curl: 333 output-checked operations, 36 first requests and separate resource diagnostics. Shared serial work improves three selected traces, while re2c exposes expensive no-ops from diagnostic exclusion. The queue helps spdlog, falls back on re2c, and slows curl’s edit trace despite a modest first-request gain. Diagnostic retention, working-set-safe cache admission and handoff CPU now take priority over another scan kernel. These results are separate from the original fixture below.

The [matched refinement](refinements/README.md) implements earlier publication, immutable identity retention and bounded result-history/configuration reuse. The numeric-macro test falls from 14.36 seconds to 272 ms, with 32 of 33 targets reused; Ninja + ccache with the same refined index takes 2.41 seconds. Source-edit editor facts arrive at 126 rather than 292 ms. Summed timed trace operations improve from 20.28 to 4.96 seconds, versus Ninja/index at 8.67 seconds. Full references match throughout; source/header/configuration fixtures and limits are explicit.

The refinement still pays for serial backends on multi-TU editor queries and retains more memory. Its separate identity-caching scan improves 5.68 to 1.28 ms without changing the SHA-256 implementation. These matched numbers belong to that run; they are not added to the earlier studies below.

## What the initial integration established

The [33-TU integration](../../experiments/integration/workspace/results/combined/REPORT.md) connects actual Clang observations, admitted source generations, project declaration queries and a built Ninja executable. All 108 measured operations match full physical object, depfile, executable and query oracles. This remains a controlled build fixture with labelled edits and explicit membership hints for the Ninja control.

| Operation | Shared build/query | Independent cached consumers | Ninja + ccache/query |
| --- | ---: | ---: | ---: |
| Source edit | 535 ms | 529 ms | 653 ms |
| Header edit | 5.47 s | 7.00 s | 6.03 s |
| Configuration change | 28.39 s | 30.21 s | 14.43 s |

These are medians of three blocks. Sharing lowers duplicate CPU work: the header case uses about 5.47 seconds of estimated CPU versus 9.77 seconds for independently cached consumers. Median current persistent-worker PSS is about 191 versus 247 MiB. Those memory samples exclude the controller and transient compiler/linker peaks; Ninja's remaining index worker alone retains less memory.

This is not a uniformly faster replacement. Summed timed operations across each twelve-operation trace have medians of 38.54 seconds shared, 42.59 seconds independent and 25.01 seconds with Ninja + ccache/query. These sums exclude preparation and between-operation validation, rather than representing complete continuous sessions. Conservative configuration invalidation dominates the shared trace. The shared controller also waits for compilation/linking before publishing query results: a source edit's editor result takes 535 ms versus 241 ms independently. That initial controller lacked earlier handoff; the refinement above measures it.

The cache controls differ in a useful way: ccache retains multiple encountered input versions through each trace; the native IR cache retains only the latest result per context. Returning to an earlier optional-header state therefore favors ccache. Configuration changes select a fresh native context and reparse every TU. Neither limitation is a demonstrated performance floor.

## Negative observations are a correctness requirement

The first Ninja control returned a stale direct-cache object after an optional header appeared. That run was rejected. A [controlled diagnostic](../../experiments/integration/workspace/results/negative-cache/REPORT.md) logs the direct hit and verifies that preprocessor mode matches uncached Clang. The corrected comparison uses both a known probe-TU invalidation hint and preprocessor-cache mode for membership changes. Ordinary edits retain direct mode. This is an explicit adapter, not an automatic general negative-dependency importer or a claim about every ccache configuration.

## SIMD benefits depend on layout, density and generated code

The [native-target Odin study](../../experiments/integration/simd/results/native/REPORT.md) compares optimized loops, scalar word tiling, four/eight-lane integer unions and native sparse lists. All query outputs match. The inputs combine an actual captured 402-observation/33-target relation with labelled generated scales; changed-observation sets are generated queries.

| Query shape | Optimized mask loop | Best tested explicit vector | Sparse lists |
| --- | ---: | ---: | ---: |
| Dense 8,192 targets, eight changed observations | 188 ns | 111 ns, four lanes | 22,860 ns |
| Sparse 4,096 targets, eight changed observations | 105 ns | 45 ns, four lanes | 26 ns |
| Sparse 16,384 targets, 64 changed observations | 7,977 ns | 6,947 ns, eight lanes | 1,651 ns |

The dense eight-change vector improves the native loop median by about 1.7×, winning six of seven shuffled blocks. Most of the dense advantage over sparse lists already comes from the bitmask representation; attributing all of it to SIMD would be wrong. Sparse lists remain best on the generated sparse fixtures. Wider vectors do not consistently win.

The captured 33-target mask fits one word. Scalar word tiling takes about 10 ns versus the row loop's 27 ns for eight changes, winning all seven blocks; the explicit vector kernels use scalar tails there. This does not explain milliseconds of complete-workflow latency.

The [generic-codegen control](../../experiments/integration/simd/results/generic/REPORT.md) and [build evidence](../../experiments/integration/simd/builds.json) also show why source vector width is insufficient evidence: the generic eight-lane operation lowers into narrower instructions, while the native build contains actual ZMM operations. Odin object-mode linking additionally requires explicit CPU-feature initialization; the kernels check CPU and OS state before selecting supported modes.

## CPU dispatch helps the actual identity scan without changing its format

The [hash follow-up](../../experiments/integration/hash_dispatch/results/scan/REPORT.md) substitutes OpenSSL's CPU-dispatched SHA-256 helper into the same Clang host. Retained scans fall from 10.35 to 6.06 ms; admitting an unchanged generation and scanning falls from 14.97 to 8.43 ms. Capability-masked library controls take 10.56 and 14.67 ms. All 420 responses preserve exact identities and records; subsequent source changes invalidate correctly in all three backends. Dispatch wins all seven paired block medians for both operations.

These are retained observation/index operations, not full build or startup gains. The full 108-operation build matrix uses the original host. Each backend also pays roughly 13.6–13.8 seconds of initial parsing/index preparation. Crypto instruction dispatch is distinct from explicit integer-vector unions. The measured improvement justifies a CPU-aware hash interface, while caching immutable identities remains a separate way to remove that work altogether.
