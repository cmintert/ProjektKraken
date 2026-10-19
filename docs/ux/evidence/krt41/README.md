# KRT-41 — Timeline reconciliation and layout preparation

Implementation evidence, 2026-10-19. Comparison baseline: `51be1231`.

## Responsibility boundary

Before: `TimelineView.set_events()` combined sorting, reconciliation, graphics
ownership, layout dispatch and initial navigation. Background lane packing copied
the event list but still read shared events, global calendar state and GUI geometry.

After: the stateless `TimelineEventPreparationService` prepares replacement and
ordered mutation batches. The view retains scene scanning, graphics creation,
reuse/removal, drop lines, grouped duplicates, timers, initial fit and navigation.
Surviving primary items retain selection and drag callbacks. Metadata-only updates
also refresh grouped copies without repacking.

`TimelineLanePacker` measures the existing item geometry on the GUI thread and
produces frozen numeric intervals. Pure first-fit packing is shared by standard,
grouped and background layouts. Workers own no live events, calendars, fonts or
graphics items. Completion/error signals use explicit queued delivery and request
tokens. Generation checks cover event geometry, previews, zoom, calendar, grouping
and empty timelines. Stale results redispatch using the current layout mode;
obsolete callbacks cannot release a newer worker. Current failures retain fresh
synchronous fallback. The 50-event threshold and grouped synchronous path remain.

No SQL, command, transaction, undo/redo, data schema, ruler rendering or navigation
responsibility moved. Dependency guards constrain the preparation and pure packing
modules and prevent the worker from importing GUI measurement or event models.

## Automated evidence

- Final complete `pytest -m ci_fast -q`: **2,227 passed, 3 skipped** in 385.18 s.
  The only warning is the existing Starlette/httpx test-client deprecation.
- Focused timeline, calendar, temporal presentation, ruler, drag/interaction,
  grouping, navigation, fit, mutation-effects and dependency regressions:
  **437 passed**. This includes the new ordered-batch, metadata, detached-input,
  request-token, actual queued delivery, coalescing, empty/threshold transitions,
  preview, calendar and grouped-layout cases. A stale completion consumes the
  pending incremental debounce rather than scheduling a second layout. Final
  boundary/helper checks separately passed **82 tests**.
- `set_events()` complexity: **19 → 2**; C901 suppression and allowance
  `c901-020f2d0c9c6b` removed through verified tightening against the baseline.
  Reconciliation measures 9, post-replacement presentation 6, effect preparation 3
  and pure packing 3; extracted functions satisfy the normal ceiling of 15.
- Repository-wide mypy passes across **485 source files**. Ruff, visual policy,
  complexity policy, test inventory and Help inspection inventory pass. Nitpicky
  strict Sphinx generation passes; rendered HTML includes the evidence page and
  architecture boundary.
- The existing point-event minimal-lane test failed on both untouched baseline
  and implementation because its date gaps did not guarantee nonoverlapping text
  extents in this environment. The fixture now separates the point events beyond
  their labels. No packing behavior changed to satisfy that assertion. Baseline
  reproduction output is retained in `artifacts/krt41-baseline-point-test.txt`.
- A first complete font-configured run found one overstrong new preview-test
  assertion: renaming an event need not enlarge its bounds when the date caption
  is wider. The test now verifies replacement request identity and preview state;
  all **82** boundary/helper cases pass with the same font configuration. No
  production change was needed for that failure.

The sandbox cannot launch the venv's WindowsApps interpreter. Running the existing
venv with approved execution outside the sandbox works (Python 3.13.14); no
environment rebuild, dependency installation or interpreter substitution was needed.
The complete-suite rerun sets `QT_QPA_FONTDIR=C:\Windows\Fonts` for Qt offscreen
rendering. Earlier attempts spent excessive time in Help rendering without that
setting; the two Help renderer/probe cases pass separately with it (**2 passed**).

## Presentation and preserved context

Contracts **2/5/6/8/9** and the timeline temporal grammar apply. Visible routes
remain the timeline, event selection/drag, Fit View, date navigation, grouping and
playback controls. Keyboard and focused-control ownership are unchanged. The
extraction preserves primary selection, viewport/zoom context, playhead/world-time
separation, initial fit, deep-zoom rebasing and the existing command mutation path.

Existing semantic roles remain `event_main`, `supporting_caption`, shared selection/focus,
`timeline_viewed_time`, `timeline_world_time` and `timeline_grid`. Existing shared
toolbar/control presentation remains. No color, stylesheet, label or interaction
contract change or exception was introduced; no visual baseline was regenerated.

The [renderer](render.py) loads the actual baseline view, lane packer and worker
together, then compares identical fixtures with the current implementation. All
**60 PNG pairs are byte-identical**, with matching scene-state manifests: six
themes × 480/1100 px widths × standard/grouped/collapsed/empty/disabled states.
Both requested widths were achieved at 900 px height, DPR 1. Captures load Segoe UI
explicitly. Fixtures include a custom 360-day calendar, pre-epoch/year-zero/sub-day
positions, uncertain timing, selected/future events, grouped copies and distinct
viewed/world-time markers. Enabled views request keyboard focus.

Dark narrow grouped and light wide standard captures were visually inspected.
Narrow graphics content remains pannable and the existing toolbar uses overflow.
These are offscreen component captures, not native Windows DPI/text-scale
acceptance, human task-time or temporal-grammar interpretation evidence. No personal
world was opened.

Local artifacts remain under ignored `artifacts/krt41/`: `focused-final.txt`,
`boundary-fonts-final.txt`, `ci-fast-verified.txt`, `before/`, `after/` and comparison
manifests. The initial full-suite attempt was interrupted to include the final
debounce correction, and a subsequent attempt was interrupted during the font
diagnosis; their partial outputs are superseded. The earlier `ci-fast-fonts.txt`
records the corrected preview-test assertion. Reproduce from the
repository root:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m docs.ux.evidence.krt41.render --output artifacts/krt41/before --baseline-ref 51be1231
.\.venv\Scripts\python.exe -m docs.ux.evidence.krt41.render --output artifacts/krt41/after --compare-with artifacts/krt41/before
```

Local commit was authorized on 2026-10-19, reusing the passed verification above
without rerunning tests. Linear records the resulting commit and delivery status.
Push and native human acceptance remain separate delivery steps.
