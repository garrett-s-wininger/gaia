# Artifact host

This component concerns access to immutable dependency inputs, toolchains and produced artifacts. It should support lightweight local use and optional remote exchange, with content identity separate from physical layout.

Transfer, cache and consumer experiments exist. A production artifact service, public protocol and authoritative repository format remain open decisions. The [artifact findings](../../research/artifacts/findings.md) and [prospects](../../research/artifacts/prospects.md) describe measured behavior before choosing those contracts.

## Research boundaries

| Area | Contracts and evidence |
| --- | --- |
| Content identity and retrieval | [Transfer research](transfer-research.md), [generic resolved locks](generic-lock-research.md) |
| Transport and progress | [Binary framing](binary-framing.md), [pipelined requests and progressive lists](pipeline-research.md) |
| Local verified access | [Pack/index cache](local-cache-research.md), including charged ordinary-file materialization |
| Python consumer integration | [Trusted hash locks](locked-python-research.md), [retained binary metadata](compact-python-research.md) |
| Portable production | [Producer-preindexed payload/index pairs](preindexed-bundle-research.md), compared with equivalent ZIP controls |
| I/O sensitivity | [Storage-service study](../../research/storage/README.md), with logical request/byte costs rather than physical-device claims |

These are experimental boundaries, not selected public standards. [Runnable experiments](../../experiments/artifacts/README.md) retain independent verification, offline reuse and negative results.

## Questions to work through

- How are metadata and payload fetched independently, in bulk or by range?
- Which identities and integrity checks cross local and remote boundaries?
- How do retention, deduplication, quotas and bounded maintenance work?
- How can tools share content without assuming the same paths or process ABI?
- What interoperability is needed with existing package and artifact infrastructure?

The [dependency component](../dependencies/README.md) owns ecosystem interpretation; [compiler tools](../compiler/README.md) produce and consume artifacts. Existing compiler caches remain separate experiments. A complete solo workflow should remain usable without provisioning a remote host.
