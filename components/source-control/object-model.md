# Gaia: logical object model

Scope: source control is one component of the broader [Gaia platform direction](../../docs/platform.md). This component's accepted requirements remain in force; they do not limit dependency packaging, loading, or compiler integration elsewhere in the effort.

Status: consolidated record proposal implementing the accepted contracts in [DESIGN.md](design.md). Record boundaries and pseudocode fields are provisional; they do not select an encoding, hash, index, database, allocation, or wire protocol. Product/lifecycle decisions belong to the main design, and unresolved choices live in its [open-decision register](design.md#open-decisions).

## Identity and control

Use distinct types for stable entity IDs (repository, change, stack, workspace, actor) and immutable content-derived object IDs (snapshot, revision, candidate, and other typed records). Entity IDs can be allocated offline. Proposed object envelopes include kind/schema information in hashed contents; the exact scheme remains open.

An ID is neither a filesystem path, Git object ID, disk offset, nor an access grant. Physical relocation during compaction preserves object identity. Long-lived mutability is expressed through versioned control references with expected-generation checks. Immutable source records never acquire new contents under an old ID.

**Proposed control records:** candidate heads per workspace/change/stack; explicit checkpoint roots; submitted-publication refs; target heads; owner/visibility/update policy; queue and operation states. Keep these responsibilities separate even when committed together. Store large root/head collections in indexed/paginated form rather than rewriting one repository-sized record. Final schemas are open.

Identical encoded objects share identity. Different valid index shapes may represent the same logical namespace with different IDs until canonical logical-state roots are selected. Equal IDs can establish identical representation; unequal IDs alone cannot establish different source semantics.

## Source records

| Logical record | Proposed contents |
| --- | --- |
| Content | Byte sequence and logical length; whole-file objects can start the implementation. |
| File entry | Regular-file content ID and executable flag, or symlink target bytes. |
| Namespace/index node | Keys/entries or child references under an identified namespace representation. |
| Snapshot | Namespace schema/representation and root reference. |
| Conflict | Structured source alternatives, explicit absence/type information, and required reconstruction inputs. |

The [file/path contract](design.md#source-files-paths-and-ignores) defines UTF-8 relative path keys, exact contents, symlinks, executable status, ignore behavior, and materialization restrictions. File bytes and symlink payloads need not be UTF-8. No ownership, filesystem timestamps, ACLs, or explicit empty-directory entries are required.

Snapshots contain no author, time, change ID, review state, or workspace ownership. An ordinary read follows the selected namespace/content references, not prior revisions, editing provenance, operation logs, or review events. Unresolved reads return an explicit conflict result. Sharing bytes does not imply shared authorization or logical file identity.

A future chunk manifest can represent reusable content pieces without introducing inter-revision delta replay. Namespace hierarchy, snapshot index, and node/object disk layout are independent choices; neither one host file per object nor one node per directory is implied.

## Changes, revisions, and provenance

```text
Revision {
    change: ChangeID
    base: SourceStateRef
    snapshot: SnapshotID
}
SourceStateRef = Empty | IntegrationID | RevisionID
```

Empty denotes the defined initial empty source state, not missing data. A base resolves to exact source state; an upper stack revision can name its exact lower revision. Successive drafts R1 and R2 may both apply to I0. Reading R2's files does not replay R1.

A stable change associates its ID with retained revisions/candidate heads. Descriptions are separate versioned metadata; review publication is a separate exact selection. Avoid embedding every historical revision in each new revision/control value.

**Proposed provenance record:** result revision, operation kind, input revision IDs, actor/workspace, and recorded time. Human/agent reconciliation of RH and RA produces RR with one source base and both editing inputs in provenance. Different source bases require alignment before combining full source states. Provenance is access-scoped and separately requested; it is not an automatic public dependency closure.

An explicit checkpoint roots its revision and selected message/provenance records. Derived stack-update revisions remain protected by retained stack versions and other roots. Recovery-only predecessor links must not promote all automatic captures into permanent history. Preserve durable checkpoint provenance under its policy; an expired recovery-only input can have an explicit unavailable result.

## Stack versions and grouping

```text
StackVersion {
    stack: StackID
    base: SourceStateRef
    items: ordered [(ChangeID, RevisionID)]
}
```

Validate unique changes, revision-to-change ownership, first-base agreement, and exact successor dependencies. A structurally valid version may contain conflicts and be ineligible for landing. Already-landed source dependencies can be recognized through validated correspondence below.

Stack control selects current candidates independently of submitted review. Concurrent clients can retain competing versions without overwriting each other. A new grouping/version does not change existing revisions or their source contents.

Singleton covers refer to the change's descriptive entity; multi-change stacks have a separate cover entity. Preserve old descriptive versions when transitioning. Splits preserve exact source dependencies and group lineage. Stack-ID assignment, active-remainder identity, cover copying/promotion, and concurrent selection UX remain open; the earlier lower-keeps-ID suggestion is an option, not an accepted rule.

## Accepted source and frozen envelopes

```text
Integration {
    parents: [IntegrationID]
    snapshot: SnapshotID
    origin: optional { change: ChangeID, revision: RevisionID }
    history_envelope: HistoryEnvelopeID
}
Target {
    name
    head: IntegrationID | Empty
    generation
    authority
}
```

New native entries have one parent, except the initial entry with none. Imported history can have multiple parents and no native change origin. Prefix landing creates one entry per selected change, with the validated result snapshot and preceding accepted entry as parent. A different-base integration can yield a different full snapshot from its proposal.

History envelopes freeze the accepted message, author/committer attribution, and relevant timestamps. The request pins selected descriptive versions, using submitted versions for reviewed work or the chosen current description for solo landing. Later draft edits do not change queued text or accepted history. Git retries use the frozen envelope.

This is small source-history metadata: log/export can request it independently of discussions; checkout need not fetch it. Authenticated requesting/authorizing actors belong in the receipt/audit separately from source attribution. A queue worker is not automatically the source author. Message-only amendment UX and exact timestamp/identity encodings remain open.

## Landing records

```text
LandingRequest {
    request_id / idempotency_key
    target
    selected_stack_version / prefix
    publication: optional exact publication reference
    descriptive_versions / attribution_selection
    requester / delegation
}
IntegrationCandidate {
    request_id
    expected_target_head / generation
    selected_revision_ids
    results: ordered [(RevisionID, SnapshotID)]
    integration_algorithm_version
    outcome: resolved | conflicted
}
LandingReceipt {
    request_id / candidate_id
    repository / target / prior_head / resulting_head
    ordered proposal_to_integration_mappings
    landed_boundary
    selected_envelopes / policy_version / evidence_event_ids
    requesting / authorizing actors
}
```

These are proposed fields, not final ID/allocation rules. Requests/candidates are immutable records; their queue states evolve through versioned control transitions. An optional publication accommodates solo landing without fabricating a review.

Candidate preparation compares each proposal to its original base and integrates it against evolving accepted source. It does not store history as patches or overwrite target files wholesale. Approval stays on the submitted proposal; required integration evidence identifies the exact candidate/context. A changed expected target invalidates the candidate and requires preparation against the new head. Exact merge/conflict algebra remains open.

The [landing contract](design.md#native-landing-queue) requires one coherent publication boundary for validated source, expected target, queue completion, receipt/evidence, and pending Git work. Verify publication has not been superseded/withdrawn where applicable and approvals remain effective. Seal exact evidence used for landed decisions; unrelated unlanded subjects remain withdrawable. Policy/evidence/publication generations and cross-store transaction mechanics are unresolved implementation details.

### Partial-landing correspondence

For A at RA based on I0 and B at RB based on RA, landing A creates IA. If IA preserves RA's source state, the receipt establishes that RB's dependency is satisfied by IA. RB retains its revision/approval; a regrouped remainder can still literally name RA while displaying its accepted counterpart. No workspace rewrite is needed solely because A landed.

Record whether each mapping preserves source state or represents integration onto changed source. Do not infer correspondence from matching contents, messages, or change IDs alone. If IA includes other work or the target moves again, prepare B against actual accepted source; the old receipt alone is insufficient. Imported history gets no guessed native correspondence. This mapping must remain durable rather than exist only in a disposable cache.

## Working captures and operation recovery

```text
WorkingCapture {
    workspace: WorkspaceID
    change: ChangeID
    based_on: RevisionID | Empty
    snapshot: SnapshotID
    captured_at
}
OperationIntent {
    operation_id / kind / actor / workspace
    expected_control_generation
    before_state / protected_inputs
}
OperationResult {
    operation_id
    after_state / outcome
}
```

A current capture root per workspace/change protects unfinished work, with bounded extra recovery roots. A capture does not strongly retain every predecessor. Explicit checkpointing includes a capture barrier and durable publication; automatic capture can batch, with pending/local-durable/remote-acknowledged status distinguished. Validate/retry or report concurrent file changes rather than claiming arbitrary multi-file reads are an atomic editor save.

Persist intent and protected before-state before destructive workspace mutation. Record a result and publish control changes on completion. On restart, detect incomplete intent and recover without treating partial workspace files as authoritative source. Filesystem materialization and storage transactions are separate: the journal alone is not proof of atomic multi-file writes.

Preserve current/newer editor work before undo/recovery; undo is a new operation. Record affected refs/states, not copies of the entire control database. Ignored files relocated for safety use local recovery artifacts outside source discovery and are not uploaded as ordinary source captures. Exact artifact lifetime/access remains open.

Completed recovery-only records expire/compact with recovery policy. Explicit checkpoints, landing decisions, and required durable provenance retain their own roots. Active reads/writes and pending synchronization independently protect required objects.

## Collaboration records

Descriptions, review publications, discussions/resolution events, approvals/withdrawals, and optional external verification are independently fetched collaboration records with durable identity/version semantics. They are not fields folded into source snapshots.

| Proposed record | Exact references/context it needs |
| --- | --- |
| Descriptive version | Change or stack entity, title/description, metadata version. |
| Publication | Selected revision/stack version and descriptive versions; prior submissions remain addressable. |
| Comment/annotation | Subject and original anchor; line context can include revision/path/diff side/range. Extensible for later granular notes. |
| Approval/withdrawal | Exact subject/context, authenticated issuer, event identity/effective state. |
| Verification | Exact revision or candidate/target context, issuer/check, outcome, optional evidence link; run/attempt semantics if implemented. |

Ordinary draft changes do not advance publications. Explicit replacement/withdrawal supersedes/cancels pending old-publication landing requests. Queue selection pins publication identity as well as revision IDs, so unchanged bytes cannot evade withdrawal. These transitions serialize with landing; sealed decision evidence cannot be retroactively withdrawn.

Private source dependency closure and public review closure differ from editing provenance. No review record is required for a plain source read or solo landing. Missing metadata, metadata not fetched, and expired optional recovery context must remain distinguishable.

## Roots and lifetime

Three accepted reference kinds govern retention: reconstruction dependencies must remain available for retained source; explicit roots protect selected states; provenance links identify history without necessarily retaining every input's bytes. Reference schemas declare their kind; arbitrary ID fields are not implicitly strong references.

| Proposed root/record | Protected data |
| --- | --- |
| Target head | Accepted ancestry/snapshots and required source provenance. |
| Explicit checkpoint | Revision/base dependencies and intentionally retained description/provenance. |
| Retained stack version / submitted review | Exact selected revisions/bases and submitted metadata under policy. |
| Latest unfinished state | Current workspace/change capture, snapshot, and necessary base. |
| Unexpired recovery point | Capture and required restoration inputs. |
| Incomplete operation / pending sync | Inputs/outputs needed for completion or recovery. |
| Active read/write lease | Objects needed for its operation lifetime. |

Durably store required objects before publishing roots. Failed publication can leave unreachable bytes to reclaim, not visible references to missing data. Deleting a checkpoint root does not delete objects needed by another root, accepted history, conflict, or pending operation. Root removal and safe physical reclamation are separate steps. Reclaim only after reachability/concurrency validation and safe location publication.

The data retained by a provenance policy and the data a reader may access are separate questions. An immortal operation log must not indirectly defeat bounded capture retention. Before reclaiming provenance inputs, define which source/evidence records remain durable and how unavailable expired inputs are represented. Retention durations/limits and concrete reclamation are still open.

## Merge/resolver interface proposal

The accepted baseline compares complete entry states, including absence, type, and metadata:

1. If current and proposed match, keep the result.
2. If current equals base, use proposed.
3. If proposed equals base, keep current.
4. Otherwise invoke an applicable resolver or retain structured conflict state.

These rules work for opaque binary/symlink entries too. Namespace collisions and existing structured conflicts need normalized handling, not just independent per-path text merging or nested marker strings. Deterministic non-overlapping text combination is supported in principle; the algorithm is unselected.

**Proposed inputs:** immutable base/current/proposed descriptors, streaming/range-readable content handles, relevant namespace context, and resource/cancellation limits. External tools can use isolated temporary inputs, leaving author workspaces untouched.

**Proposed outcomes:** resolved entry, unresolved alternatives, unsupported, or execution failure. Validate and retain outputs as immutable source. Unsupported leaves a visible unresolved result; timeout/crash reports tool failure with inputs preserved, not a successful merge. Record tool/version/output identities where needed for reproducibility. Custom output is neither approval nor test evidence; automatic-queue trust rules for arbitrary synthesis remain open.

## Snapshot representation options

Selection is deferred; start simply and measure. User namespace, snapshot index, and physical node/array/segment layout need not share a shape. Logical records need not be separate disk files, allocations, tables, or requests.

| Option | Benefit | Cost/question |
| --- | --- | --- |
| Sorted flat manifest | Simple compact ordered baseline, scans and binary lookup. | Insertions/whole-manifest updates can rewrite much data; positional chunks may shift. |
| Persistent B+ tree | Bounded blocks, ordered/prefix scans, incremental writes. | Ordinary balancing depends on edit order; canonical logical roots require more rules. |
| Compressed radix trie | Prefix locality without a node per directory. | Durable packing, copy-on-write, common/long keys, and node shapes need measurement. |
| Hash-array mapped trie | Immutable map updates independent of directory shape. | Hash order loses lexical locality; prefix enumeration needs extra support. |
| Content-defined ordered chunks / prolly tree | Ordered scans, sharing, potential history-independent structure. | Boundary complexity, variable size/churn, and worst-case bounds. |
| Directory hierarchy with indexed children | Unchanged-subtree sharing and cheap prefix moves. | Deep lookup levels; huge directories still require bounded internal indexes. |

Full-path maps change descendant keys on a directory move. Relative-name hierarchies can reuse an entire subtree by rebinding its parent. Persistent file identity is another dimension and needs name-to-ID bindings. Append-only physical storage with a direct index is compatible; mandatory growing historical overlay chains are not the agreed direct snapshot-read model.

No multi-implementation bake-off is required before coding. Measure point/prefix reads, updates, moves, structural diff, cold reads, memory, write amplification, compaction, and equal-state construction. Canonical logical roots remain optional; reproducible object encoding is distinct from forcing one tree shape for all equal states. Representation changes still need compatibility handling.

References retained from the discussion: [Ideal Hash Trees](https://lampwww.epfl.ch/papers/idealhashtrees.pdf), [Adaptive Radix Tree](https://db.in.tum.de/~leis/papers/ART.pdf), [Dolt prolly trees](https://www.dolthub.com/docs/architecture/storage-engine/prolly-tree/). These are options, not measured Gaia results; ART's memory-index results do not establish durable-store performance.

## Representation and compatibility boundary

The [compatibility policy](design.md#format-compatibility) permits unversioned experimental evolution before a declared stabilization boundary. Proposed durable fields include repository format/capabilities, typed record schemas, and index/cache versions only where they solve a real boundary. Unsupported required semantics fail before mutation; optional data can be skipped only when its contract permits it.

Physical layout changes may preserve IDs; changing hashed object bytes/semantics may require mappings and different IDs. Account for retained source, private metadata/access, evidence, Git mappings, and pending queue/recovery records in supported migrations. Exact field widths, canonical encoding, hashes, migration protocols, and storage implementation remain open in the [decision register](design.md#open-decisions).
