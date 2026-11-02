# KRT-131 recurrence verification

This records implementation evidence for optional recurrence on ordinary Events.
The working tree is uncommitted; no release, commit or owner acceptance is claimed.

## Behavior and architecture

- The Event model retains its existing identity and serialization. Its optional
  schedule is versioned attributes metadata; display occurrences are detached
  projections and never enter database, search, graph or world-state pipelines.
- The evaluator seeks to the requested window and pages both sparse candidates
  and dense results. Calendar dates are calculated from the authored anchor,
  with custom weeks, variants, leap days, skipped fifth weekdays and both directions.
- Date-frame Save Changes owns schedule and bound drafts. Content autosave
  preserves current stored recurrence; explicit schedule saves reject stale
  baselines. Tests cover discard and newer edits during save acknowledgement.
- Timeline filters feed one fixed-height occurrence strip. Compact clusters
  expose date lists and bounded continuation. The ordinary anchor remains the
  only timing authority; generated markers cannot drag or become dependency sources.
- Portable calendar context recognizes supported recurrence metadata and keeps
  future versions opaque. No database migration or new worker slot was added.

## UI contract review

Contracts 1–9 apply. The visible Repeats disclosure uses shared inspector controls;
calendar fields and named weekdays retain existing input conventions. Event
identity uses the shared Event painter with a circle instead of a diamond,
colored through event_main. Names and dates match ordinary Event typography.
The strip uses shared surface, supporting-caption, selection and focus roles.
There are no local palette literals or visual-policy exceptions. Native button
semantics provide keyboard access without a permanent button face; this is a
timeline glyph, not a new action-control variant.

Selection identifies the source Event; date lists explain the particular
occurrence without moving time. Schedule edits stay in the ordinary inspector.
Marker changes do not repack ordinary lanes across zoom visibility thresholds.

## Verification record

Base revision: `6ca4d3b01c2a82c4ca8a53f5b95bf38352023e85`, dirty working tree,
Python 3.13.14 / PySide6 and Qt 6.10.1 on Windows, 2 November 2026.

- `pytest -m ci_fast -q --no-cov`: **3,210 passed, 3 skipped**, 4,516 deselected.
  A prior pass before the last bounds/recovery regressions had 3,208 passed.
- The final one-line cluster-selection clearing correction, added billion-unit
  cases and keyboard-menu assertions were checked afterward with
  `pytest tests/unit/test_event_recurrence.py tests/unit/test_recurrence_integration.py
  -q --no-cov`: **37 passed**. The complete ci_fast suite was not rerun after
  that final selection correction; its earlier pass is not exact final-source coverage.
- Repository-wide `mypy src`: no issues in 602 source files. Ruff and the
  complexity, visual and Help inspection policies passed. Complexity allowances
  remain untouched; no reviewed hotspot was edited.
- Offline Help generation and strict Sphinx HTML builds passed. The new task
  was rendered through the real offline Help viewer at 360/640 pixels in six
  themes; normal and narrow dark/light renders were inspected.

Local logs and generated images are under
`artifacts/krt131/`; these are disposable verification output, not packaged assets.

The initial ci_fast run exposed Help-topic ordering and a preparation dependency
guard violation, both corrected. A dark-theme menu-state assertion passed in an
isolated rerun; the final ci_fast run determines its current status.

Offscreen renders cover six palettes and 360/480-pixel inspectors, including
focus. Native Windows observation used a disposable component harness containing
the actual Event editor and Timeline widgets. It opened no user world and used
the current application stylesheet. Component observation is not a full
application startup, packaged build or persistence acceptance run.

Agent-observed native actions: select the festival marker and read its occurrence
date and short description; scroll through Repeats; focus and replace interval 1
with 2 using keyboard input; observe enabled Save Changes and the unsaved-timing
status; use Discard and observe interval 1 and saved status restored. Native
rendering exposed and corrected strip overlap with the first ordinary Event row.
Cluster-menu keyboard selection was additionally exercised with pytest-qt.

## Documentation review

### Circle refinement — 2 November 2026

The owner requested the same pinpoint/label presentation as ordinary Events,
using circles instead of diamonds. Recurring marks now reuse the shared vector
Event painter, colors and typography without a permanent button box or calendar
icon. Viewport fitting moves the label rather than the date pin, including at
the left/right edges; offscreen starts do not acquire false edge pins. Overlap
clustering measures label extents, and native button semantics retain Tab,
Space/Enter, tooltip, selection and menu access. Ordinary diamond painting is
unchanged by default.

Verification: **100 focused tests passed**, including 13 new circle, viewport-edge,
six-theme identity and strip-position tests plus existing temporal display,
grouping, view-helper and recurrence interaction coverage. Repository-wide mypy
passed for 603 source files; Ruff, visual/complexity policy, Help inspection,
offline Help and strict Sphinx checks passed. The complete ci_fast suite was not
rerun for this presentation refinement. Six-theme normal/narrow renders were
regenerated; the dark narrow timeline render was inspected. The earlier native
observations describe the original boxed presentation; new circle rendering
has offscreen evidence, not a fresh native or human acceptance claim.

The visual vocabulary was updated in the authoritative Linear document and its
repository counterpart. Existing Help IDs and interaction meanings are retained.
Changes remain uncommitted.

| Field | Record |
| --- | --- |
| Reader | Existing worldbuilder authoring a recurring festival or cycle |
| Primary purpose | How-to: user/event-recurrence.md; inline control reference |
| Sources | Recurrence domain/service, Event commands, editor save acknowledgement, transfer context and Timeline strip |
| Entry points | Manual toctree, Event chapter link, event.recurrence task and three control excerpts |
| Existing meanings | Original Event timing and ordinary Save/Discard meanings retained |
| Save/recovery | Explicit Save Changes; autosave isolation; stale baseline rejection and Discard/reapply |
| Source review | Individual changed source fingerprints and canonical explanations reviewed |
| Human prose approval | Pending |
| Full-app live Help review | Pending |
| Independent reader round | Pending; no participant observations or task-time improvement claimed |

Use the [documentation review form](../../../developer/documentation-review.md)
and [reader-testing protocol](../../../developer/documentation-reader-testing.md)
for subsequent human review. All implementation issues remain open while the
changes are uncommitted.
