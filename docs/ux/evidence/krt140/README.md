# KRT-140 — Explicit map settings ownership

Implemented in the uncommitted development worktree on 2026-11-09. KRT-140
remains In Progress. Human acceptance and native Windows DPI verification are
pending; automated and rendered evidence do not establish reduced cognitive load.

## Behavior and ownership

Feature actions now owns Feature properties across canvas, toolbar and Layers
routes. Groups expose Group actions; rasters and the base map name their own
settings routes. The reused modeless properties and date editors identify their
target and scope. The Layers opacity control names the active target and is
disabled for locked features or absent targets.

Group captions count descendant features and map surfaces, including hidden
items, and retain their collective scope with zero or one feature. Feature
captions show the containing group path. Ancestor opacity, manual visibility,
zoom limits and date values are explained without providing an inheritance
override. Icon size while zooming remains distinct from zoom visibility.
Group dates continue to affect vector features only.

Commands, storage, temporal resolution and inheritance remain unchanged.
Untouched zoom values retain their stored precision and legacy zoom basis.
Name in Layers changes only the tree label; the separate Rename action retains
existing marker and linked-record synchronization. Canvas
selection mirrors the corresponding Layers target without opening an inspector.

## Contracts and evidence

Authoring contracts 1–9 apply: ordinary settings reuse existing modeless editors;
specialized editors retain their established behavior. Shared secondary actions,
supporting captions, standard multiline input styling and semantic focus roles
provide the presentation. No authored map colors or visual-policy exceptions
were changed. Escape cancels the innermost menu/editor; accepted changes retain
existing commands and undo boundaries. Target guards reject stale editor results.

The focused regressions cover ownership, shared menu dispatch, scope counts,
hidden and locked targets, modeless target changes, map context, opacity,
temporal inheritance and persistence/undo integration. The render matrix covers
all six themes at 420/760 px dialog widths and 300/480 px panel widths, including
focus, disabled opacity and theme changes with retained draft text/selection.
Offscreen renders use Windows Segoe UI at device pixel ratio 1.0.
The generated map.layers Help was also captured at 360/640 px in all six themes;
the normal and narrow routes were visually inspected. The retained matrices are
listed in [capture metadata](renders/captures.json) and
[Help presentation metadata](help-renders/presentation.json).

Validation on 2026-11-09: 319 distinct focused regressions passed across the
primary batch and targeted recheck (the initial batch's sole remaining failure
was a reviewed Help fingerprint, corrected before its successful rerun).
Focused Ruff, repository-wide mypy (649 source files), visual policy,
complexity policy, Help inspection, offline Help generation and strict Sphinx
passed. No reviewed complexity hotspots or baseline exceptions changed.

| Documentation review field | Record |
| --- | --- |
| Reader and purpose | Map authors choosing between one feature and a collection; how-to |
| Canonical page and release | Maps guide and map.layers/map.appearance/map.visibility; Unreleased |
| Source identity | cf074014aa532eb346eb01782fbf7d07da2ef52e plus this uncommitted worktree |
| Sources reviewed | Shared feature actions, properties/date/size editors, layer panel, existing property and rename commands |
| Anchors and integration | Existing task/excerpt anchors retained; new properties/group action bindings; indexed evidence page |
| Rendered review | Offscreen production QSS, narrow properties and group scope; repaired multiline notes styling |
| Human/live Help/reader approval | Pending; no participant or native-DPI claims |

![Narrow feature settings](renders/dark_mode-420-properties.png)

![One-feature group scope](renders/light_mode-420-group.png)

![Generated map settings Help](help-renders/dark_mode-640.png)

Reproduce the render matrix with the shared pytest fixtures:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
$env:KRT140_EVIDENCE_DIR = "docs/ux/evidence/krt140/renders"
.venv\Scripts\python.exe -m pytest tests/unit/test_map_settings_scope.py -q
```

## Documentation review and human acceptance

Primary purpose: how-to, in the canonical Maps guide. Source review checks the
visible labels, acceptance/cancellation, independent settings, inherited effects,
rename synchronization and undo guidance. Existing Help anchors remain, including
the retired layer-properties anchor; new controls have dedicated inspection
bindings. Offline Help and strict Sphinx validation are recorded separately from
human reader performance.

Using the [documentation review form](../../../developer/documentation-review.md)
and [reader observation form](../../../developer/documentation-reader-testing.md),
human prose review, live Help review and unassisted reader testing remain pending.
For authoring acceptance, start from an empty world under KA-04/KA-20 rules:
create a map, put two features in a group, change only one feature, then change
the group. Repeat with a one-feature group and explain each setting's scope
before applying it. Verify the saved results and Undo independently. Record
misunderstandings, assistance and unintended sibling changes; do not report
automated checks as human acceptance.

## Map settings consolidation — 2026-11-09 follow-up

Based on committed ownership work `10818028`, this uncommitted follow-up removes
the separate Map actions button. One **Map settings** toolbar action exposes
**Scale**, **Map hierarchy** and **Detail-map footprints**, followed by a
separated **Delete map…** action. **Fit to View** remains on the toolbar. Scale,
registration, footprint visibility/editing and confirmed deletion use their
existing handlers; no commands, storage or map-setting values changed.

Contracts 2/4/5/6/7/8/9 apply. The button uses the shared secondary toolbar role.
Section headings use shared section-header/supporting-caption styles and skip
keyboard navigation. A shared menu-heading helper supplies visible headings
because native Qt separator titles were omitted in rendered output. Disabled
registration and footprint controls explain their prerequisites. Keyboard Space
opens the menu; native toolbar overflow exposes the same menu at narrow widths;
Escape dismisses it without ending an active marker appearance edit. Tests retain
the selected feature, playhead, pan/zoom and active edit when opening/dismissing.

The affected batch and targeted rerun passed 295 distinct map, hierarchy,
calibration, toolbar and Help regressions. The final menu checks include six
themes at normal/narrow requested widget widths (1400/520 px); actual offscreen
widget dimensions are recorded in the captures, since Qt enforces its minimum
size. These are software-viewport/offscreen checks, not native DPI or human
acceptance. Existing task/excerpt anchors remain; the focused `map.settings`
topic documents the consolidated route.
Focused Ruff, repository-wide mypy (650 source files), visual policy, complexity
policy, Help inspection, offline Help generation and strict Sphinx passed.
The [menu capture metadata](settings-menu-renders/captures.json) records 24
menu/toolbar images; [offline Help presentation](settings-help-renders/presentation.json)
records the focused Map settings topic in six themes at normal/narrow widths.

![Map settings with visible section headings](settings-menu-renders/dark_mode-1400-menu.png)

![Narrow settings menu](settings-menu-renders/light_mode-520-menu.png)

Reproduce menu captures with the existing shared map test fixture:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
$env:KRT_MAP_SETTINGS_EVIDENCE_DIR = "docs/ux/evidence/krt140/settings-menu-renders"
.venv\Scripts\python.exe -m pytest tests/unit/test_map_settings_menu.py -q
```

The documentation review remains how-to material in the Maps guide, now also
covering `map.settings` and calibration. Source review verified action routes,
prerequisites, unchanged confirmation, cancellation and context preservation.
Human/live Help review, reader testing and native DPI acceptance remain pending
under the forms linked above.

## Layers-to-map navigation focus — 2026-11-09

The owner reported that Space continued selecting/deselecting a Layers item
after moving the pointer back to the map. Real Qt event tests reproduced the
underlying visibility toggle for a group, marker, path and region: Layers kept
keyboard focus and consumed Space before the existing map pan handler saw it.

A view-owned `LayerNavigationFocus` now returns focus to the map on pointer
entry only when the Layers tree itself owns focus and no mouse button is held.
It does not route global keys, replace the Space-pan implementation, change
selection, or write map state. Text editors and other controls keep keyboard
ownership, and unfinished layer drags are left alone. Watching the view rather
than its replaceable viewport also supports the software viewport used in tests.

Contracts 2/5/6/8/9 apply. This is a bounded navigation-focus handoff from the
tree to the canvas, matching the owner's requested pointer transition; it is
not a general focus-on-hover policy. Existing focus presentation, themes,
authoring modes, map inspector behavior and pan interruption/release guards
remain unchanged. The Maps guide explains both Space-drag on the map and Space
visibility toggling while working in Layers.

Validation: 110 focused regressions passed, covering all four reproduced cases,
actual scroll movement, unchanged visibility/selection/position/geometry,
retained text entry and tree drag ownership, existing Space-pan lifecycle,
feature actions, inspector context and Help integrity. Focused Ruff,
repository-wide mypy (651 source files), visual/complexity policies, Help
inspection, offline Help generation and strict Sphinx passed. These are
automated/offscreen checks; native owner acceptance remains pending. The fix
and the preceding settings-menu consolidation are still uncommitted.
