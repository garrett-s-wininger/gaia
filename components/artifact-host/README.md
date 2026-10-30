# Artifact host

Planned component. There is no artifact service implementation or selected remote/storage protocol yet. Existing local cache files are compiler experiments.

This component would provide access to immutable dependency inputs, toolchains and produced artifacts. It should support lightweight local use and optional remote exchange, with logical identity separate from physical layout.

## Questions to work through

- How are metadata and payload fetched independently, in bulk or by range?
- Which identities and integrity checks cross local and remote boundaries?
- How do retention, deduplication, quotas and bounded maintenance work?
- How can tools share content without assuming the same path layout or process ABI?
- What interoperability is needed with existing artifact/package infrastructure?

The [dependency component](../dependencies/README.md) owns ecosystem interpretation; [compiler tools](../compiler/README.md) produce and consume artifacts. Review the [research findings](../../research/findings.md) before selecting a storage representation. A complete solo workflow should remain usable without provisioning a remote host.
