# KRT-47 — Longform authoring verification

2026-10-06; implementation based on `a12c84e5771fadb488c5d2d68e09ef8b0ddb67ef`.

## Routes and contract mapping

Contracts 1/2/3/4/5/6/7/8/9 apply. **Add content…** opens a searchable inline
existing-entry chooser; the empty state teaches the same route. Explicit selection
and **Add to document** append one existing entry without opening its inspector.
Duplicate names retain type and stable identity; adding existing membership leaves
its arrangement intact. **Outline actions** shares menu construction and command
intents with right-click Move Up/Down, Promote/Demote, document removal and world
deletion. Card selection updates the outline action target. **Find** is labeled.
All actions retain access through the shared responsive **More actions (…)** menu.

Enter accepts a selected chooser result or advances Find; Shift+Enter searches
backward. Escape closes the local chooser/search, and existing outline shortcuts
remain accelerators. Delete in the outline requests guarded world deletion. Refresh
restores outline selection without re-emitting navigation, preserving inspector
drafts; unchanged content retains reading cursor/selection and scroll. Playhead and
inspector authoring state are outside these membership operations. No new modal
exception or interaction-contract revision.

## Membership and deletion

Addition reuses MoveLongformEntryCommand's transaction, exact metadata snapshot
and history serialization; the append position is calculated on the database
worker, including members hidden by filters. Add/Remove are registered for queued
command execution and persisted undo/redo. New signals are bound by LongformManager;
no new worker slot, ConnectionManager responsibility or main-thread SQL.

**Remove from document** preserves the world entry. Its descendants lift one level;
direct children occupy its former position before the next sibling. Exact worker
snapshots restore the full section, child hierarchy, other documents and authored
metadata with one undo operation. Failure after child updates rolls back all writes.

**Delete from world…** has a default-Cancel confirmation explaining whole-world
scope. Cancel emits no command. Confirmation uses EditorCoordinator, retaining
raster-reference guards; deleting the active inspector target also respects its
existing Save/Discard/Cancel draft guard. Tests execute real event/entity deletion
commands and undo. Refresh, export and position reindex no longer implicitly add
all world objects; existing authored memberships remain intact. Explicit CLI
indexing remains available with its existing transaction ownership.

## Presentation and rendered evidence

Controls use shared primary/secondary roles. App background uses `app_bg`; outline
identity uses `entity_main`/`event_main`; chooser/outline selection and keyboard
focus use `selection_bg`, `selection_text` and `focus_ring` through a shared
StyleHelper item-view helper. Two obsolete outline literal-color exceptions were
removed explicitly; no visual baseline exception was added or broadened.

Run `.venv\Scripts\python.exe docs/ux/evidence/krt47/render.py` to reproduce
54 offscreen captures with production QSS, registered Segoe UI fonts, isolated
QSettings and synthetic snapshots. No real world is opened or modified.

- `<theme>-<400|1100>-empty.png`: actionable empty state and disabled actions.
- `*-outline-focus.png`: selected section and asserted keyboard focus.
- `*-actions.png`: shared labeled structural/removal/deletion menu.
- `*-add.png`: chooser, explicit selection and hover over the Add control.
- `*-400-overflow.png`: narrow-width access to supporting actions.

All six palettes were inspected at narrow widths; normal-width controls were
also inspected. The offscreen runtime could not load SVG images through its
image plugins (`render-log.txt`); textual labels remain available. These renders
verify control geometry and theme presentation, not first-time discoverability
or human task-time improvement. Fresh human KA-18 comparison remains pending.

## Validation

The 20 new ci_fast acceptance cases cover visible add/nest/reorder/undo, narrow
overflow, shared menu intents, cancellation, real confirmed world deletion and
undo, inspector draft cancellation, authoritative membership snapshots, descendant
lifting/rollback, unchanged refresh targets, Find and persisted history after
database reopening. Existing Longform service, CLI, integration, outline, search,
demand-loading and exact-undo tests also pass.

Project Ruff, full mypy (441 modules), test-discovery membership, visual policy
and complexity policy pass. The bounded suite passed **1601 tests, 2 skipped**.
All 23 reviewed C901 hotspots are unchanged; no
refactor allowance was raised. The reviewed collection change adds these 20
ci_fast cases and renames the obsolete worker auto-indexing test to an explicit
indexing transaction test. See `complexity.json` and `verification-ci-fast.txt`.

This evidence accompanies the KRT-47 implementation commit; delivery status is
tracked in Linear. No executable build, database migration or human benchmark
recording was performed.
