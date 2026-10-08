# KRT-64 map inspection verification — 2026-10-08

Ordinary map feature selection preserves Map's active workspace tab. Passive
inspection updates only the matching inspector already visible in another zone,
resolved at the time of navigation. Hidden/inactive and shared-zone inspectors
stay untouched. The labeled **Open in inspector** action reveals the selected
feature's underlying Entity/Event through existing draft guards.

## Behavior and boundaries

`MapNavigationController` owns source-aware inspection and superseded navigation.
The existing MapHandler click entry point delegates through its unchanged
two-argument callable contract. MainWindow/AppCoordinator only compose the
controller; no database access or command mutation was added.

New spatial presses, scene/layer selection and map changes cancel older map-origin
navigation continuations without cancelling their underlying saves. A declined
navigation keeps local feature/layer selection. Inspector identity remains separate
from map selection and trajectory preview. Explicit opening retains source metadata
and can reveal an already-inspected object. Map edit sessions are preserved.

Contracts 2/5/6/7/8 apply. The action uses the existing shared secondary role, not
Entity/Event identity colors. Focused-button Space opens; map Enter/Escape retain
their existing local-operation ownership. No interaction contract or styling
baseline changed; no reviewed C901 hotspot was touched.

## Automated evidence

- 278 focused tests passed, covering map/Longform navigation, the real production
  composition, map widgets/layers, edit transitions and trajectory editing.
- Final `ci_fast`: **1,735 passed, 2 skipped**, 4,384 deselected, in 87.70 seconds.
  One existing FastAPI/Starlette dependency deprecation warning.
- Ruff clean for changed Python modules/tests and the renderer. Mypy clean for
  all four changed/new production modules. Visual policy, complexity policy and
  `git diff --check` passed.
- Test-discovery policy reports one pre-existing stale baseline entry:
  `test_trajectory_edit_coordinator.py::test_switching_maps_discards_active_edit`.
  That entry is already present in HEAD while the tracked test file instead has
  `test_accepted_map_notification_does_not_discard_draft`. Neither the test file
  nor its baseline was changed in this work.

New regression cases deliver real Qt pointer and keyboard events to production
MapWidget/WorkspaceShell instances with mocked data/editor dependencies. They cover
Entity/Event point/path/region selection, shared/visible/hidden/inactive/moved zones,
local layer/trajectory state, map transform/playhead retention, explicit opening,
already-inspected targets, declined navigation, held presses/drag, save continuation
and supersession, layout re-evaluation after save, hidden targets and narrow overflow.
Additional tests verify the actual MainWindow composition uses passive map browsing.

## Rendered evidence

Run from the repository root:

```powershell
.venv\Scripts\python.exe -m docs.ux.evidence.krt64.render_navigation
```

The renderer uses the production main stylesheet, installed Segoe UI fonts, shared
StyleHelper action styles and disposable INI settings. It opens no world. Twelve
PNGs cover all six palettes during live theme switching:

- `*-states.png`: disabled, normal, hover and keyboard focus, with stable geometry.
- `*-narrow-toolbar.png`: the real toolbar at its narrow layout minimum (523 px
  with production fonts), retaining a readable direct Open in inspector route.

At smaller available toolbar widths the QAction also appears by its label in
the standard toolbar overflow menu, verified by the delivered-widget regression.
The renderer optionally captures that menu when its layout places the action there.
All six state boards and the narrow route were visually checked. Earlier font-less
or incomplete diagnostic captures were replaced or removed within this directory.

This establishes rendered and automated acceptance, not a fresh native desktop
walkthrough or human task-time benchmark. No executable build was performed.
Publication status is tracked in KRT-64.
