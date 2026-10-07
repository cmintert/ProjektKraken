# KRT-22 — Connection capture and progressive refinement

Proposed and approved for implementation 2026-10-06 against `7826d960`.
[Implementation evidence](evidence/krt22/README.md).
[Linear issue](https://linear.app/projektkraken/issue/KRT-22/expose-loose-relation-capture-before-full-relation-editing).

## Outcome and scope

A creator can record a connection by choosing one existing object, then refine
that same connection into membership, participation or another relationship.
Ordinary capture and refinement happen inside the Entity/Event inspector.
The full editor remains available for expert configuration.

Include the human-review problems owned by this issue: boundary grouping,
participation vocabulary, recognizable Notes input and confidence formatting.
Keep the KRT-16 canonical relation/attribute investigation separate; this work
adds no attribute conversion or new rule about which representation is canonical.

## Proposed interaction

| Stage | Visible route | Fields and result |
| --- | --- | --- |
| Capture | Connections → **Connected to…** | Inline existing-object search, **Connect**, **Cancel**. One required choice: destination. |
| Refine | Select connection → **Refine relation…**, or double-click | Inline meaning/type, direction preview, Notes and collapsed **Timing…** / **Advanced details…**. **Apply** updates the selected relation; **Cancel** restores its saved snapshot. |
| Participation | Event Connections → **Add participant…** | Same shared capture panel, labeled for participation; records `involved` without asking the creator to understand that internal name. |
| Location | Event Connections → **Add location…** | Same shared capture panel with location wording; records `located_at`. |
| Expert | Visible More actions → **Full relation editor…** / **Add detailed relation…** | Retains custom types, target changes, payloads and all current expert semantics. |

Use the existing `related` type for loose capture, consistent with current
loose-capture storage. KRT-56 (2026-10-07) replaces immediate inspector-drop
creation with a labeled Connections drop target and a directed Connect/Cancel
draft. A visible meaning choice replaces modifier-only type selection. Preserve
the dropped-object → inspected-object direction and reject self-drops without
banning advanced authored self-relations. Create one outgoing relation with empty attributes;
do not manufacture a reverse relation, temporal binding, confidence or payload.
Describe it as **Connection — kind not specified**. Timing is **Not specified**,
not an assertion that the relation is timeless or that dates are unknown.
Existing unconstrained resolver behavior is preserved.

The selected object is the initial source. A sentence preview uses both actual
object names. Generic connections avoid implying that the source owns, causes
or belongs to the target. Typed refinement exposes direction explicitly;
**Reverse direction** exchanges endpoints on the same relation UUID. Creating
an additional reverse relation remains a separate expert option, clearly named.

Meaning presets display creator language, including **Connected**, **Member of**,
**Participant in**, **Located at** and **Custom type…**. Persist existing type IDs.
Event-sourced `involved` reads as “Target participates in Source”; it must not
appear to require the creator to type `involved`. Show custom type names unchanged.
Do not silently reinterpret existing `member_of` rows categorized as participants.

Notes is a visibly bordered multiline field with a label and useful placeholder.
Weight and confidence live under Advanced details, with explanations. Format
numeric summaries without floating-point tails; formatting must not round stored
values or mark the relation dirty. Preserve numeric and choice wheel protections.

## Timing

Timing starts collapsed for a new unconstrained connection. Existing timing is
summarized beside the disclosure so advanced data is apparent before expansion.
Place each boundary's choice, date/event input, fixed viewed-date shortcut and
preview in one block: all Start controls together, then all End controls.

Common wording: **No start limit**, **From a date**, **Begins with an event**;
**No end limit**, **Until a date**, **Ends with an event**. A separate **Date
unknown** choice preserves unknown-versus-open meaning. **Use viewed date**
shows the actual timeline playhead and stores a fixed date. Event choices explain
that they follow rescheduling, identify the named event and show a date preview.

Advanced details retain stateful/historical/occurrence/atemporal behavior,
before/after anchors, offsets, uncertain expressions, instant relations and
state-change payloads. Do not flatten these into exact start/end dates.
Changing one boundary must preserve the other. Event participation capture
does not silently choose dynamic timing; the creator can explicitly add it later.

## State, keyboard and presentation contract

Apply contracts 1/3/4/7/10 to inline common authoring and secondary expert details;
2/8 to shared click, double-click and keyboard behavior; 5/6/9 to visible local
drafts, context preservation, feedback and undo.

Enter selects an active search completion before committing capture. In a
multiline Notes field it inserts a newline; Apply is an explicit button.
Escape closes the innermost popup or cancels the local relation edit. It must
not discard the inspector's description draft. Changing relation/object or
opening the full editor with pending edits offers Apply / Keep editing / Discard.
Disclosure changes retain values and never emit a mutation.

After capture, select the saved row and expose Refine. After refinement, keep
the same selected UUID even if it moves between Event relation categories.
Same-object worker refreshes retain newer local drafts and disclosure choices.
If an external undo deletes the edited relation, disable Apply and explain that
it no longer exists; do not recreate it from the stale draft.

Reuse shared disclosure, responsive action and theme-aware input patterns.
The expert dialog is the documented contract-3 exception for multi-step advanced
configuration. No contract rule change is proposed.

## Implementation sequence

1. Extract reusable target resolution/completion from `RelationEditDialog`,
   including duplicate-name disambiguation, existing-object validation and kind
   snapshots. Introduce a shared presentation-only connection authoring panel
   for both inspectors; widgets emit snapshots and intent only.
2. Wire inline capture through the existing add signal, `EditorCoordinator`,
   `AddRelationCommand` and worker. Leave existing typed/drop/expert routes
   available. Add visible success/error feedback without moving the text caret.
3. Wire inline refinement through the existing update path. Extend update
   snapshots narrowly for explicit endpoint reversal, including undo/redo and
   serialization. Use repository capabilities for persistence; add no feature
   responsibility to the transitional worker, connection manager or MainWindow.
4. Separate timing presentation from serialization and reuse it in refinement
   and the expert form. Retain an immutable original snapshot and preserve
   untouched attributes, payloads, precision and unknown fields losslessly.
   Refactor the touched dialog sections instead of growing its constructor.
5. Correct Add command identity retention across undo/redo. Current execute
   generates IDs and undo clears them: redo of capture can leave the later
   refinement command pointing at a deleted UUID. Retain assigned IDs and
   creation timestamps, serialize them and reinsert via the repository within
   command transactions. Preserve compatibility with old command history and
   bidirectional additions; never overwrite a conflicting existing row.
6. Add focused verification, rendered evidence and an audit disposition entry.
   Record measured human improvement only after a fresh comparison run.

## Acceptance and verification

* Entity and Event: choose a named existing target, Connect, reopen and inspect
  exactly one authored `related` row, separate from automatic `mentions`.
  Duplicate names resolve to the selected UUID; unresolved input cannot commit.
* Refine to membership plus note: same relation UUID, correct source/target,
  no duplicate; cancel changes nothing. Reverse explicitly and verify undo.
* Capture → refine → undo refinement → undo capture → redo capture → redo
  refinement succeeds with the original UUID, including serialized history.
* KA-07: fixed start equals the viewed date and survives event rescheduling.
  KA-08: explicitly event-bound participation end follows rescheduling and undo.
* Existing confidence precision, notes, arbitrary attributes, payloads,
  open/unknown boundaries, offsets and temporal expressions survive opening,
  collapsing, ordinary refinement and full-editor round trips (KA-19).
* Preserve description drafts/caret and playhead through worker refreshes;
  verify local cancel and pending-edit navigation decisions in both inspectors.
* Render at narrow and normal inspector widths with the production theme:
  capture, refinement, both boundary blocks, existing advanced details and
  visible expert routes. Check Notes readability and keyboard focus order.
* Run focused relation/command/playhead/editor and wheel-protection tests,
  changed-module Ruff/mypy, test policy and bounded `ci_fast` if appropriate.
  No executable build is needed. Human KA-05–08/19 comparison starts from a
  new empty world and remains distinct from automated acceptance evidence.

## Review decisions

Approve the inline interaction above, the reuse of `related` without a new
provisional schema, explicit reversal of one relation, and secondary expert
controls. The user approved implementation and then requested the verified batch
be committed on 2026-10-06. A fresh human comparison remains a separate follow-up.
