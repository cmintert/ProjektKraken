# KRT-21 — Referenced-object creation

Date: 2026-10-08. Reviewed baseline: `b372e883316a923a4946b2bdf7b1ad548011c0b8`.
Authority: [KRT-21](https://linear.app/projektkraken/issue/KRT-21), revised
2026-10-08. This is an existing-route consistency fix, not a new capture mode.

## Entry-point audit

| Route | Intent and object | Selection and continuation | Disposition |
| --- | --- | --- | --- |
| Explorer New menu, Ctrl+I/E and empty-state buttons | Explicit Entity/Event creation | EditorCoordinator creates and selects; Entity requires Name + Type | Preserved |
| Entity/Event inspector Create new signal | Explicit Entity/Event creation | Same normal creation handlers and draft guards | Preserved |
| Timeline empty-state Create Event | Explicit Event creation | Normal Event handler; date from viewed playhead | Preserved |
| WikiLink/Peek Create Entity/Event | Subordinate referenced object | Existing non-selecting command; cache reconciliation resolves Peek locally | Already conforming; visible-button regressions added |
| Map Add Marker Here: New Location/Entity/Event | Subordinate object and point placement | Local UUID; object + marker in one composite; no inspector navigation | Child selection disabled; incremental composite refresh added |
| Map completed path/region: Link picker New actions | Subordinate object and geometry placement | Local UUID returned directly to feature intent; creation followed by placement | Selection disabled; placement refresh narrowed to the affected map |
| Relation authoring and detailed relation dialog | Select existing targets | RelationTargetEdit and suggestion snapshots; no Entity/Event creation route | No feature added; an open relation draft is protected by cancellation/failure tests |
| Explorer map creation, graph, Longform, other editor controls | No additional Entity/Event creation caller found | Ordinary navigation or existing-object manipulation | No new route added |
| CLI and performance probes | Noninteractive creation | No GUI origin to preserve | Outside this interaction change |

Call-site search covered CreateEntityCommand/CreateEventCommand construction,
EditorCoordinator factories, creation signals and their ConnectionManager wiring.
ContextTagCoordinator decorates the existing factories; callers still use those
factories before setting contextual selection intent.

## Behavior and boundaries

- Map contextual creation uses `select_after_create=False`, serialized by the
  existing commands. Explicit creation retains the default `True`.
- The safe object/marker composite is exactly two commands: one Entity/Event
  creation and a marker for that same UUID and object type. It propagates the
  persisted lore snapshot and the child's selection intent. Unmatched/mixed
  composites retain conservative refresh behavior.
- Standalone placement completion reloads only its map. Legacy creation results
  with absent/malformed effects reload the corresponding lore dataset and marker
  cache, without rehydrating active inspectors. Explicit legacy results still
  queue selection; contextual results do not.
- Context tags, chosen types, intentional provisional Concept defaults, map
  Location defaults and viewed-playhead Event dates remain intact. No global
  focus restoration or asynchronous navigation continuation was introduced.
- Marker composites retain atomic rollback. Path/region creation retains its
  existing two-command persistence boundary; this issue does not redesign it.
  A separate placement failure can leave the already-created lore object present.

## Interaction contract and presentation

Contracts **2/5/6/7/8/9** apply: visible creation routes, focused-control keyboard
ownership, preserved authoring context and normal reversible commands. Enter and
Escape behavior in existing pickers/editors is unchanged. No new interaction
exception or contract revision is introduced.

At the user's request, Alt-hover on a wiki link now shows the shared eye icon
as a 24 px cursor; Ctrl-hover retains the hand and ordinary prose retains the
I-beam. Alt takes precedence when both modifiers are held, matching Alt+Click.
Pressing/releasing modifiers also updates a stationary hover in Rich/Source.
The eye uses `supporting_text`, rather than Entity/Event identity colors, and
recolors on theme changes without document edits. The shared SVG loader renders
with QSvgRenderer so this cursor does not depend on an optional image plugin.

Existing primary creation and secondary supporting actions continue to use shared
StyleHelper presentation. No action availability, control geometry or stylesheet
is changed. Existing disabled Open/Peek controls still explain the caret
prerequisite; modifier cues do not take focus, select text or change undo history.
The 352 px [six-theme Rich/Source render](peek-cursor-themes.png) shows actual
editor widgets with their actual QCursor bitmap overlaid at its hotspot, because
QWidget.grab does not capture an OS pointer. It is a labeled render, not a native
desktop screenshot. The eye remains visible on all six editor surfaces. Toolbar
disabled states reflect the caret being outside the hovered link. Qt regressions
cover normal/Alt/Ctrl/combined modifiers, stationary changes and theme switching.
`check_visual_policy` passes with no new exceptions or baseline regeneration.

## Verification and remaining acceptance

Final checks: **367 focused tests passed**; `pytest -m ci_fast -q`:
**1,774 passed, 2 skipped**, with one existing Starlette/httpx deprecation warning.
Ruff across src/tests, fresh-cache mypy across all 451 source modules, visual
policy, complexity policy and dependency projections passed. No executable or
package build was run.

The focused regressions use the existing Qt/database fixtures and real command
execution against a test database. Worker delivery is simulated; the tests do
not establish native worker scheduling or a human task-time improvement.

- Entity/Event writing sources × Entity/Event targets × Peek/feature/marker
  routes × immediate/late delivery: retain text, dirty state, caret/selection,
  scroll, focused widget, workspace layout and playhead. Late delivery leaves
  the newer source context in place.
- Open link on an unresolved name exposes both creation choices in Peek.
  Visible Peek button creation resolves the local pane without stealing resumed
  writing focus. Explicit Entity/Event creation still selects the new object.
- Full path/region flow retains the generated object UUID and authored geometry
  through creation and placement completion. Point placement remains atomic.
- Cancellation and failed creation preserve an open relation draft and writing;
  failed marker creation rolls back the new object. Command serialization and
  undo/redo retain selection intent, IDs, types and dates.
- Context tags are captured at submission even if the active context later changes.
- Legacy/malformed result tests cover both selecting and non-selecting creation.
- Reviewed hotspot `c901-5a285eb9563e`, DataHandler.on_command_finished:
  complexity **33 → 30**, with its ceiling lowered to 30. The extraction stays
  within existing signal-based refresh routing and adds no public API.

Native confirmation was supplied by the user in this session: "The context is
preserved" and, after clarifying the route, "both open peek and at the bottom of
peek I can create it". The guide now explicitly names Open link/Peek link,
Ctrl+Click/Alt+Click and the two creation buttons instead of suggesting a plain
click. This records user confirmation of context preservation and the creation
route; it does not claim a recorded native walkthrough, native cursor check,
packaged-build verification or measured human task-time improvement.

An expanded architecture run exposed an unrelated existing baseline mismatch:
DatabaseService.require_connection is present at HEAD but absent from the
choke-point public-API baseline. Neither file is changed by KRT-21.
Collection policy also reports the pre-existing removed
test_switching_maps_discards_active_edit from KRT-26. KRT-21 updates only its
own intentional expansion of the existing path test to path/region cases; it
does not refresh unrelated collection debt.
