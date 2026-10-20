# KRT-102 — Space-held map navigation

Baseline: `7895d128`. Implementation is uncommitted. This records automated
source-level verification, not native or packaged-GUI acceptance.

## Defect and boundary

Changing a QGraphicsView to ScrollHandDrag still lets interactive scene items
accept a mouse press first. The original filled-region reproduction leaves both
scroll positions unchanged. The regression dispatches real Qt events through the
viewport and verifies an actual RegionItem is under the starting point.

`SpacePan` temporarily disables scene interaction and sends navigation events
directly through Qt's hand-scrolling path. MapGraphicsView delegates before its
marker, drawing, raster, vertex, calibration and trajectory handling. No item
flags, authored geometry, raster values or command semantics change.

The first Space press snapshots interaction, drag mode and explicit/inherited
view and viewport cursors. Auto-repeat cannot replace that snapshot. Space
release restores it once. If the mouse is still down, the controller ends Qt's
drag while interaction remains disabled and swallows the late physical release.
Focus/window/hide/grab loss and a missing release also recover safely. A deliberate
tool change ends temporary navigation and keeps the newly selected tool state;
the abandoned pan cannot place or commit an edit.

## Contracts and presentation

Contracts 2/5/6/7/8/9 apply: navigation retains drafts, selection, geometry and
tool context; a pan is not an authoring action. Existing selection, context-menu,
drawing, vertex, marker-drag and painting routes remain available without Space.
There are no new controls, color choices or QSS roles. Existing native hand/tool
cursors are restored, including custom viewport cursors and prior non-interactive
state. Narrow 260 × 180 views are exercised under all six production themes.
Focus and disabled-interaction cases are covered behaviorally. No contract change.

## Verification

Evidence is retained in ignored `artifacts/krt102/`:

| Report | Result |
| --- | --- |
| `before.txt` | Reproduced filled-region failure before the fix |
| `pan-first.txt` | 15 passed: four real-item gestures and 11 existing Space/raster cases |
| `lifecycle.txt` | 13 new lifecycle, tool-preservation and early-release cases passed |
| `labels-handles-raster.txt`, `region-label.txt` | All seven label/handle/footprint/raster cases passed after correcting a label probe initially placed at the scroll boundary |
| `interaction-regressions.txt` | 34 passed: context/double-click and ordinary navigation/drawing/vertex/raster behavior |
| `lost-release.txt` | Missing mouse release recovery passed |
| `narrow-themes.txt` | Six narrow styled theme cases passed |
| `post-pan-editing.txt` | Real raster painting and marker dragging resume after panning |

These batches cover 77 distinct focused cases, including 33 new regressions.
Successful tests were reused instead of rerunning the release suite. Tests use
software rendering with QT_QPA_PLATFORM=offscreen and KRAKEN_NO_OPENGL=1.
Source/test lint, repository-wide mypy, complexity and visual policy, test
inventory and strict documentation checks are recorded alongside these reports.

Native Windows/packaged interaction remains unverified. The earlier beta
rehearsal executable predates this runtime fix and does not contain it. The final
release candidate must be rebuilt from its committed source and retain the
existing clean-CI and native/package acceptance gates.
