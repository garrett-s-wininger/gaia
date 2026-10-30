# Milestone 1: local engine foundation

Scope: source control is one component of the broader [Gaia platform direction](../../docs/platform.md). This component's accepted requirements remain in force; they do not limit dependency packaging, loading, or compiler integration elsewhere in the effort.

Status: accepted milestone scope; implementation details below are proposals unless already established in [DESIGN.md](design.md) and [OBJECT_MODEL.md](object-model.md).

## Outcome

On Linux, a developer can initialize a local repository, capture eligible saved files, create explicit checkpoints, read earlier source directly, and restore it safely after edits or process interruption. Everything works offline with no separately provisioned service or account. Native code is written in Odin.

This milestone validates persistence and recovery. It is a subset of the full local-source-loop MVP milestone; it does not claim complete review, stack, synchronization, or large-monorepo readiness.

## User-visible slice

Exact command names are provisional. Provide a thin CLI over reusable engine operations:

1. Initialize/open a repository with experimental-format identification and workspace identity.
2. Capture eligible saved workspace state, applying the agreed path/file semantics and initial ignore support.
3. Inspect changes relative to the selected checkpoint and identify the captured state.
4. Checkpoint the complete current change with a message. Represent it as a single-change stack from the start, without implementing stack manipulation yet.
5. List retained checkpoints and read a file from an exact historical revision without changing the workspace.
6. Restore selected files or a complete captured state, automatically preserving current eligible work first.
7. Inspect recovery points and recover an interrupted local operation.

An explicit capture entry point is acceptable for the first engine slice. Automatic save watching, background scheduling, and CLI-managed daemon lifecycle follow after this persistence path works. Do not describe explicit capture as completion of the agreed automatic-save MVP behavior. Engine operations may run in-process initially; keep service lifecycle outside the persistence API.

## Engine responsibilities

| Boundary | Required behavior in this milestone |
| --- | --- |
| Repository control | Stable entity IDs, versioned references, explicit checkpoint roots, current working state, and expected-version publication. |
| Immutable object store | Write/read/validate typed content, namespace/snapshot, and revision records by object ID. Detect absent or corrupt objects explicitly. |
| Namespace/workspace | Capture paths, regular bytes/executable status, and symlink targets; apply ignores and materialize safely. |
| Checkpointing | Publish durable source plus pinned message/provenance records; return success only after the accepted durability boundary. |
| Recovery | Protect before-state, record operation intent/result, detect interruption, and preserve newer edits during recovery. |
| Inspection | Enumerate retained checkpoints and read historical source without loading review metadata or replaying earlier revisions. |

Choose the simplest viable physical representation. Whole-file content objects and a straightforward snapshot index are acceptable starting points; exact tree/index selection, content chunking, segment optimization, and canonical logical-state roots remain deferred. Record shortcomings rather than complicating the implementation in anticipation of every scale tier.

The initial ignore syntax, ID/hash encoding, local storage location, and transaction/journal mechanism need concrete implementation choices. Document those choices as experimental and keep interfaces small. Do not introduce a dynamic plugin framework or multiple storage implementations to prove pluggability.

## Correctness and recovery acceptance

- Changes to bytes or executable status produce correct new state; prior checkpoints remain unchanged. Symlinks are captured as links, without traversing their targets.
- Ignored untracked files never enter captured source. Unsupported eligible entries and names produce actionable errors. Repository internals are excluded from discovery.
- A file added, modified, or deleted after a checkpoint can be restored from retained source, while the pre-restore working state remains recoverable.
- Restoring a snapshot never silently overwrites ignored local data or traverses a symlink outside the workspace. Validate the affected namespace before mutation, and handle races through the operation protocol rather than relying on preflight alone.
- Interruption before reference publication exposes no incomplete checkpoint. Interruption after acknowledged publication leaves the checkpoint readable on restart.
- Interruption during restore is detected, and protected states remain recoverable. Preserve edits made since the operation started rather than overwriting them during recovery.
- Concurrent writers cannot silently lose a reference update. A simple local single-writer mechanism with explicit busy/retry behavior is sufficient initially; distinguish it from future concurrent workspaces.
- Failed writes, missing/corrupt objects, and low-space errors do not report successful capture/checkpoint/restore. Preserve existing readable state where possible.
- Automatic capture roots do not form a permanently strong chain of every preceding capture. Retention roots and provenance follow their declared semantics, even before automatic reclamation is enabled.

Use meaningful integration tests over temporary repositories and deterministic failure injection around object durability, reference publication, and workspace mutation. Process-kill/restart tests exercise recovery. Do not equate those tests with demonstrated resilience to every power-loss/storage failure; the implementation must also specify and review its flush/ordering contract.

## Performance evidence

Start with small and established-project fixtures and the actual available hardware. Record initialization/capture, checkpoint, historical file read, restore, and recovery latency, along with peak memory, disk footprint, and bytes written per small change. Measure cold and warm conditions separately where practical.

Report whether a checkpoint rewrites a full manifest or only changed records; retain that evidence when revisiting the snapshot representation. Repeated unchanged captures should reuse identical content objects. Measure repeated small edits to a large file to expose whole-file storage costs early. Do not claim million/ten-million-scale support from this milestone; those remain progressive architectural checkpoints.

## Explicit follow-on work

Automatic save capture and lightweight service lifecycle; local landing/integration queue; multi-change stack update/split and human/agent reconciliation; normalized structured-conflict propagation; Git import/export and automatic projection; native remote synchronization; review publication/approvals/delegation; automatic recovery-history expiration and compaction; larger benchmark tiers.

Do not enable destructive reclamation before its reachability and retention rules are verified. Absence of automatic cleanup in this engine milestone is a documented limitation, not a replacement for the accepted bounded-maintenance MVP requirement.

## Done when

The offline local flow works from a fresh repository, retained historical states remain readable across restart, safety/recovery acceptance checks pass, and measured storage/performance limitations are documented. The result should provide a small reliable engine to extend, without selecting infrastructure or advanced algorithms prematurely.
