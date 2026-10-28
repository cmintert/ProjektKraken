# KRT-114 Timeline dependency strands

Implementation and verification record, 28 October 2026. Baseline:
`94c22f49d336b5bd83b7af8f1bea19d83b4abd35`; application 0.20.1.
This record accompanies the KRT-114 implementation commit. Native Windows
interaction/DPI, owner UX
acceptance and human documentation review remain pending.

## Delivered behavior and review boundaries

Show dependencies starts enabled beside Snap to Events, overflows through More
actions, and synchronizes with Settings → Timeline through the canonical local
settings adapter. It changes presentation only. Complete accepted-world Follow
Event references define colored connected components; filtered, collapsed and
unplaced Events remain part of strand identity.

The owner clarified that wires must connect to event sides and use readable,
ordered node-editor forms. The renderer uses actual painted endpoint-row/text
extents for sockets, horizontal side tangents, arrows, stable branch ordering,
smooth cubics and obstacle-aware rounded routing points. Crossings receive a
routing penalty; crowded fallback tracks have separate offsets. It protects
actual text/marks by routing around them, rather than clipping caption-sized
pieces out of a wire. Unavoidable crossings are not claimed to be eliminated.
The relevant reference is SideFX's [node wiring and routing guide](https://www.sidefx.com/docs/houdini/network/wire.html).

Endpoint rows and duration caps retain start/end meaning; detached duration
measures do not become ports. No timing solver, SQL or command runs during
painting. Geometry caches survive selection and simple panning. Offscreen wires
are culled without changing topology; long-wire routing grids retain local port
corridors and outer gutters instead of every intervening label corner. Transient
caption previews refresh separately from accepted topology.

Semantic roles `timeline_dependency_0`–`timeline_dependency_7` are defined in all
six palettes and the built-in recovery themes, with at least 3:1 stroke contrast.
The repository vocabulary and its authoritative Linear counterpart are updated.
Contracts 2/5/6/8/9 apply. There are no new visual/complexity-policy exceptions.
Lane placement, temporal authoring, keyboard ownership, drafts, selection,
Viewing/World current time and undo remain governed by their existing paths.

## Automated and rendered evidence

- Focused Timeline/Settings/Help/architecture matrix: **409 passed, 1 skipped**;
  JUnit: `logs/krt114-focused.xml`. The warning is an existing deprecated Qt
  mouse-event constructor in the ruler-scrubbing test.
- Final routing/interaction/stable-lane check after bounded-grid, culling and
  transient-caption, monotone-handle and complete crowded-route refinements:
  **60 passed**; JUnit:
  `logs/krt114-final-routing.xml`. These checks overlap the preceding matrix.
- Repository Ruff and mypy pass; mypy checks 566 production files. Visual,
  complexity, test-policy and Help inspection checks pass. No reviewed C901
  hotspot was changed and no allowance ceiling was raised.
- Offline Help generation and strict Sphinx HTML pass. The new inspection
  paragraph and search target are validated independently of build success.
- Reproduce the 24 UI captures with
  `python -m scripts.render_timeline_dependencies` using offscreen Qt. It uses
  disposable preferences and synthetic events, without opening a saved world.
  Captures use Segoe UI at 10 pt, widths 1200/400 px and zoom factors 2.0/0.8.

| Theme | Sparse / normal | Sparse / narrow | Crowded / normal | Crowded / narrow |
| --- | --- | --- | --- | --- |
| Dark | [Image](dark_mode-sparse-1200.png) | [Image](dark_mode-sparse-400.png) | [Image](dark_mode-crowded-1200.png) | [Image](dark_mode-crowded-400.png) |
| Light | [Image](light_mode-sparse-1200.png) | [Image](light_mode-sparse-400.png) | [Image](light_mode-crowded-1200.png) | [Image](light_mode-crowded-400.png) |
| Fantasy | [Image](fantasy_mode-sparse-1200.png) | [Image](fantasy_mode-sparse-400.png) | [Image](fantasy_mode-crowded-1200.png) | [Image](fantasy_mode-crowded-400.png) |
| Imperial | [Image](imperial_mode-sparse-1200.png) | [Image](imperial_mode-sparse-400.png) | [Image](imperial_mode-crowded-1200.png) | [Image](imperial_mode-crowded-400.png) |
| Cyberpunk | [Image](cyberpunk_mode-sparse-1200.png) | [Image](cyberpunk_mode-sparse-400.png) | [Image](cyberpunk_mode-crowded-1200.png) | [Image](cyberpunk_mode-crowded-400.png) |
| Muted light | [Image](muted_light_mode-sparse-1200.png) | [Image](muted_light_mode-sparse-400.png) | [Image](muted_light_mode-crowded-1200.png) | [Image](muted_light_mode-crowded-400.png) |

The captures establish offscreen rendering, not human readability or usability
acceptance. Dense fixed-position timelines can require horizontal/vertical
scrolling. Native DPI, keyboard/focus and checked-overflow presentation require
owner review in the actual workspace.

Additional presentation checks: [keyboard focus](toggle-focus.png),
[disabled control](toggle-disabled.png), [checked overflow action](overflow-checked.png),
[narrow offline Help](help-dark_mode-400.png),
[normal offline Help](help-light_mode-680.png), and
[generated HTML manual](manual-html.png). The HTML capture used software graphics
after the offscreen Chromium GPU context failed; no application rendering setting
was changed. The excerpt and search verification reached `timeline.viewing` at
`help-inspect-timeline-show-dependencies`.

## Documentation review form

| Field | Record |
| --- | --- |
| Issue / reader / purpose | KRT-114; Timeline users with saved Follow Event sources; existing how-to and control reference |
| Canonical page / release | `docs/user/timeline-and-calendars.md`; 0.20.1 development worktree |
| Source review | Toggle labels/default, canonical settings flow, pure topology, endpoint rows, route ordering, uncertainty, persistence and cancellation-independent display behavior inspected |
| Topic / anchors | `timeline.viewing`; existing anchors preserved; new `help-inspect-timeline-show-dependencies` binding and paragraph |
| Source identity | Baseline above plus the accompanying KRT-114 implementation commit; reviewed fingerprints in `docs/help-inspection.json` |
| Automated review | Tests, inspection/search route, offline Help and strict HTML build as recorded above |
| Rendered review | Synthetic six-theme UI matrix and generated Help/HTML; agent inspection, not human acceptance |
| Human prose / live Help approval | Pending |
| Reader round / independent task performance | Pending; no participant or benchmark result claimed |

Use the [documentation review form](../../../developer/documentation-review.md)
and [reader-testing protocol](../../../developer/documentation-reader-testing.md)
for later human acceptance. Keep KRT-114 In Progress while native/owner acceptance
remains pending.
