# KRT-56: Longform gesture, inspector context and relation-drop mitigation

Status: implemented 2026-10-07; automated and rendered verification passed.
Native desktop walkthrough remains unavailable; commit and push authorized
2026-10-07.
Plan date: 2026-10-06.
Tracking: https://linear.app/projektkraken/issue/KRT-56

## Evidence and failure sequence

The production Longform outline emits `item_selected` on selection change.
Longform forwards it to `NavigationCoordinator.on_item_selected`, which starts
a 250 ms timer. When it fires, `set_global_selection` loads the object and calls
`workspace.show_panel("entity" / "event")`. `show_panel(focus=False)` still
activates the tab. Shared-zone placement therefore replaces the Longform view.

Unlike Explorer, the outline emits no drag-start cancellation. Even adding that
signal is insufficient: the selection timer can fire while a slow mouse press
is still held, before Qt starts the drag. Cancelling navigation afterwards cannot
recover the original inspector target, draft or uninterrupted interaction.

Isolated offscreen reproduction used production LongformEditorWidget,
NavigationCoordinator and WorkspaceShell, with service collaborators mocked:

- Before the held-press timeout: active center tab Longform, selected ID `prior`.
- After 350 ms with the mouse still held: active center tab Entity, ID `second`.
- With QDrag.exec substituted by a 350 ms Qt event-loop wait: tab Entity,
  ID `first`, while the outline drag was in progress.
- No database was opened. This proves the signal/timer/tab behavior; it does not
  substitute for native pointer/focus and actual drag rendering verification.

The earlier read-only investigation confirmed six persisted self-connections
created by Entity/Event editor drop handlers. Four were subsequently removed.
Tasgilla and Benchmark Charter retain one each. Tasgilla's one UUID renders twice
because outgoing and incoming lists are appended independently.

Longform cards also emit navigation on mouse press, before text selection is
resolved. Include this related path so the repair does not leave another route
that hides a document while the user is selecting its text.

## Intended interaction

| Gesture | Outcome |
| --- | --- |
| Outline press / held press | Immediate local highlight; no global navigation, tab activation, draft prompt or mutation |
| Outline drag / structural drop | Keep document visible; preserve inspector target and playhead; one existing reorder command on successful internal drop |
| Cancelled drag / invalid drop | No deferred navigation after cancellation; no world mutation |
| Completed outline click / keyboard selection | Select locally and scroll to the entry; use the passive inspection policy below |
| Card click | Select locally after release; text selection remains owned by the text view |
| Card text-selection gesture | No inspector navigation or tab switch |
| Explicit Open in inspector / title or wiki link | Guarded navigation, deliberate tab activation, exact existing object identity |
| Relation drop on designated Connections target | Stage a named, directed draft; save only through Connect |
| Same-object relation drop | Reject with an explanatory cue; never create a self-connection through this gesture |

Passive inspection policy: when Longform and the destination inspector share a
workspace zone, a local selection must not activate or silently replace that
hidden inspector. Keep the document active and expose a labeled **Open in
inspector** action for the selected entry. When the inspector is already visible
in a different zone, a completed selection may update it through existing draft
guards without taking keyboard focus or changing the source tab. A hidden
inspector is opened by explicit navigation. Determine placement dynamically;
never assume center or right. A rejected navigation must leave the local document
selection usable and clearly distinguish it from the inspected object.

## Implementation sequence

1. **Separate local selection from navigation intent.** Preserve immediate outline
   highlighting and document action targets. Emit completed browse intent only
   after release when no drag occurred. Use Qt's drag-distance threshold rather
   than a longer selection timer. Keyboard selection is a separate route;
   refresh, selection restoration and programmatic synchronization are silent.
   Cover card text selection and existing explicit link navigation separately.

2. **Introduce source-aware navigation policy.** Carry the source panel and
   explicit-open versus passive-inspect intent through a narrow Longform binding
   or feature controller. Existing global navigation remains available to
   Explorer, Timeline, Graph and links. Resolve source/destination zones at use
   time. Do not globally change WorkspaceShell.show_panel semantics: callers
   deliberately use it to reveal tabs. Preserve save/discard/cancel guards and
   asynchronous save acknowledgement. Cancel stale gesture requests, including
   any deferred navigation waiting on a save; a superseded request must not later
   steal the tab. Do not use the Explorer-specific selection-restoration callback
   to reset the Longform outline during drag.

3. **Make relation-drop intent explicit.** Restrict relation acceptance to a
   visibly labeled Connections target, with feedback naming both endpoints and
   direction. Whole-inspector drops must not save a relation. Use the shared
   RelationAuthoring controls to stage the draft; show Connect and Cancel.
   Preserve the existing drop direction (dragged object -> inspected object),
   which differs from ordinary capture's inspected object -> chosen object.
   Validate IDs, object kinds, target identity and editability at entry, movement
   and drop. Capture the target identity for the gesture; reject if it changed
   before drop. Reject self-drops in the shared drop-intent path, including Shift
   type selection. Never overwrite an unfinished relation draft; use its existing
   Apply / Keep editing / Discard handling. Keep Connect unavailable while saving.

4. **Preserve advanced relation semantics.** Do not ban all self-relations or add
   a uniqueness constraint for endpoint/type pairs: deliberate advanced relations
   and multiple differently timed relations must remain representable. Prevent
   repeated submission of the same pending drop draft. Existing authored relations
   remain untouched. Shift may preselect a type in the staged draft but cannot be
   the only route to typed authoring. Successful Connect remains one command and
   one undo operation, using the established worker-thread mutation path.

5. **Deduplicate presentation by relation UUID.** Share the merge rule between
   Entity and Event lists. Show each saved relation once across outgoing/incoming
   snapshots, retaining genuinely distinct IDs and correct endpoint navigation.
   Use accurate self-relation wording when displaying existing deliberate records.
   Preserve Event participant/location classification and relation selection.

## Boundaries and contract obligations

Contracts 2, 5, 6, 7, 8 and 9 govern gesture ownership, context, visible routes and
reversibility; 1 and 3 govern reuse of inline relation authoring. Read the
authoritative Linear contract and visual vocabulary alongside their repository
counterparts. Clarify audit exception E-01: passive selection may populate a
visible separate inspector; explicit open may reveal a shared-zone inspector.
Record the revised whole-inspector relation-drop convention in the audit and
KRT-22 plan/user documentation. Any normative contract revision must update
Linear and the repository together.

Use shared StyleHelper controls: local selection/focus roles, neutral supporting
captions, neutral mode information for the draft, and an explanatory warning for
invalid drops. Object identity colors identify endpoints. Preserve Enter/Escape
ownership: multiline controls and completion popups retain their keys; Escape
cancels only the innermost gesture/draft. Keep Open, Connect and Cancel reachable
in narrow layouts, with disabled prerequisites explained.

Prefer a small feature-specific controller or existing narrow navigation seam;
do not add Longform business responsibilities to MainWindow, ConnectionManager,
DatabaseWorker or DatabaseService. Existing facades may delegate. Before editing,
check the complexity policy; any executable touch to a reviewed hotspot requires
the incremental-refactor workflow and a strictly lower ceiling.

## Verification and delivery

- Delivered Qt mouse events: press, hold beyond 250 ms, release, fast/slow drag,
  Escape, cancelled external drag and successful internal reorder. No latent
  inspector load/tab switch after drag completion. Test keyboard selection,
  programmatic refresh and content text-selection gestures separately.
- Layout matrix: Entity and Event share Longform's zone; each is visible in a
  different zone; destination hidden; panels moved between zones during use.
  Verify real active tab, keyboard focus, scroll, draft, selection and playhead.
- Draft matrix: clean/dirty inspector, pending save, failed save, Cancel and
  superseded navigation. No gesture-induced dialog while mouse is held/dragging.
- Relation matrix: self/cross-object, repeated drops, malformed/missing object,
  changing target, read-only state, Shift, existing unfinished draft, pending
  Connect, command failure, undo/redo and advanced custom/timed relations.
- One self-relation ID gives one row; two different IDs remain two rows. Verify
  Event classifications, direction, preserved selection and endpoint links.
- Focused existing Longform, delayed-navigation, workspace and relation suites;
  required Ruff/mypy ratchet, visual and complexity policies, then bounded
  ci_fast. No executable/package build. Render enabled/disabled/focus, theme
  switching and narrow controls using production styling. Perform a native
  pointer check in a disposable world; retain evidence. KA-05/06 and KA-18 cover
  relevant semantics; claim no human timing improvement from automated probes.

No production repair is part of this plan. If separately authorized, repair only
the two confirmed accidental relation UUIDs after rechecking current state and
making a verified SQLite backup; preserve all other data and command history.
Keep KRT-56 open until implementation, verification and an authorized commit.

Implementation and verification evidence: [KRT-56 checks](evidence/krt56/README.md).
