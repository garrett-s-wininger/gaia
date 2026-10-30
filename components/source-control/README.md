# Source control

The MVP design is agreed; implementation has not started. The first deliverable is a small local engine that proves source capture, checkpointing, historical reads and recovery before collaboration infrastructure is added.

## The intended experience

Work is organized into first-class stacks, including a single-change stack. Private checkpoints should be easy to make without preparing a review. Review records are fetched separately so ordinary source access does not pay for them.

Local updates are explicit and preserve work. Conflicts can remain represented while the user continues elsewhere. Landing goes through a native queue, rather than making people repeatedly rebase and retry. A partial stack can land and leave the rest available for further work.

Solo use is complete and offline. A local service may be managed automatically by the CLI; shared hosting is optional. The native model is independent of Git storage, with compatible source history imported/exported through an adapter.

## Read the design

- [MVP design](design.md): accepted behavior, boundaries and open decisions.
- [Object model](object-model.md): proposed records and representation alternatives.
- [First milestone](milestone-1.md): the local-engine implementation slice and acceptance criteria.

Those documents retain the agreed contracts. Record layouts and implementation choices explicitly marked as proposals remain open. The [platform direction](../../docs/platform.md) covers the broader effort; editor, compiler execution and artifact hosting have separate component homes.
