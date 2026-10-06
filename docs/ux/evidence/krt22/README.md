# KRT-22 implementation verification — 2026-10-06

Implemented after approval of [the plan](../../krt22-relation-authoring-plan.md),
against base `7826d960`. This is seeded automated/render evidence, not a human
benchmark run or a measurement of faster authoring.

## Behavior

Entity/Event Connections have inline **Connected to…** capture. It requires one
existing target and creates `related` with empty attributes and no reverse row.
Event **Add participant…** / **Add location…** use the same capture controls with
the existing `involved` / `located_at` types and no implicit timing.

**Refine relation…** and double-click open meaning, actual direction and Notes
inside the inspector. Timing and advanced details start collapsed. Recorded
advanced values are indicated before expansion. **More actions** retains the
full editor and detailed-add routes. Automatic `mentions` remain protected.

Start and End each group their intent, date/event choice, viewed-date shortcut,
preview and optional offset. Viewed dates remain fixed; source/event links
follow event rescheduling. The common panel and full dialog share `RelationForm`
and canonical target resolution. Untouched managed values retain their original
snapshots, including numeric precision, custom attributes and payloads.

Apply is one command, with correlated success/failure feedback. Same-object
relation refreshes replace lists while retaining prose/caret and local relation
drafts. Newly saved rows are selected by UUID, including category changes.
Deleted draft rows cannot Apply; stale stored snapshots reject updates.

## Contract and exceptions

Contracts 1/3/4/7/10: ordinary authoring is inline; named timing and advanced
disclosures retain depth. The modal full editor remains a justified multi-step
configuration exception to contract 3. Contracts 2/8: Enter in capture resolves
the active completion before Connect; Notes Enter inserts a newline; Escape
cancels the innermost relation operation. Contracts 5/6/9: independent relation
drafts have Apply / Keep editing / Discard guards; worker refreshes retain
context, and command replay preserves relation UUIDs and creation timestamps.
Contract v1 has not changed.

Direction reversal updates the same row and is undoable. Source-event timing or
state-change payloads must be explicitly refined before reversal; the UI guards
both the reversal action and Apply so changing endpoints cannot silently change
which event supplies a boundary or which entity receives a mutation. Arbitrary
existing type names remain available in Advanced details and the full editor.

## Validation

* Final `pytest -m ci_fast -q`: **1,440 passed, 2 skipped**, 42.28 seconds.
  [Captured output](verification-ci-fast.txt). One existing FastAPI/Starlette
  deprecation warning; no executable build.
* Sixteen focused new acceptance cases cover both inspectors, canonical target
  capture, failed-save retention, lossless ordinary refinement, disclosure/draft
  refresh, deletion, multiline Enter/local Escape, inline fixed/dynamic timing,
  coordinator save feedback and prose/caret preservation, complete serialized
  undo/redo, reversal, stale snapshots, atomic replay collisions and confidence
  formatting. Existing form/playhead/numeric/choice/inspector tests also pass.
  The final focused relation and wheel-protection run passed **119 tests**.
* Changed-module mypy: **14 modules clean**. Repository Ruff and collection policy
  pass. New tests have explicit `ci_fast` membership and the collection baseline
  is updated.
* Production QSS renders inspected at 360 and 640 pixels for both inspectors:
  capture, refinement, grouped timing and advanced data. Offscreen Windows font
  loading is explicit; native/SVG arrow glyph rendering in this environment is
  not evidence of the application's native-window appearance.

The UI, UUID replay and context behavior are verified. A new empty-world human
KA-05–08/19 comparison remains necessary to measure usability improvement. This
batch is included in the KRT-22 implementation commit. The human comparison
remains a separate authoring-benchmark follow-up.

## Render evidence

Run from the repository root:

```powershell
.venv\Scripts\python.exe docs/ux/evidence/krt22/render.py
```

The renderer creates no world/database and isolates QSettings in a temporary
directory. It captures actual inspector widgets with seeded names and dates.

| Inspector | Capture | Refine | Timing | Advanced |
| --- | --- | --- | --- | --- |
| Entity, 360 | [Image](entity-360-capture.png) | [Image](entity-360-refine.png) | [Image](entity-360-timing.png) | [Image](entity-360-advanced.png) |
| Entity, 640 | [Image](entity-640-capture.png) | [Image](entity-640-refine.png) | [Image](entity-640-timing.png) | [Image](entity-640-advanced.png) |
| Event, 360 | [Image](event-360-capture.png) | [Image](event-360-refine.png) | [Image](event-360-timing.png) | [Image](event-360-advanced.png) |
| Event, 640 | [Image](event-640-capture.png) | [Image](event-640-refine.png) | [Image](event-640-timing.png) | [Image](event-640-advanced.png) |
