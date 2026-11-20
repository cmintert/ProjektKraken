# KRT-115: Dependency visibility and trails

Implementation evidence, 29 October 2026, on the KRT-116 routing baseline
`d6cc01390b1aa68562e3a84453634aa5a103e01d`. This record accompanies the KRT-115
implementation commit. No package or release is claimed. Native Windows/DPI,
owner readability, human prose/live Help approval and reader testing remain pending.

## Behavior and boundaries

Dependencies: All / Selected / Trail / Off replaces the Boolean checkbox.
The menu spells out Show dependency trail. Selected shows direct incident
connections; Trail uses the whole accepted-world strand, including branches,
merges and hidden intermediate Events. Repeatable colors never define membership.
No Event selection, hiding, automatic fitting or date editing is added.

Routing still receives all eligible copies and obstacles. Filtering happens at
paint time, preserving shared routes, lane positions, drafts, viewport, playhead
and history. The selected target comes from accepted selection publication;
pending scene clicks cannot switch its trail. Clearing selection removes the
target; reselecting the same accepted Event restores it without requiring global
navigation to change. World replacement and accepted mutations update topology.

The canonical local key is `timeline/dependency_visibility`. Fresh/default is
Selected. An absent new key reads legacy true/false as All/Off without writes;
an existing invalid new value recovers to Selected. New choices take precedence.
Reset clears both keys. Toolbar/overflow/Settings share the mode values, and an
open Settings draft retains its edit when the toolbar changes the saved value.

## Automated verification

- Focused dependency, Settings, interaction, date navigation, time coordinator,
  overflow, grouped integration, routing, delayed-navigation and Help matrix:
  **238 passed** (`logs/krt115-focused.xml`). One existing deprecated QMouseEvent
  constructor warning is unrelated to this change.
- After reviewing the actual generated excerpt, added a four-mode excerpt check
  and trail search query: **28 passed** in the updated Help suite
  (`logs/krt115-help.xml`; includes overlap with the earlier matrix).
- Repository mypy, Ruff, visual policy, complexity policy, reviewed Help inventory,
  offline Help generation and strict Sphinx **passed**. Mypy checked 570 source
  files. No reviewed complexity hotspot was modified or policy exception added.

The tests cover chains/branches/merges, equal-color disconnected strands, hidden
bridges, isolated/empty selection, accepted publication and restored selection,
deletion/restoration/splitting, world replacement, exact cached paths and unchanged
positions, migration/reset/reopen, keyboard menus, Settings synchronization and
draft conflicts. Existing endpoint/grouping/uncertainty/routing regressions remain.

## Reproduction and retained artifacts

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.venv\Scripts\python.exe -m scripts.build_help
.venv\Scripts\python.exe -m scripts.render_timeline_dependency_visibility
```

Settings are isolated in a temporary directory; no saved world is opened. Windows
Segoe UI fonts are explicitly loaded for readable offscreen captures. Retain the
18 palette/mode/control sheets, two Help captures and [raw measurements](metrics.json)
beside this record; earlier KRT-114/KRT-116 evidence is preserved separately.

Each mode sheet stacks **All, Selected, Trail, Off** in that order. The selected
Event is The march begins. Offscreen examples show the current viewport; other
trail members remain reachable by ordinary scrolling. Normal views use 1200 px
and 2× zoom, narrow views 400 px and 0.8× zoom. No native DPI claim is implied.

| Palette | Normal modes | Narrow modes | Focus/menu/disabled |
| --- | --- | --- | --- |
| Dark | [1200 px](dark_mode-1200-modes.png) | [400 px](dark_mode-400-modes.png) | [Controls](dark_mode-control-states.png) |
| Light | [1200 px](light_mode-1200-modes.png) | [400 px](light_mode-400-modes.png) | [Controls](light_mode-control-states.png) |
| Fantasy | [1200 px](fantasy_mode-1200-modes.png) | [400 px](fantasy_mode-400-modes.png) | [Controls](fantasy_mode-control-states.png) |
| Imperial | [1200 px](imperial_mode-1200-modes.png) | [400 px](imperial_mode-400-modes.png) | [Controls](imperial_mode-control-states.png) |
| Cyberpunk | [1200 px](cyberpunk_mode-1200-modes.png) | [400 px](cyberpunk_mode-400-modes.png) | [Controls](cyberpunk_mode-control-states.png) |
| Muted light | [1200 px](muted_light_mode-1200-modes.png) | [400 px](muted_light_mode-400-modes.png) | [Controls](muted_light_mode-control-states.png) |

Agent visual review checked readable mode/action labels, checked menu state,
disabled controls, narrow More actions access and the four visibility states.
Roles remain secondary actions/focus plus `timeline_dependency_0`–`_7`; no palette
or policy-baseline exceptions were added. Contracts 1/2/4/5/6/7/8/9 apply.

The real-layer measurements use 5/20/50/100 independent source/target pairs,
with clear rows or denser interfering label geometry. Each warms the full routing
cache, then cycles all modes and five selected targets. Every case records
**zero reroutes, no missing routes and unchanged paths/positions**. The fixture
has one-edge strands, so branching semantics are established by tests and the
separate capture fixture. These are local paint-operation measurements, not
end-to-end frame-rate, flicker or native interaction guarantees. Raw timing
samples, separate cold routing latency and per-mode eligible counts are retained.

## Documentation review

Review follows the [documentation form](../../../../developer/documentation-review.md).
Reader: Timeline users tracing saved Follow Event sources. Primary purpose:
control reference, with a short how-to route. Canonical page:
`docs/user/timeline-and-calendars.md`; topic `timeline.viewing`; excerpt
`help-inspect-timeline-show-dependencies`. Existing anchors/IDs remain intact.

The actual contextual excerpt includes all four definitions in its first
paragraph; the manual table and procedure provide further detail. Search for
Show dependency trail reaches the Timeline topic. Generated Help rendering is
captured at [400 px dark](help-dark_mode-400.png) and
[680 px light](help-light_mode-680.png). Source inspection, generated HTML checks,
offscreen companion rendering and automation are separate from human acceptance.

The authoritative Linear vocabulary and repository counterpart were updated
together. The Linear dependency appendix previously contained an encoding-error
traceback; that affected appendix was restored from the maintained repository
wording and updated for these four modes. The rest of the document was retained.

Human reviewer/date, live Help contexts, owner acceptance and independent reader
rounds are **pending**. Use the
[reader-testing form](../../../../developer/documentation-reader-testing.md) for
future observations. KRT-115 remains In Progress pending the remaining acceptance.
