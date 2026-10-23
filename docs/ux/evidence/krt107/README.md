---
orphan: true
---

# KRT-107 — Stable timeline lanes

## Measured bounds correction

Removed the unconditional 400 px minimum from shared paint, hit and packing
bounds. Title width (including space for the possible Not yet suffix), caption
width, temporal glyph/channel extents, existing small selection padding and the
15 px inter-event gap remain measured and collision-safe. Short labels can now
share rows where their actual extents permit it; long labels remain untruncated.
The obsolete EventItem.MAX_WIDTH constant and its fixed-width assertion were
removed. Regressions cover short and long text bounds, future-title space and
lane reuse across a gap previously blocked by the 400 px floor. Current results
are in artifacts/krt107/measured-bounds-tests.txt. Older probes below predate this
correction; native review is pending.

## Current policy — chronology before compactness

The latest owner instruction supersedes both policies below. Overlapping visual
intervals follow saved chronological anchors, with stable event-ID ties. Each
event takes the highest row below every earlier intersecting event. This
longest-path recurrence minimizes lanes subject to chronology; an overlap chain
can require extra rows beyond overlap depth. Non-overlapping events can reuse
rows. Worker inputs now carry the saved numeric anchor separately from measured
collision starts, so uncertainty geometry cannot reverse chronological order.
History cannot override this canonical assignment. Pure calculation uses O(n
squared) work and O(n) storage. Tests cover reversed visual starts, equal-anchor
ties, overlap chains, and a small exhaustive precedence-constrained oracle.
Current logs are in artifacts/krt107/chronological-tests.txt. Native owner review
is pending; older verification counts and timing probes below are historical.

## Revised policy — compact first

Owner review superseded the initial retention policy below. Current packing uses
exactly the current overlap depth K, releases old lanes outside 0..K-1, repairs
within that budget, and recomputes current row heights. Valid placements within
the minimum lane count stay preferred. Zoom automatically reclaims spare rows;
Compact lanes is an optional deterministic repack, not required during zoom.
The initial policy and verification below are historical. New regression coverage
includes five-to-one automatic compaction, stale tall row heights, and old
reservations outside a reduced budget. Numeric probe results and current test
logs are retained in artifacts/krt107. Native owner acceptance remains pending.

Revised-policy verification: **450 timeline and dependency tests passed**. Ruff,
repository mypy, visual/complexity policies, Help inspection, test inventory,
strict Sphinx and offline Help builds pass. The probe now reports 4 → 8 → 4 rows
for the zoom cycle at 50, 500 and 5,000 events. Full ci_fast was not rerun for
this bounded revision. A legacy gravity fixture was given stable IDs so equal-date
tie ordering is deterministic rather than dependent on generated UUIDs.

Implementation evidence, 23 October 2026. Baseline HEAD:
`7f7f950c7c904f7e478da9ab1ddcc16f7fc242bd`. No commit or push is included.

## Reviewed design

Zoom preserves accepted lane assignments, row heights and spare row slots.
Collisions are repaired within horizontal overlap components. Capacity is bounded
by max(previous allocated rows, current overlap depth); this is a history bound,
not a bound relative to the current zoom's minimum. A deliberate **Compact lanes**
command reclaims spare rows. Initial automatic fitting establishes a compact
baseline rather than retaining provisional startup rows.

Compatible old placements are reserved before displaced/new intervals are placed.
Ordered neighbor checks include future reservations. Component-local compact
fallback greedily reuses old lane names, prioritizing smaller color classes.
Movement is heuristic, not globally minimal. The three-event counterexample is
covered; deterministic compact row count is checked against a small exhaustive
oracle. No optimizer dependency or new persistence format is introduced.

History belongs to the GUI and is separate for standard, each tag and All events.
Workers receive frozen snapshots. Existing token/generation guards reject stale
results before either scene or history acceptance. Grouped results are staged
until the whole pass succeeds. Empty replacements and final deletions discard
history. Same-world refreshes preserve surviving IDs. World selection uses the
existing Select & Restart route, which creates a fresh view/history.

## Verification and artifacts

- New focused regressions cover changed visual-start order, future reservations,
  local fallback, bounded repeated zoom cycles, idempotence, selection/playhead
  preservation, split-button direct activation, overflow submenu ownership,
  independent group histories, collapsed bands, compaction with an active worker,
  empty states and 49/50/51-event dispatch boundaries.
- The final complete timeline matrix passes **412 tests**. It initially exposed
  two legacy tests that expected
  zoom to compact automatically. They now explicitly request compaction; all
  38 advanced tests pass. Other initial matrix tests passed (410).
- Focused UI matrix: 74 passed, including action labels, overflow, visual
  presentation, new stability tests and Fit View regressions.
- Repository mypy: 493 source files clean. Ruff, complexity policy, visual policy,
  Help inspection and test inventory checks pass. No baseline ceilings weakened.
- Strict Sphinx HTML and canonical offline Help builds succeed. Existing Fit View
  inspection identity is retained; Compact lanes has its own canonical anchor.
- An initial ci_fast run with optional QT_QPA_FONTDIR override had three unrelated
  font-sensitive UI failures. All three pass without that override; the complete
  run in the standard offscreen environment recorded **2,482 passed, 3 skipped**
  and one dependency-guard failure. That guard now permits the pure standard-library
  `bisect` module specifically for timeline packing, preserving the no-Qt/no-storage
  boundary. All **36 dependency tests** pass after this correction. The final sparse
  reservation optimization was separately rechecked with **31 passing layout and
  lifecycle tests**. A redundant `--lf` run that selected the full suite was stopped;
  no clean single full-suite rerun is claimed. Logs are retained under artifacts.

Reproduce the disposable visual/packing probe with:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
$env:QT_QPA_FONTDIR = "C:\Windows\Fonts"
python -m docs.ux.evidence.krt107.probe
```

`artifacts/krt107/probe.json` records intervals, lanes and row heights at zooms
2.6, 3.2 and 2.6, using a recreation of the four Northwatch events plus Hardwood
Battle. This does not establish the exact original screenshot scales. Twelve
offscreen captures cover six palettes at 480 and 1600 pixels. Inspecting dark
1600 and light 480 confirmed readable retained events, focused Fit View and narrow
overflow. Other captures are available for review, not claimed human acceptance.

The synthetic 5,000-event probe (overlap depth 4 expanding to 8) takes roughly
13 ms for collision repair and 5 ms for the return zoom on this machine. These
are detached calculation timings, not end-to-end GUI latency guarantees.

Preserve `artifacts/krt107/` until native acceptance. It contains no existing world
data and can be regenerated with the probe. No cleanup of other artifacts occurs.

## Documentation review

Reference addition for existing timeline users in the current unreleased version:
`docs/user/timeline-and-calendars.md`, topic `timeline.viewing`. Preferred route:
Fit View arrow → Compact lanes; narrow route: More actions → Fit View submenu.
Acceptance is immediate; it changes presentation only. Recovery is continued zoom
or another compaction; it is not an authored undo step. Existing dates, time,
selection, Help anchors and navigation actions remain intact.

Authoring contracts 2/5/6/7/8/9 apply. The split control uses shared Phosphor/menu
presentation and global secondary roles; identity and selection roles retain
their existing meanings. Empty-state disabled eligibility and direct Fit View
activation are tested. No keyboard shortcut is required. The documentation
review and reader-observation forms remain the authority for human review.

Native DPI review, human prose approval, live Help inspection, independent reader
observations and owner acceptance of zoom stability/spare rows are **Pending**.
Offscreen evidence and build success do not establish those outcomes. Linear
remains In Progress while the implementation is uncommitted.
