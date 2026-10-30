# Gaia: source control MVP

Scope: source control is one component of the broader [Gaia platform direction](../../docs/platform.md). This component's accepted requirements remain in force; they do not limit dependency packaging, loading, or compiler integration elsewhere in the effort.

Status: consolidated design. Behavioral contracts below are accepted unless explicitly labeled **Proposal**, **Open**, or **Deferred**. They describe intended behavior, not an implemented system or measured performance.

This document owns the source-control component's product scope and requirements. [OBJECT_MODEL.md](object-model.md) owns proposed logical records and representation options. [MILESTONE_1.md](milestone-1.md) owns the first implementation slice and its acceptance criteria. The [open-decision register](#open-decisions) replaces the earlier running list of discussion questions.

## Purpose and scope

Build the source-control component of the broader Gaia tooling effort. Use Odin for native components. Favor a small understandable implementation, predictable performance, and recovery from mistakes. Add complexity when correctness or measurements justify it.

The complete solo workflow must work offline without account registration or separately provisioned infrastructure. Start with a CLI over reusable native operations. A CLI-managed local service is acceptable if it starts and recovers automatically and remains extremely lightweight. Shared hosting is optional.

Deliver Linux first while isolating platform-specific behavior for later macOS, Windows, and likely BSD support. Code repositories are the initial workload; preserve binary content without requiring specialized asset workflows.

| Full MVP includes | Deferred or outside scope |
| --- | --- |
| First-class linear stacks, including singleton stacks; explicit whole-change checkpoints | File/hunk staging; branching dependency graphs within a stack |
| Automatic working-state preservation, safe switching, restore, and undo | Full editor/forge UI; stable public plugin ABI or runtime plugin loading |
| Private drafts, explicit review publication/updates, human/agent collaboration | Automatic comment relocation and advanced hunk/granular annotation tracking |
| Native landing queue, prefix landing, one native target (`main`) | Native merge-commit authoring, native release-branch/tag workflows |
| Full local checkout; imported Git branches/tags remain addressable | Partial/sparse/virtualized workspaces, binary locking, nested repositories |
| Git source-history import/export and automatic projection using Git protocol exchange | Git-backed native storage, Git-compatible server, dual Git/native landing authority |
| Status, diff, change/stack history, file history, recovery | Advanced search/blame unless separately prioritized |
| Optional externally produced verification records | CI execution, runners, pipelines, agent/test scheduling |

Arbitrary distributed/offline merging of shared review writes is deferred. A shared target requires its authority to accept landing; saving and checkpointing remain available offline. Milestone 1 is a subset of this MVP, not a commitment to deliver every row at once.

## Core vocabulary and identity

| Concept | Meaning |
| --- | --- |
| Repository | Native source/control data and independently stored collaboration metadata. |
| Snapshot | Immutable source namespace state, including any structured conflicts. |
| Working capture | Recoverable saved workspace contents; does not advance review history. |
| Change | Stable identity of one ongoing unit of work. |
| Revision | Immutable proposal: a change, its exact source base, and a snapshot. |
| Stack / stack version | Stable review/work grouping / immutable ordered selection of exact change revisions and base. |
| Integration | Immutable entry in accepted source history, with resulting snapshot and origin. |
| Target | Versioned reference to accepted history; initially `main`. |
| Workspace | An editor's local files and recoverable per-change working state. |
| Publication / candidate / receipt | Exact submitted review / prepared integration result / durable record of landing and its decision evidence. |

Stable entity IDs identify changes, stacks, workspaces, and actors across updates. Immutable typed records use content-derived object IDs. Entity evolution changes versioned references, not existing immutable objects. Storage compaction can move an object without changing its identity.

A revision's **source base** says where its proposal applies. **Editing provenance** says how its drafts were produced. Successive drafts may share one source base; reconciling two drafts does not add merge parents to accepted history. Snapshots contain source state independently of authors, timestamps, workspace ownership, and review state.

Equal encoded objects have equal identity. Whether all logically equal namespaces must yield the same root ID is open. Keep snapshot/index choices replaceable; a generic namespace framework or multiple implementations are not prerequisites for starting.

## Authoring and stacks

### Saves and checkpoints

Ordinary file saves preserve eligible work through automatic working captures, without a message or staging ceremony. Explicit checkpoints create named immutable revisions of the whole current change, including additions, modifications, and deletions. Subsequent saves accumulate working state without advancing the checkpoint or submitted review.

Working captures and unsubmitted checkpoints are author-private, including synchronized copies. They can have descriptions without creating review requests, notifications, discussions, or approval requirements. Capture timing and batching remain implementation choices; unsaved editor buffers require editor cooperation. Distinguish editor-save, locally durable capture, and remote backup acknowledgement.

Checkpointed conflicts are valid saved work but cannot land unresolved. Saving a resolution updates working state; checkpointing creates a new revision. Explicit stack operations can also create derived revisions without making every file save a review revision.

### Dependencies, updates, and grouping

A stack is an ordered dependency sequence. Each revision applies to the exact source state before it. A stack version pins its base and exact revisions; it cannot silently change when a lower change is edited.

Checkpointing a lower change marks affected dependents as needing an update. One explicit local action updates them as a group, preserving prior revisions and working state first. Clean updates proceed automatically; conflicts are recorded and the operation finishes rather than pausing for file-by-file fixes. The old coherent stack remains available. A mixed sequence still based on old inputs must not be presented as an updated coherent version.

Users can continue editing unrelated files, switching changes, saving, and synchronizing conflicted work. Conflicts are source state, not a globally stopped command. File materialization and builds may still encounter unresolved inputs.

A stack has a title and cover description; each change has its own description. A singleton stack and its change share one editable title/description record. Exact cover transitions when adding/removing changes remain open.

Stacks can split into separate review groups without changing constituent change identities or existing source revisions. Splitting `A, B | C, D` preserves C's dependency on B. Review grouping and source dependency are distinct; the upper group cannot land ahead of its required base. Preserve earlier stack versions, descriptions, discussions, and split provenance. Do not copy stack approvals onto a newly created group. Which group retains a stack ID is open.

A resolved, eligible prefix can ship even when later changes are unfinished, unapproved, or conflicted. [Landing correspondence](#partial-landing-correspondence) connects the remaining proposal base to accepted source without needless revision rewriting.

## Source files, paths, and ignores

| Entry | Preserved source state |
| --- | --- |
| Regular file | Exact bytes, including line endings, plus executable status. |
| Symlink | Target bytes, without following the link during capture. |
| Directory | Namespace structure; explicit empty-directory tracking is deferred. |

Do not version ownership, filesystem timestamps, ACLs, or other host-specific metadata. Eligible unsupported entry kinds fail explicitly. Binary contents and symlink target payloads need not be UTF-8.

Repository paths are relative UTF-8 names separated by `/`, with case-sensitive identity and no Unicode normalization or case folding. Reject absolute paths, `.`/`..` components, and reserved internal-storage paths. Unsupported imported names fail explicitly. Validate destination-host naming/collision restrictions before checkout mutations; never silently rename or overwrite colliding entries. Materialization must not escape the workspace through paths or symlinks. Exact reserved names and encoding/length bounds remain open.

Paths identify entries in the MVP, behind an explicit namespace/key interface. Moves change keys; copies can share content without implying persistent file identity. A later ID namespace would also need path-to-ID bindings, identity-aware merge/history behavior, and migration rules. It is not just a type substitution.

Ignore support is required from the start and applies consistently to status, automatic discovery/capture, checkpoints, and uploads. Ignored untracked content must not enter source storage or the upload queue. Already tracked files remain tracked; ignore edits do not silently omit modifications, create deletions, or remove old content from history. The exact tracked-path membership representation and stop-tracking UX remain open.

Always exclude repository internals and credentials from discovery. Preserve ignored local files during switches/restores: relocate safely or stop the affected transition if source would overwrite them. The shared ignore file itself is captured normally.

**Proposal:** one versioned root ignore file plus local-only exclusions; comments, literal paths, directory rules, and a small documented glob syntax. Names such as `.gaiaignore`, escaping, negation/precedence, and nested/global rules are not settled. Do not claim Git-ignore compatibility.

## Collaboration and resolution

Humans and agents must be able to work on one change concurrently. Preserve divergent revisions; never silently choose the last writer. Reconciliation is an explicit local operation and records its inputs. It combines clean edits or produces structured conflicts while leaving earlier drafts recoverable. It does not create native merge commits or implicitly approve its result.

**Proposal:** isolate active editors in distinct workspaces. If drafts have different source bases, align them explicitly before comparing their full states. Simultaneous mutation of one filesystem workspace and the exact divergence UX remain open.

Use deterministic three-way comparison of base/current/proposed entries. Automatically retain identical results or the changed side when the other equals base. Include metadata, type, and deletion state in comparisons. For other cases, use an applicable resolver or retain structured alternatives. Text merging can combine unambiguous edits; no arbitrary winner is selected for binary, symlink, or namespace/type conflicts.

The replaceable resolver interface must accommodate large files and custom tools through immutable content handles, with streaming/range access rather than mandatory whole-file buffers. Tool protocol, selection, normalized repeated-conflict propagation, resource limits, and trust for automatic custom synthesis remain open. Tool execution failure must be visible and preserve inputs; it is not successful resolution. Rendered conflict markers are a presentation, not canonical stored conflict data.

## Review, access, and evidence

### Source and collaboration separation

Source reads, checkout, and source synchronization do not fetch or traverse review records. Descriptions, discussions, approvals, and external verification are independently stored/fetched, with separate subscriptions/caches. A complete native backup includes both stores and their references; they need not run on separate servers.

Small frozen source-history envelopes contain accepted messages, author/committer attribution, and relevant timestamps for logs and Git export. Landing requests pin descriptive versions; landing freezes the envelope. Later draft text edits do not rewrite accepted history. Source author, committer attribution, authenticated requester/authorizer, and delegated actor are distinct.

### Permissions and privacy

Local ownership works without account setup. Shared permissions distinguish source reading, contribution, review, landing, and policy administration. An agent's identifiable delegation names its granting principal, scope, and allowed operations. Editing a stack does not implicitly permit approval, landing, or administration. Use a small fixed capability set first; credentials, revocation, authentication, and role templates remain implementation design.

Enforce permissions on source objects and metadata as well as ref/review transitions and final queue publication. An object ID is not access authorization. Publishing a selected revision exposes its required source dependencies, not every private provenance-linked draft or capture. Publishing an upper change cannot hide its unlanded base. Absence of review metadata differs from metadata not yet fetched.

### Publication and lifecycle

Request review and **Update review** are explicit. They publish exact source and descriptive versions. Ordinary saves/checkpoints and backup leave reviewers looking at the existing submission. Retain earlier submissions and discussions; comments retain original source context. Richer hunk annotations and automatic cross-revision relocation are deferred.

Approvals attach to exact revisions and reviewed context. Rewritten/resolved proposals need their own approvals; do not infer approval from authorship, synchronization, agent participation, or successful merging. A grouping-only split does not invalidate change-level approval when revision/context are unchanged. Exact stack-level approval requirements remain open.

| Action before landing | Effect on pending landing |
| --- | --- |
| Save or checkpoint privately | Existing submitted selection remains unchanged. |
| Update review | Supersede requests for the replaced publication; enqueue the replacement explicitly after policy satisfaction. |
| Withdraw review | Cancel its pending requests. |
| Withdraw approval | Append a withdrawal event; landing must recheck effective evidence/policy. |

Serialize these actions against landing. If withdrawal wins, invalidated publication/evidence cannot be used. If landing wins, report already landed rather than successful retroactive cancellation. Approval used for landed code cannot be withdrawn after landing. Seal its evidence and policy decision; later concerns or revert/corrective changes are new records. Partial landing seals only evidence used for the landed prefix.

Discussion resolution appends an event rather than deleting messages. Shared events are ordered by the authority. Shared offline review writes are deferred; local reading of retained/fetched metadata works offline.

### Solo and external verification

Solo repositories require zero approvals and no checks by default. Their owner can land from a checkpoint without a review or synthetic self-approval. Integrity, resolved-content, authorization, concurrency, and durability checks still apply. Team repositories can configure approval requirements; precise counts/self-approval defaults remain open.

CI execution is wholly external. Gaia can attach results identifying exact revisions or integration candidates, issuer, outcome, and optional evidence links. It does not schedule jobs, run tests/agents, provision environments, or own logs/artifacts. Human review, agent review, and test evidence are distinct. Required evidence gates and richer equivalence/copy rules can follow; the attachment schema is a proposal, not a prerequisite for the local-engine milestone.

## Native landing queue

One native authority owns each target: local for standalone operation, shared when explicitly configured/promoted. Backup connectivity alone does not transfer authority. Standalone landing works offline; a shared target is landed only after its authority accepts it.

Landing is a durable queued request for an exact stack version/prefix, requester, and descriptive selection. The authority prepares immutable integration candidates against the latest accepted target without changing author workspaces. Preserve unrelated target changes; do not overwrite a newer target with an old proposal's full snapshot.

A deterministic conflict-free integration of an unchanged approved proposal may land without fresh human approval. Approval stays on the original proposal; any required integration-specific evidence must cover the exact candidate. Conflict freedom is not proof of behavioral compatibility. Rework/resolution produces a new proposal requiring its own policy satisfaction. Advanced approval reuse across rewritten proposals remains deferred.

Conflicted candidates remain source records and require resolution; they do not advance the target. Users may adopt/resolve them explicitly. Other independent work should remain able to proceed; exact queue scheduling/fairness is open. Enqueue acknowledgement means the request is durable, not landed. Solo operation uses the same queue and normally completes without waiting for reviewers.

At publication, atomically validate expected target generation/head, candidate results, permissions, policy, effective approvals, and unsuperseded/unwithdrawn publication where applicable. Publish one accepted entry per selected change in order, the completed target advance, queue completion, receipt/evidence, landed boundary, and pending Git projection work. Readers see the old target or the complete selected prefix. Retry without duplicate landing; target movement requires a new candidate and correctly scoped evidence.

New native accepted history is linear. Imported history may have multiple parents to preserve Git merge ancestry. A native integration records the validated candidate result, which may differ from the proposal snapshot after integration onto a newer target.

### Partial-landing correspondence

Landing A from `I0 → A → B` creates accepted entry IA and a receipt mapping A's exact revision to IA. If source state is preserved, B can recognize its original base as already satisfied, keeping its revision/approval. This is recorded landing correspondence, not equivalence guessed from equal contents or messages.

If IA includes other target work, or the target later advances, the receipt alone does not make B directly applicable. The queue prepares B against actual accepted source and records any conflicts. Partial landing may split the review/work groups while preserving change identities and lineage; it never silently rewrites the author's workspace. See the [record proposal](object-model.md#landing-records).

**Proposal:** begin with one serial queue per target, explicit state transitions, and no speculative batch testing. Atomic transaction boundaries and policy/evidence version checks still need implementation design.

## Synchronization and Git

### Native synchronization

Separate immutable data transfer from mutable ref advancement. Transfer missing dependencies in resumable validated batches, then publish references only after durable receipt. Saving remains local when disconnected; retries resume automatically once configured connectivity returns.

| Reference | Automatic behavior |
| --- | --- |
| Private backup roots | Preserve captured/checkpointed state, including structured conflicts, under private access rules. |
| User-owned feature/draft ref | Advance in the background when visibility, permission, policy, and expected-version checks pass. |
| Shared accepted target (`main`) | Advance only through its authoritative landing queue. |

A feature “branch” can be a named stack/draft ref rather than another history primitive. Losing a ref concurrency check preserves both versions and pauses that update, without necessarily stopping independent backup transfer. Never force-overwrite a competing ref. Receiving remote state updates knowledge/caches, not checked-out files or local draft selection.

Distinguish local capture, remote durable backup, review publication, queue acceptance, completed landing, and Git projection status. A native conflicted backup is valid even when source is ineligible for shared landing or Git export.

### Git adapter

Gaia owns the source model and storage. Git is an import/export and protocol-exchange target, never the native storage backend. After import, source operations work without Git storage or a Git process. A Git repository maintained by the adapter is isolated interchange state.

Import may seed existing source history, including supported modes, parent relationships, author/committer/messages/timestamps, and selected branches/tags. Imported history has no inferred Gaia stacks or review approvals. Unsupported names/features fail explicitly before publishing destination refs. Exact handling of signatures, submodules, unusual tags, and byte-for-byte identity is open.

Maintain durable mappings scoped to external repository/object format. Repeated exchange is incremental/idempotent. Reuse known unchanged imported/exported identities and retain existing native metadata when recognized; new or externally rewritten commits get no guessed approvals or change identities. A fresh import without native mappings cannot recover Gaia metadata.

Automatically project accepted resolved native history to configured Git refs. Draft/feature-ref export is a possible later explicit policy, not an implication of automatic private backup. Never export rendered conflicts as ordinary resolved source or choose a side just to satisfy Git. Git carries compatible source history only: no Gaia metadata hidden in notes, trailers, private refs, or archive blobs. It is not a lossless native backup.

Run projection at the native target's authority, locally or hosted. Native landing durably queues projection; Git unavailability does not undo it. Retry with frozen envelope data, mappings, conditional ref updates, and separate acknowledgements. Unexpected external ref changes pause the affected projection without force pushing or automatically advancing native accepted history. Incorporating external changes later is an explicit native workflow.

Git tools/libraries versus a native protocol implementation is open. Reuse scheduling/retry/status orchestration, keeping Git conversion/protocol behavior inside the adapter. The two systems do not share a distributed transaction or simultaneous landing authority.

## Durability, recovery, and retention

Explicit checkpoint/landing success means source dependencies and control references are durably recoverable. Persist objects before atomically exposing their roots; failures may leave reclaimable unreferenced objects, never acknowledged roots to missing data. Use expected-version checks and idempotent operations. Exact storage/flush mechanics remain open.

Workspace application is a separate recoverable operation, not an instantaneous atomic replacement of all files. Protect before-state and intent before mutation, then record completion. Preserve unfinished state per workspace/change automatically on switching. Undo creates a new restoring operation while preserving intervening work; reverting accepted code is a new change. Recover interrupted operations without blindly overwriting newer editor changes. Preserve ignored local data too.

Recovery supports file/whole-state restore after accidental edits/deletion, undo of unwanted updates, and restart after interrupted materialization. Machine-loss recovery covers acknowledged retained native backups; local-only bytes have no remote copy. Backup must include references and recovery records needed to find retained content, not just raw objects.

| Data class | Retention contract |
| --- | --- |
| Explicit checkpoints and accepted history | Durable until an explicit removal action/policy; no silent deletion under disk pressure. |
| Automatic recovery captures | Bounded documented lifetime; dense recent history, thinning/expiration later. Preserve latest unfinished state. |
| Incomplete operations, pending sync, required conflict inputs, active readers/writers | Protected while required for recovery, completion, or reconstruction. |
| Rebuildable caches/indexes, expired unreachable data | Bounded caches and safe automatic reclamation. |

Reconstruction dependencies, explicit roots, and provenance links have different lifetimes. Do not permanently retain every automatic capture through strong predecessor links or an immortal operation log. Expiration cannot break retained source; unavailable old recovery inputs must be represented honestly. The [root catalog](object-model.md#roots-and-lifetime) details the proposed mapping.

Automatic maintenance is incremental, recoverable, and bounded in CPU, memory, I/O, temporary space, and write amplification. Users should not need repack/GC/index expertise. Avoid full-history rewrites or requiring a second full repository's space for normal compaction. Reclaim safe caches/expired data first at low space; preserve protected work and promised recovery windows, and report failed writes honestly.

Account separately for retained unique content, recovery, shared/exclusive bytes, caches/indexes, dead space, and temporary peaks. A small checkout can legitimately have large unique history. Whole-file independent objects may store repeated large-file versions less efficiently than Git; measure before claiming smaller repositories. Reusable chunks and segment compaction are implementation options, not selected formats.

## Performance and scale

Use snapshot access rather than replaying historical diffs. Reading an old file must not walk intervening revisions or load review history. History queries need their own indexes; snapshots alone do not guarantee fast ancestry/path-history queries. Indexes/caches are rebuildable, not the only durable record.

After initial discovery, warm status, small edits, and checkpoints should primarily track changed/active paths and affected index nodes. Avoid unconditional full scans, whole-history memory residency, and one host file/watcher per source object/path. Handle watcher overflow, missed events, and restarts with correct rescan/reconciliation. Requested full imports/materialization/output inherently cost their data size. Record prototype limits rather than prematurely implementing every scale optimization.

| Planning tier | Files | Accepted/imported source revisions |
| --- | ---: | ---: |
| Small | 1,000 | 1,000 |
| Established | 10,000 | 50,000 |
| Larger | 100,000 | 100,000 |
| Architectural scale checkpoint | 1,000,000 | 1,000,000 |
| Long-term stretch, outside MVP acceptance | 10,000,000 | 10,000,000 |

The available developer laptop is the baseline. Record CPU, RAM, disk/capacity/free space, OS/filesystem, and power/cache conditions; do not substitute a container's specifications for the laptop. Exact fixtures and numerical thresholds are open. Count draft revisions/captures separately. Vary source bytes, historical changed bytes, file sizes, directory shape, stack depth, workspace/concurrent-writer count, and unfetched review volume independently and together.

Measure cold/warm latency distributions, peak memory, disk footprint, bytes written, background I/O, backlog, and compaction peaks. Separate import/index construction/full checkout/recovery from steady-state status/checkpoint/historical-read/diff/history/update/sync costs. Include service startup/idle resources, ignored build outputs, repeated save/undo, abandoned drafts, binaries, interrupted cleanup, and recovery under pressure. The laptop must remain usable for editing/builds.

Million-scale is an architectural checkpoint toward Sapling/Scalar-class workflows, not demonstrated parity. Ten-million is aspirational and not an MVP gate. Progressive index/history-only fixtures are useful but must not be reported as full materialization/recovery tests. Full checkout alone does not establish competitive huge-repository usability; keep traversal, acquisition, and materialization separable for later sparse/lazy workspaces. Revisit their priority before claiming large-monorepo readiness.

## Subsystems and local deployment

All subsystems expose small replaceable interfaces with explicit identity, ownership/lifetime, failure, cancellation, streaming/pagination, transaction, and durability contracts. Pluggability does not require dynamic loading or a generic storage API for unrelated source/review semantics.

| Boundary | Responsibility |
| --- | --- |
| Source store | Immutable object lookup/write/validation and protected lifetimes. |
| Namespace | Entry-key resolution/enumeration and binding to workspace paths. |
| Repository control | Versioned refs, permissions/policy checks, atomic publication/landing. |
| Workspace | Ignore-aware capture, safe materialization, recovery. |
| History queries | Ancestry/path-history access and rebuildable indexes. |
| Merge/resolvers | Snapshot comparisons, structured conflicts, large-file/custom resolution. |
| Collaboration store | Descriptions, publications, discussions, approvals, verification records. |
| Synchronization/interchange | Durable transfer/status, native ref rules, external adapters/mappings. |
| Maintenance | Bounded indexing, retention, compaction, and reclamation. |

**Proposal:** Odin procedure tables plus implementation context, composed in-process first. A local service can share the same engine as hosted deployment, with embedded storage and local-only IPC by default. No external database, containers, privileged installation, service-manager configuration, or cloud registration should be required to try it.

The CLI should start/reconnect/recover a compatible lightweight process without port/process administration. Concurrent startup must not create duplicate writers. Its lifecycle must support automatic capture/sync even with no foreground command; idle shutdown cannot silently break that guarantee. Lifecycle, diagnostics, version discovery, IPC, and resource budgets remain open.

Promoting a local authority to shared hosting must explicitly transfer target ownership while preserving IDs, history, access-scoped drafts, and pending synchronization. Do not leave both local and remote authorities advancing the same target. The promotion UX remains open.

## Format compatibility

Early experimental builds may skip format bumps for developer velocity, without claiming cross-build compatibility. Mark the format experimental; a matching early marker is not a compatibility promise. Do not silently reset repositories a prototype cannot read.

Declare a stabilization boundary. After it, incompatible persistent-data changes require detectable version/capability changes and deliberate migration handling. This includes source, control, collaboration, recovery, and namespace semantics. Application release numbers and rebuildable cache/index versions need not track the durable format one-for-one.

Unsupported required semantics fail before mutation. Supported migration is restartable, validates before publication, and preserves recovery paths; ordinary opening must not silently rewrite the whole repository. Physical repacking can preserve object IDs, but changing canonical encodings may require new IDs/reference mappings. Account for Git mappings, private data/access, evidence, and pending operations. Version fields and encoding are still proposals.

## Delivery sequence

The accepted first implementation milestone is [Milestone 1: local engine foundation](milestone-1.md): initialization, capture, whole-change checkpointing, historical reads, safe restore, and interruption recovery. It may use explicit capture/in-process calls first and documents those limits; this does not complete automatic capture, service lifecycle, or landing.

The subsequent roadmap remains a planning sequence:

1. Complete the local source loop: automatic preservation, lightweight lifecycle, stack operations/conflicts, and local queued landing.
2. Establish Git interoperability early enough to develop on existing hosting; add native shared transfer/ref control and authentication.
3. Complete collaboration/review publication, approval/lifecycle checks, delegation, and shared queued landing.
4. Validate the full solo and two-user/agent workflows, including prefix landing, lower-change updates, real conflicts, external ref divergence, interrupted synchronization, backup/restore, bounded retention/maintenance, and progressively larger fixtures.

## Open decisions

This is the single register of unresolved choices. Accepted contracts above are not reopened by implementation detail remaining here. Prototype choices can be simple and experimental; all deferred mechanisms are not prerequisites for Milestone 1.

| Area | Still to choose | When needed |
| --- | --- | --- |
| Initial persistence | ID allocation/hash, typed encoding, storage location/layout, single-writer control, flush/journal/publication mechanics | Milestone 1 implementation |
| Capture and ignores | Initial ignore file names/syntax/precedence, tracked membership/stop-tracking; capture barrier and concurrent-file validation; exact reserved names/length bounds | Minimal rules in Milestone 1; richer UX later |
| Recovery and retention | Time/space/thinning defaults, explicit deletion/abandonment/pinning, provenance retention, local ignored-data relocation, backup/restore mechanics | Recovery protocol in Milestone 1; cleanup before full MVP |
| Service and authority | Watcher/rescan lifecycle, IPC, startup/idle budgets, shared promotion and reconnect rules | Automatic local/shared loop |
| Stack control | Concurrent-head selection, split/remainder identity, singleton/multi-cover transitions, partial-landed group presentation | Stack workflow |
| Conflicts/resolvers | Text algorithm, normalized repeated/multi-input conflict semantics, binary/type materialization, tool protocol/limits and automatic-output trust | Update/reconciliation/queue implementation |
| Review/access | Shared credentials/revocation, team approval/self-approval defaults, stack approvals, exact anchors, descriptive-only edits and queued amendments | Team/review workflow |
| Queue transactions | Request states, dependency-aware scheduling/fairness, common policy/evidence/publication checks, receipt schema | Native landing implementation |
| Git | Ref mappings, conditional-update divergence recovery, identity/fidelity contract, signatures/submodules/tag support, tool/library versus protocol implementation | Baseline adapter |
| Scale | Actual fixtures/hardware, numeric latency/memory/space/I/O budgets, changed-path/ancestry index design | Progressive measurement |
| Snapshot representation | Sorted manifests, ordered trees, radix/hash tries, chunked maps/hierarchies; canonical logical-state roots and file chunking | Deferred until constraints/measurements justify selection |
| Compatibility/evidence | Stabilization baseline, version fields/migrations; optional verifier record schema/outcomes/evidence retention | Before durable compatibility promise / optional integration |

## Prior art and reference material

These references inform choices; they do not imply feature parity or measured superiority. Representation-specific papers and options live in [OBJECT_MODEL.md](object-model.md#snapshot-representation-options).

| Source | Relevance |
| --- | --- |
| [Git snapshots](https://git-scm.com/book/en/v2/Getting-Started-What-is-Git%3F), [commit graph](https://git-scm.com/docs/git-commit-graph) | Snapshot access and indexed history queries are separate concerns. |
| [Git packfiles](https://git-scm.com/book/en/v2/Git-Internals-Packfiles.html), [GC](https://git.github.io/htmldocs/git-gc.html), [maintenance](https://git-scm.com/docs/git-maintenance/2.47.1.html) | Compression, retained history, and reclaimable fragmentation have different causes/costs. |
| [Git fast-export](https://git-scm.com/docs/git-fast-export) | Possible incremental interchange mechanism; fidelity limits need explicit handling. |
| [Mercurial phases](https://www.mercurial-scm.org/help/topics/phases) | Publication/visibility states, distinct here from private backup and landing. |
| [CVS](https://ftp.gnu.org/old-gnu/Manuals/cvs-1.9/html_mono/cvs.html), [Subversion](https://subversion.apache.org/features.html) | Atomic updates, directory operations, and optional locking are independent design axes. |
| [Bazaar/Breezy](https://www.breezy-vcs.org/developers/overview.html) | Persistent file identity, deferred behind our namespace boundary. |
| [Jujutsu conflicts](https://docs.jj-vcs.dev/v0.45.1/conflicts/) | Recorded conflict state that permits deferred resolution. |
| [Gerrit labels](https://gerrit-review.googlesource.com/Documentation/config-labels.html) | Future per-evidence classification/copying after trivial rework. |
| [Epic Lore](https://epicgames.github.io/lore/explanation/system-design/) | Central authority/offline capability, binary/sparse workflows, replaceable stores. |
| [Anthropic Scion](https://www.anthropic.com/research/redesigning-source-control) | Server-side/on-demand architecture; our standalone offline requirement differs. |
| [Sapling](https://sapling-scm.com/docs/scale/overview/), [Scalar](https://www.kernel.org/pub/software/scm/git/docs/technical/scalar.html) | Incremental/indexed/sparse approaches informing the long-term scale goal. |
