# Review of other timeline visual indicators

Reviewed 2026-10-07 against `e8a00a8bdc30efa42985883940901d395750712a`.
This extends the [KRT-50 baseline](README.md) using the same screenshot-first
method. Production code and world data are unchanged.

## Findings that need follow-up

### Collapsed groups discard occurrence uncertainty

Compare the two event rows and collapsed band in
[expanded/collapsed group comparison](indicators/groups-expanded-collapsed.png).
The full event rows show a year window and an uncapped approximate halo. The
collapsed band only receives their representative dates, so both become single
ticks without those cues. At this zoom the ticks are barely visible.

`GroupBandManager.set_grouping_config` and its collapse path load
`[e.lore_date for e in events]`; `GroupBandItem.paint` draws plain vertical ticks.
Its one-unit noncosmetic pen becomes approximately 0.06 screen pixels wide at
1.2 pixels/day with a base scale of 20. The group chevrons and titles survive,
but the temporal meaning does not. This is confirmed information loss in the
collapsed rendering. Whether a creator reads the tick as an exact date remains
a human interpretation question. Preserve uncertainty and readable screen-space
marks in any simplified group grammar.

The group screenshot uses isolated production bands/overlay with the same tick
inputs as the manager. It is not a claim of complete grouping UI-flow validation.

### Snapping does not disclose the uncertain layout anchor

[Snapped year-only occurrence](indicators/navigation-snapped-uncertain.png)
shows the playhead through the hollow midpoint of the year window.
`TimelineView._manual_playhead_time` snaps against `event.lore_date`. A concrete
probe at `444687.5` (five days after the anchor) returns `444682.5`, the year
midpoint. The 12-pixel snap threshold is applied in screen space correctly.

Navigating to a representative coordinate can be useful. The missing distinction
is between the precise date now being viewed and the event's uncertain occurrence
date. Nothing in this timeline widget explicitly names the snapped point as a
layout anchor. Do not remove navigation or treat this as storage corruption;
review a clear navigation cue that preserves the event's uncertainty.

### Viewed time and world time depend heavily on color

[Separate lines](indicators/state-during.png),
[coincident lines](indicators/navigation-coincident.png), and
[380-pixel view](indicators/navigation-narrow.png) show the issue.
The playhead has a red handle/line, and world current time has a blue line without
a header label or handle. At the captured year zoom, the blue line appears solid,
despite `CurrentTimeLineItem` defining a dashed cosmetic pen. This observation
does not establish why the dashed stroke becomes effectively continuous.
When dates coincide, the lines merge into one composite mark with one handle.

The toolbar's Set Current Time / Return to Current Time actions explain their
operation, but do not label the marks or give their date values. At narrow width
they move behind the visible overflow button. That preserves a route; it reduces
immediate identity feedback. The sticky ruler text describes the **left viewport
edge**, not the viewed/playhead date: the year overview says Year 1216 while the
review events are in 1218. The label is mechanically correct but should not be
used as proof that the currently viewed time is explicit.

Hover and drag states only lighten the playhead handle:
[hover](indicators/navigation-hover.png), [drag](indicators/navigation-drag.png).
Their geometry stays constant. These captures set presentation flags; they do not
demonstrate a completed mouse drag or its persistence.

These navigation/grouping findings are tracked in
[KRT-57](https://linear.app/projektkraken/issue/KRT-57/preserve-uncertainty-and-time-identity-in-timeline-navigation-and).

### Future fading makes captions too faint

Compare [before](indicators/state-before.png),
[during](indicators/state-during.png), and [after](indicators/state-after.png).
Definitely future items fade, including their date captions. An uncertain year
inside its possible range and an approximate date without hard bounds stay at
normal opacity. This correctly avoids declaring them definitely future or past
from a midpoint alone.

However, `EventItem.set_temporal_state` applies 0.7 opacity to the **whole item**.
The caption already uses `text_dim`, and that extra fade makes it hard to read.
[Contrast diagnostics](indicators/text-contrast.json) calculate ideal solid-stroke
text contrast against the actual scene `app_bg`, after opacity compositing:

| Palette | Normal caption | Future caption | Future title |
| --- | --- | --- | --- |
| Dark | 5.28 | 3.37 | 6.07 |
| Light | 4.23 | 2.54 | 5.72 |
| Fantasy | 4.82 | 3.08 | 6.46 |
| Imperial | 5.48 | 3.24 | 7.50 |
| Cyberpunk | 3.93 | 2.48 | 6.85 |
| Muted light | 3.14 | 2.12 | 3.77 |

The project's [visual vocabulary](../../visual-interaction-vocabulary.md) requires
4.5:1 for touched normal text. All six future captions fall below that target;
normal captions already fall below it in three palettes. These are token/opacity
calculations, not anti-aliased pixel measurements. Preserve a future-state cue
while keeping names/dates readable, using an appropriate shared caption role.

The `past` flag means the start occurrence is past, not that a duration has ended.
At day 190 the 240-day event and June-start/90-day event both have `past=True`
while still potentially or certainly ongoing. Past items are not given a separate
paint treatment. This is not proof of an incorrect state calculation; any added
past/ongoing indicator must explicitly decide which question it answers.

### Toolbar focus has no visible distinction

Compare [focused dark theme](indicators/theme-dark_mode.png) and
[same scene, toolbar unfocused](indicators/toolbar-unfocused.png).
Go to date owns keyboard focus in the former (`hasFocus=True` in diagnostics),
but no visible focus treatment distinguishes it. All six theme captures confirm
the same focus ownership. This is a rendered focus-feedback defect; it should
use shared StyleHelper action presentation, preserving dimensions across states.

Caption/focus findings are tracked in
[KRT-58](https://linear.app/projektkraken/issue/KRT-58/keep-timeline-captions-readable-and-toolbar-keyboard-focus-visible).

## Grammar that should be preserved

| Indicator | Screenshot result | Assessment |
| --- | --- | --- |
| Minute-precision point | Filled diamond; date/time caption | Clear geometric distinction from uncertain anchors in these captures |
| Hour/day/month/year precision | Hollow anchor, capped dotted finite window | Preserves an occurrence interval instead of inventing a precise date |
| Compact finite occurrence | Fixed 16-pixel hollow/capped symbol | Keeps uncertainty category; deliberately loses scaled width |
| Calculated year | Same year window, calculated caption | Qualification stays in text; no extra certainty is invented |
| Approximate/uncertain/estimated date | Hollow anchor, fixed 32-pixel uncapped fade | Does not fabricate a bounded interval; qualifiers share broad grammar |
| Before/after | One hard cap and fade toward open side | Retains direction without inventing the missing endpoint |
| Explicit occurrence window | Two hard caps and hollow anchor | Finite window remains distinct from solid duration presence |
| Independent finite endpoints | Hatched edges around a solid middle | Correctly distinguishes possible presence from certainly occupied interval |
| Duration longer than start uncertainty | Solid certain core plus hatched possible edges | Retain this successful presence grammar alongside a future duration measure |
| Invalid expression/unavailable calendar | Question-mark occurrence symbol and explanation | Appropriate unresolved category for actual errors |
| Selected item | Contrasting outline; hollow anchors remain hollow | Selection does not convert the anchor to certainty |
| Ruler/grid | Quarter/year/day levels change with zoom; collision avoidance | Calendar boundaries match the shown item positions; no wrong-date defect reproduced |
| Group heading | Chevron, identity stripe, elided text | Collapse state stays visible; full navigation interaction not tested here |

Source-to-image checks used `temporal_geometry.py`, `event_item.py`,
`temporal_anchors.py`, `timeline_view.py`, `timeline_scene.py`,
`timeline_ruler.py`, `group_band_item.py`, `group_band_manager.py`,
`group_label_overlay.py`, and the TimelineWidget toolbar.

Hour/day compact marks look alike at broad zoom, while captions retain their
supplied components. At high zoom their windows expand to the true precision
intervals. Approximate, uncertain and estimated point assertions also share a
soft mark: these screenshots do not establish that every qualifier needs a unique
shape. Seek fresh interpretation before adding more visual categories.

Within KRT-50, [endpoint/error comparison](indicators/endpoints-errors.png) confirms
that valid **one-sided start plus duration** and **approximate independent
endpoints** also collapse into unresolved duration boxes. That extends the known
approximate-start defect. Preserve their valid one-sided/soft occurrence grammar
when implementing separate duration/presence presentation. Finite endpoint cores
remain semantically correct and must not be discarded.

## Capture index

All 23 images are unannotated production-widget captures, with full item captions
and the native ruler. Controlled rows preserve direct comparison; context comes
from other event rows, grid and scale. Theme captures include selected normal and
future items, and actual toolbar keyboard focus.

| Comparison | Images |
| --- | --- |
| All point/occurrence categories | [Visible](indicators/occurrences-visible.png), [compact](indicators/occurrences-compact.png) |
| Day-window transition at 24 pixels | [23px](indicators/day-below-24px.png), [25px](indicators/day-above-24px.png) |
| Precision windows at 1000 pixels/day | [Close view](indicators/precision-close.png) |
| Endpoints and actual errors | [Comparison](indicators/endpoints-errors.png) |
| Temporal state | [Before](indicators/state-before.png), [during](indicators/state-during.png), [after](indicators/state-after.png) |
| Six palettes, selection and keyboard focus | [Dark](indicators/theme-dark_mode.png), [light](indicators/theme-light_mode.png), [fantasy](indicators/theme-fantasy_mode.png), [imperial](indicators/theme-imperial_mode.png), [cyberpunk](indicators/theme-cyberpunk_mode.png), [muted light](indicators/theme-muted_light_mode.png) |
| Focus comparison | [Toolbar unfocused](indicators/toolbar-unfocused.png) versus focused dark above |
| Handle states | [Hover](indicators/navigation-hover.png), [drag](indicators/navigation-drag.png) |
| Time identity | [Coincident](indicators/navigation-coincident.png), [narrow](indicators/navigation-narrow.png), [snapped uncertain](indicators/navigation-snapped-uncertain.png) |
| Group simplification | [Full event reference](indicators/groups-reference.png), [production bands](indicators/groups-expanded-collapsed.png) |

## Validation, limits and next steps

Reproduce with `.venv\Scripts\python.exe docs/ux/evidence/krt50/indicators.py`.
The [renderer](indicators.py), [semantic diagnostics](indicators/render.json),
contrast diagnostics and screenshots are retained as durable evidence. Temporary
QSettings are isolated and removed at exit. No world database is opened.

**164 existing focused tests passed** across temporal display, timeline rendering,
calendar boundaries, ruler, temporal state, interaction and grouping. One existing
Qt mouse-event deprecation warning was emitted. The evidence script passes Ruff
and formatting checks. All 23 capture states were visually reviewed. No production
code, executable build or commit was made; no policy baseline was changed.

These are offscreen widget captures, not a full application/user session. The
timeline's normal/selected states, six palettes, toolbar focus, narrow layout and
simulated handle hover/drag are covered. Disabled controls, full keyboard/drag
flows, custom calendars, screen-reader behavior, every ruler level transition and
full grouped-world persistence are not claimed. Existing tests cover some of
those mechanics but do not establish visual usability. Fresh human interpretation
and matched before/after evidence remain necessary for accepting a fix.

Implementation should preserve authoring contracts 1/2/4/5/6/7/8/9 as applicable,
selection and playhead/world-time separation. Use theme-owned identity, supporting
caption, focus and selection roles plus shared StyleHelper controls. Avoid alarm
colors for historical uncertainty. Recheck disabled states, focus, narrow overflow
and all palettes, then run the visual policy checker for production presentation
changes. No contract revision or new exception is proposed by this research.
