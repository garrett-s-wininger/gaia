# Editor

Planned component. There is no editor implementation or agreed editor MVP yet.

The design space includes editing working content, human/agent collaboration, conflict presentation and access to compiler diagnostics/results. Source-control capture and recovery should provide useful foundations without requiring the editor to own repository history or review policy.

## Questions to work through

- What is the editable content model, and how does it connect to immutable snapshots?
- How can a human and agents work concurrently without losing edits?
- How should deferred conflicts and safe updates appear in the editing experience?
- How are compiler requests, diagnostics and artifacts associated with the content the user sees?
- What belongs in extensions, and what interface lets them participate?

Text storage, rendering, extension architecture and milestones remain open. Relevant starting points are the [platform direction](../../docs/platform.md), [source-control design](../source-control/design.md) and [compiler research](../../research/compiler/README.md).
