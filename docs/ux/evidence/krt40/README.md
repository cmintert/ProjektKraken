# KRT-40 — Temporal entity save preparation

Implementation evidence, 2026-10-19. Base revision:
`d8a4c6715422c0aa5a86848c736a737a5d13cff9`.

## Responsibility boundary

Before: `EntityEditorWidget._save_temporal` compared visible values, assembled
patches/metadata, obtained ownership choices and began submission. Pending
metadata, dated-description intent and a pending boolean were separate fields.

After: the stateless `TemporalEntityDraftService` compares copied snapshots and
returns `NoChanges`, `ChoiceRequired` or `PreparedSave`. Existing dialogs and
presentation stay in the widget. Modal preparation uses a `finally`-released
guard; each modal return and final submission compare the captured identity,
generation, revision, time, baseline and live values. Cancellation or mismatch
emits no partial request and does not clear the current draft.

One copied `PendingTemporalSubmission` holds submitted metadata and description
intent; the temporal pending property is derived from that record. Revisions and
dirty state remain in `BaseEditorMixin`. The existing coordinator still correlates
command results. Checkpoint comparisons are installed before pending guards are
released or autosave restarts. Later edits, including summary/description intent,
remain live and dirty. Invalid successful checkpoints retain recovery guidance and
block retries until deliberate reset. Discard, clear and hydration drop the record.

No command, worker, SQL, transaction, schema, calendar resolution or Context-tab
responsibility moved. The dependency guard restricts the preparation module to
its pure-data imports. Existing payload keys and acknowledgement return values
are unchanged.

## Automated evidence

- Final `pytest -m ci_fast -q`: **2,191 passed, 3 skipped**. The only warning is
  the existing Starlette/httpx test-client deprecation warning.
- Final focused regressions: **207 passed**. Includes pure preparation, widget,
  checkpoint, command, temporal authoring, dependency, fresh authoring-context,
  time-coordinator, Help inspection and chronology-service cases.
- Help dialog/search regressions: **26 passed**. Updated the existing dated-event
  picker test double to accept the optional captured-context argument; its real
  modal choice and Help-metadata assertions remain unchanged.
- New regressions cover addition/removal choices, cancellation after an earlier
  choice, silent autosave deferral, nested saves, changes during modal choices,
  guard release on exceptions, reset/late acknowledgement, nested transport copies
  and acknowledgement preserving newer summary/dated-description intent.
- Existing checkpoint coverage protects historical/current/future edits,
  baseline/event ownership, real typing/autosave timing, failure/invalid
  checkpoints, fresh calendar resolution, composites, rollback and undo/redo.
  Existing chronology tests retain invalid historical conflicts during unrelated
  edits and reject new conflicts; reprojection remains distinct from authoring.
- Ruff and changed-file formatting pass. Repository-wide mypy passes across
  **483 source files**. Visual policy and Help inspection inventory pass.
- A fresh strict Sphinx build passes after linking this page from the UX
  evidence navigation tree. The generated HTML index contains the expected link.
- Complexity policy passes against the base above. `_save_temporal`: **16 → 7**;
  allowance `c901-b90fc28385bc` and C901 suppression removed. The extracted service
  preparation measures 8, metadata comparison 7 and description preparation 3;
  all remain below the normal ceiling of 15.
- The first `ci_fast` run found the stale Help handler fingerprints and removed
  metadata locator. Reviewed only the affected entries, carried the metadata
  locator into the service, and added review entries for the new dependencies.
  Existing ownership, removal and Save/Discard explanations remain accurate.
  The generated-excerpt/inspection regressions pass in the final focused run.

Local detailed outputs are retained under ignored `artifacts/krt40/`:
`focused.txt`, `help-dialog.txt`, `ci-fast.txt`, and `complexity.json`.

## Presentation and context

Contracts **2/5/6/9/11** apply. Visible routes remain **Save Changes**, **Discard**,
**Start a new description at this time**, and the existing ownership/removal
dialogs. Enter remains owned by the focused control, including multiline writing;
dialog cancellation leaves unrelated edits intact. No shortcut or focus-routing
implementation changed. Existing checkpoint tests assert caret/selection, scroll,
document undo and newer-draft preservation. Time-coordinator tests retain pinned
draft time and guarded navigation. No UX contract revision or exception was added.

Presentation roles remain shared primary/secondary controls, neutral
`mode_bg`/`mode_border`/`mode_text` banners, and shared focus/disabled states. No
local colors, action wording, dimensions or styling were introduced.

The reproducible [renderer](render.py) compares the actual base-revision widget
with this implementation using the same fixture. All **60 readable PNG pairs are
byte-identical**: six shipped themes × requested 360/800 px inspector widths ×
editable/read-only/pending/failed-save/invalid-checkpoint recovery states. Both
requested widths were achieved at 900 px height and DPR 1. Save is the focus
target where enabled; read-only fixtures retain disabled Save/Discard controls.
The manifests retain fonts, dimensions, labels, enabled state, pending/dirty
state, banner text and hashes. Dark narrow recovery, light wide pending, light
narrow read-only and cyberpunk wide failed-save captures were visually inspected.

Final readable captures and manifests:

- Base: `artifacts/krt40/font-before/`
- Implementation: `artifacts/krt40/font-check/`
- Comparison: `artifacts/krt40/readable-comparison.json`

The earlier `before/` and `after/` matrices used missing-font fallback glyphs and
are superseded, despite matching pixels. Final captures explicitly load Segoe UI.
The harness guards an existing receiverless Context-widget resize callback during
fixture teardown only; no production Context code was changed.

These are offscreen component captures, not native Windows DPI/text-scale
acceptance, a whole-application release gate, or human task-time evidence. Native
review remains separate and is not claimed. No personal world was opened.

Reproduce from the repository root with `QT_QPA_PLATFORM=offscreen`:

```powershell
.\.venv\Scripts\python.exe -m docs.ux.evidence.krt40.render --output artifacts/krt40/font-before --baseline-ref d8a4c6715422c0aa5a86848c736a737a5d13cff9
.\.venv\Scripts\python.exe -m docs.ux.evidence.krt40.render --output artifacts/krt40/font-check
```

Commit and push were authorized on 2026-10-19. Linear records the resulting
commit and delivery status; native review remains separate as described above.
