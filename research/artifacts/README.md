# Artifact transfer

The artifact track examines how tools obtain immutable inputs and outputs without coupling content identity to filesystem layout or requiring a server administrator for solo use.

- [Findings](findings.md): what the HTTP baseline and matched binary comparison establish.
- [Prospects](prospects.md): what to measure next.
- [Shared data and lifetimes](followthrough.md): demand admission, growing caches and direct metadata queries across Python, Odin and Node.
- [Producer-preindexed bundles](../../components/artifact-host/preindexed-bundle-research.md): portable two-artifact flat/ZIP plans, receiver binding and complete-operation near parity.
- [Generic resolved locks](../../components/artifact-host/generic-lock-research.md): opaque package identities, content associations and matched JSON/binary acquisition costs.
- [Retained binary consumer metadata](../../components/artifact-host/compact-python-research.md): matched SHA-256/CRC pack and ZIP readers, setup versus full installation cost.
- [Hash lock to real Python](../../components/artifact-host/locked-python-research.md): direct packed imports/resources, complete acquisition/install/startup and exact discovery boundaries.
- [Pipelining and progressive lists](../../components/artifact-host/pipeline-research.md): one-connection request windows, known-index batches and progress versus full completion.
- [Local cache experiment](../../components/artifact-host/local-cache-research.md): verified logical access, immutable indexes and explicitly charged file materialization.
- [Binary format experiment](../../components/artifact-host/binary-framing.md): bounded message layout and explicit compatibility limits.
- [Research design](../../components/artifact-host/transfer-research.md): ownership, identity, metadata/payload separation, recovery and open decisions.
- [Experiments](../../experiments/artifacts/README.md): runnable loopback comparison and correctness tests.
- [Run index](experiments.json): portable evidence locations.

This is transport research. Dependency resolution, compiler execution, review metadata and package trust policy keep their own schemas and responsibilities.
