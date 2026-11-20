# KRT-116: Smooth bypasses and separated crowded tracks

Implementation evidence, 29 October 2026. Baseline router:
`9b6554bebce91f086c45bbcbca27e7c7beb68b98`, branch
`dev/krt-111-event-anchors`. The owner authorized a local commit on 29 October,
reusing the recorded checks. Native Windows/DPI readability and owner acceptance
are pending.

## Implemented boundaries

Clear space retains the original cubic. Painted blockers form practical cluster
envelopes with broad, tangent-continuous bypasses on either side. Forward
bypasses are monotone and end at their intended sockets. Reserved empty label
space is not an obstacle. Rounded orthogonal fallback remains available.

Corridors use coordinated tracks, never modulo-eight reuse. Smooth tracks prefer
8 px spacing. When broad turns cannot fit, nested rounded routes use distinct
3.5 px turning columns checked against a 3 px stroke (selected pen: 2.5 px).
Detours and alternative searches are bounded independently of strand colours.
Shared runs are rejected, not merely penalized. Branches/merges can fan out
outside a 24 px common-terminal neighbourhood. Comparisons clip at the actual
circle boundary; an entire long flattened segment is never exempted.
Independent wires can still cross at a point. Unsafe candidates are rejected;
failed routing does not paint a false connection.

Validation covers side tangents, selected strokes, arrowheads, intentional source
contact and self-intersections. The fallback search cannot satisfy its initial
side with an out-and-back stub that simplification turns vertical. Local port
corridors allow reverse-direction forks to separate near their source.

Allocation precedes viewport culling. Normalized geometry and a content-anchored
floor keep routes stable during simple pan, selection and theme changes.
Production background painting uses completed paths; a GUI-owned single-shot
timer coalesces cold preparation outside paint. There are no new worker threads,
database/solver calls, settings or mutations. Cold preparation still uses the GUI
thread and can be noticeable on dense geometry; this is not an asynchronous
responsiveness claim.

## Reproduce and inspect

Use the project Python with `QT_QPA_PLATFORM=offscreen`:

```text
python -m scripts.build_help
python -m scripts.render_timeline_wire_refinement --phase before
python -m scripts.render_timeline_wire_refinement --phase after
```

`before` loads the immutable original router through Git without checkout.
Both phases use the same current harness and disposable preferences. Real-widget
captures compare the chosen router in the current shell/cache, rather than
recreating the whole historical application. `--scenes-only` skips the density
sweep. No saved world is opened. Segoe UI is loaded explicitly.

Each phase retains dark/light, 400/1200 px and 0.8x/2x comparisons, plus density
fixtures with 5/20/50/100 wires. Narrow images are viewport crops with unchanged
coordinates and stroke widths.

| Case | Before | After |
| --- | --- | --- |
| Single blocker | [Original](before/dark_mode-single-blocker-0.8-1200.png) | [Smooth bypass](after/dark_mode-single-blocker-0.8-1200.png) |
| Staggered blockers | [Original](before/dark_mode-staggered-cluster-0.8-1200.png) | [Cluster bypasses](after/dark_mode-staggered-cluster-0.8-1200.png) |
| Multiple wires, branches/merges | [Original](before/dark_mode-branches-and-merges-2.0-1200.png) | [Separated wires](after/dark_mode-branches-and-merges-2.0-1200.png) |
| 100-wire corridor | [Repeated tracks](before/dark_mode-100-0.8-1200.png) | [Compact tracks](after/dark_mode-100-0.8-1200.png) |
| Actual nine-Event Timeline | [Original router](before/widget-dark_mode-2.0-1200.png) | [Current router](after/widget-dark_mode-2.0-1200.png) |

The actual Timeline includes several Follow Event connections, three intervening
Events and a duration Event, preserving real captions, marks and ordinary lane
placement. Geometry fixtures additionally force multiple blockers into the wire
trajectory instead of relying on lane packing to put them there.

## Measurements and verification

Each phase's `metrics.json` and `scenes.json` retain latency samples, detour bounds,
path elements, missing routes, protected-body collisions, stroke intersections
and shared straight length. The latter is an independent flattened-geometry
measure, not a complete curved-overlap or human traceability metric. The
100-wire regression independently checks every pair of complete 3 px strokes.

Recorded median cold routing in milliseconds, three runs on the same fixture:

| Wires | 0.8x before | 0.8x after | 2x before | 2x after |
| --- | ---: | ---: | ---: | ---: |
| 5 | 10.66 | 1.38 | 7.17 | 1.63 |
| 20 | 152.83 | 12.33 | 144.68 | 13.73 |
| 50 | 938.37 | 113.36 | 887.16 | 76.48 |
| 100 | 3610.28 | 18.71 | 3491.72 | 551.18 |

These are geometry timings, not native frame times or timing assertions.
Compact routing at 100 wires/0.8x explains its lower cost than 50 broad sweeps.
Every density/zoom case retains every path with zero protected-body collisions,
shared straight length and pairwise stroked intersections. Multi-blocker fixtures
also retain every path and zero shared straight length; point crossings are
recorded separately. Widget records additionally measure cold routing, warm
captures and pan/selection/zoom cache misses.

In the nine-Event real-widget probe, all eight theme/width/zoom combinations
recorded zero repaint, selection and simple-pan cache misses. Cold routing was
about 298 ms at 0.8x and 28 ms at 2x, versus roughly 460 ms and 37 ms with the
original router in the same shell. Warm captures take roughly 4-6 ms. Zoom
recomputes routes. These are offscreen samples; cold preparation still blocks the
GUI thread while it runs.

- Final shared-terminal/local-port routing matrix: **47 passed**,
  `logs/krt116-routing.xml`.
- Timeline/lanes/async layout/interaction/grouping matrix: **126 passed**.
- Full Timeline plus relevant architecture and Help: **588 passed, 1 skipped**,
  92.07 s, `logs/krt116-final-regression.xml`; one existing Qt mouse-event
  deprecation. This final run includes socket clipping, local port corridors,
  crossing comparison, smooth duration-side returns and coalesced preparation.
- Repository Ruff and mypy passed (568 production files). Complexity, visual and
  test policies passed. No reviewed C901 hotspot or policy allowance changed.
- Offline Help generation, inspection and strict Sphinx HTML passed. Actual
  HelpViewer dark/light captures at 400/680 px are retained under `after/help-*`;
  search for Show dependencies reaches `timeline.viewing`.

Coverage includes four endpoint combinations, explicit zero-duration ends,
duration caps versus detached measures, reverse/same-row routes, blocked
arrowheads/sockets, long-grid bounds, grouped copies, hidden/unplaced Events,
caption previews, obstacle ordering, pan/culling/selection stability, horizontal
path culling and preparation outside production paint. `Wire` and the ordered
`route_wires` interface remain compatible.

## Presentation and documentation review

Preserved roles: `timeline_dependency_0` through `_7`, Event marks, supporting
captions, shared controls and selection emphasis. No theme, keyboard, gesture or
control changes. Contracts 2/5/6/8/9 preserve selected Event, drafts, caret,
Viewing/World current time and undo. Existing KRT-114 six-theme toggle/focus/
disabled evidence is retained; this refinement adds dark/light normal/narrow
route evidence and maximum-selection-width geometry checks.

Review follows the [documentation form](../../../../developer/documentation-review.md).
Reader: Timeline users tracing saved Follow Event sources; primary purpose:
control reference. Canonical page: `docs/user/timeline-and-calendars.md`, topic
`timeline.viewing`, anchor `help-inspect-timeline-show-dependencies`. The small
reference change explains smooth bypasses, separate tracks, point crossings and
omitted unsafe routes. IDs and anchors are unchanged; only the two affected
source reviews were updated individually.

Native Windows/DPI, live Help/focus/overflow, human prose approval and tracing a
selected connection are **pending**. Use the existing
[reader-testing form](../../../../developer/documentation-reader-testing.md) for
later observations. Keep this issue and parent acceptance open. The local commit
reuses the recorded checks; no new test suite was run for that delivery. Normal
commit hooks remain enabled. Push, package and release are separate actions.
