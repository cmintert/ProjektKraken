# KRT-26 — unfinished map edit verification

2026-10-08; implementation based on revision 7b7fc211acb1780ed3fa7177a4d0b2db126f5cb5.
Implementation and verification evidence. Publication result is recorded in KRT-26.

## Behavior and contract mapping

One feature-specific transition coordinator protects trajectory and managed
geometry drafts before map navigation, target/mode replacement, affected feature
or world-entry deletion, map/layer deletion, world selection, restore and close.
Unchanged existing sessions leave directly. New journeys, new dated geometry
states, modified drafts and meaningful local proposals require Apply / Keep
editing / Discard. Same-map list refresh preserves accepted selection and reloads
its dependent snapshots without a navigation decision.

Keep editing is the initial focused/default decision; Escape and dismissal retain
the draft. Enter activates the focused decision. Apply is primary, Keep editing
secondary, and Discard destructive through StyleHelper. Disabled Apply remains
visible with its prerequisite in text and tooltip. Theme changes reapply shared
roles. Geometry conflicts retain working vertices and expose Discard and reload,
including when the scene target disappears. Explicit local Cancel/Escape behavior
remains, with trajectory date/speed operations retaining their containing session.

Contracts 2/3/4/5/6/7/8/9 apply. The loss-prevention decision is an exceptional
modal choice before leaving a direct authoring operation; normal editing stays
in its existing surface. No contract revision, migration or persistent draft
stash is introduced. World selection still requires restart.

## Persistence and lifecycle boundaries

The guard consumes copied status dictionaries and correlated session/command
completion. It keeps the first pending action, ignores unrelated or stale
results, and validates world identity before continuing. A dismissed/reselected
World Manager destination cannot execute a stale settings write. Close queues a
fresh close event only after map approval, then uses existing editor/raster
checks. Restore retains validation, confirmation, safety backup and worker
shutdown ordering before replacement.

Trajectory Apply waits for the matching authoritative reload; a reload failure
retains a conflicted draft and cancels navigation. Geometry owns original and
working vertices independently of scene items, rebinds recreated items, and
preserves existing handles on unchanged refreshes. Failed Apply reopens vertex
editing. Dated-state optimistic comparisons are preserved. Base geometry has a
worker-side geometry/anchor comparison for Apply/undo/redo, preserving unrelated
current marker fields. The command registry serializes this command. A small
worker failure-path correction includes the command ID when no database is ready;
no feature slot or new worker responsibility was added.

The touched World Manager caption now uses the shared supporting-caption role.
Only its exact resolved gray-color exception was removed from the visual-policy
baseline; no exception or ceiling was raised.

## Reproducible rendered evidence

Run from the repository root:

- `.venv\Scripts\python.exe docs/ux/evidence/krt26/render.py`
- `.venv\Scripts\python.exe docs/ux/evidence/krt26/replay.py`

The decision renderer uses production QSS, explicit Windows Segoe UI fonts,
disposable QSettings and all six palettes. It records enabled Apply at 420 px and
disabled Apply at 320 px, with actual keyboard focus and button bounds checked.
The twelve palette images are durable evidence; the disabled/narrow captures
also show the visible prerequisite. Images were visually reviewed across every
palette. No stylesheet baseline was regenerated.

[Assisted replay diagnostics](replay.json), [journey draft](journey-kept.png) and
[geometry draft](geometry-kept.png) use production MapWidget/coordinators and
synthetic snapshots. The synthetic background goes through the production map
load path; the viewport uses software rendering. The journey point and geometry
vertex are modified through production edit callbacks, then Keep editing,
same-map refresh and explicit Discard are exercised. Zero commands are emitted
before Apply and the viewing date remains 5.0. Synthetic world settings and
background files are removed automatically. These captures demonstrate retained
working state; existing surrounding map-control presentation is not a new visual
acceptance claim.

This is automated/assisted acceptance, not a human KA-16 recording, completion
rate, first-use learnability result or measured task-time improvement. A fresh
human benchmark remains separate.

## Verification

- Focused map/trajectory/geometry/lifecycle coverage: **449 passed**; final narrow
  recovery presentation adjustment: **104 passed**.
- Bounded ci_fast: **1,706 passed, 2 skipped**. The one reported warning is the
  existing Starlette/httpx deprecation.
- Ruff, mypy for all **450 production modules**, dependency projections,
  visual policy, complexity policy and git diff whitespace checks passed.
  Reviewed C901 hotspots were untouched; no allowance or ceiling increased.
- Both evidence scripts pass. Failed geometry Apply is also replayed with real
  vertex handles; [failure capture](geometry-after-failed-apply.png) and
  [narrow conflict recovery](geometry-conflict-narrow.png) show the retained draft.
- Strict Sphinx HTML checking reports **22 warnings** in existing UX navigation
  and a local skill cross-reference, including the contemporaneous untracked
  Northwatch document. No warnings name the KRT-26 evidence or investigation;
  those two pages are explicitly included in developer navigation.
  [Exact diagnostics](sphinx-warnings.txt) are retained. Unrelated documentation
  and demo-world work was preserved.
No executable/package build was requested or performed. Sphinx output, if used,
is disposable under .tmp/krt26-sphinx; scripts, renders, diagnostics and this
report remain in this evidence directory. The initial Python access-denied
limitation was resolved by running the project virtual environment outside the
sandbox. The user authorized commit and push after verification; the resulting commit and
publication status are recorded in KRT-26.
