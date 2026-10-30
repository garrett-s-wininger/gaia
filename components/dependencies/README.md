# Dependencies

This component concerns selecting dependency versions, admitting their contents and making those contents available to tools. Selection and loading are separate operations and should be measured separately.

The implemented evidence is Python-specific: loader/resource integration, retained archive indexes, compact metadata and a local reference resolver. It does not establish a universal package format, a complete installer, an Odin solver or a remote repository protocol.

Read the [Python findings](../../research/python/findings.md) and [prospects](../../research/python/prospects.md). The original experiment plans live beside the research: [loading/formats](../../research/python/designs/dependency-formats.md) and [resolution](../../research/python/designs/resolution.md).

## Questions for a broader design

- What is an immutable dependency input, and which ecosystem rules determine its identity?
- Which metadata can be queried without fetching or extracting the payload?
- How should tools access names, ranges, resources and optional inputs in bulk?
- What compatibility materialization is required, and who pays for it?
- How are target/toolchain configuration, provenance and integrity represented?

The [artifact host](../artifact-host/README.md) would provide storage/access; dependency adapters interpret ecosystem meaning. The [compiler component](../compiler/README.md) consumes admitted inputs. These are proposed boundaries, not finalized protocols.
