# Artifact host

Exploratory component. The [transfer research design](transfer-research.md), [HTTP baseline](../../experiments/artifacts/README.md) and [binary framing experiment](binary-framing.md) examine metadata-first immutable retrieval. There is no production artifact service or selected public remote/storage protocol. Existing compiler caches remain separate experiments.

This component would provide access to immutable dependency inputs, toolchains and produced artifacts. It should support lightweight local use and optional remote exchange, with logical identity separate from physical layout.

## Questions to work through

- How are metadata and payload fetched independently, in bulk or by range?
- Which identities and integrity checks cross local and remote boundaries?
- How do retention, deduplication, quotas and bounded maintenance work?
- How can tools share content without assuming the same path layout or process ABI?
- What interoperability is needed with existing artifact/package infrastructure?

The [dependency component](../dependencies/README.md) owns ecosystem interpretation; [compiler tools](../compiler/README.md) produce and consume artifacts. Review the [research findings](../../research/findings.md) before selecting a storage representation. A complete solo workflow should remain usable without provisioning a remote host.

Read the [artifact findings](../../research/artifacts/findings.md) and [next questions](../../research/artifacts/prospects.md) for measured request/byte tradeoffs, offline reuse and the limits of the initial loopback baseline.

The [local pack/index cache experiment](local-cache-research.md) compares shared admission and verified logical access on both transports, with ordinary-file materialization charged separately. It is a cache prototype, not an authoritative repository format.

The [one-connection experiment](pipeline-research.md) distinguishes pipelined independent requests from one known-list request with progressive object records. It retains complete verified cache/consumer costs and identifies cold index and connection boundaries.

The [trusted lock/Python consumer proof](locked-python-research.md) retrieves missing hashes without a remote collection index and runs the prior pinned Django application directly from the retained pack. Name/version discovery stays a separate pinned-catalog lookup.

The [retained binary consumer index](compact-python-research.md) removes repeated logical metadata reconstruction and compares packed/ZIP readers with equivalent per-read SHA-256 and CRC checks. Cold production and complete acquisition remain charged.

The [generic resolved-lock proposal](generic-lock-research.md) compares JSON and lazy binary tables for ecosystem identities, content descriptors and opaque associations/metadata, without imposing dependency-solver semantics.

The [producer-preindexed bundle experiment](preindexed-bundle-research.md) sends payload and portable index as two CAS artifacts for both flat storage and indexed ZIP, retaining equivalent validation and explicitly separating production from receiver work.
