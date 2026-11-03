# KRT-137: compact ordinary timeline events

Recorded 2026-11-03. This is rendering and automated regression evidence;
fresh human interpretation and live application review remain pending.

## Presentation reviewed

The user requested one retained unlabeled span bar, with separate Starts, Ends
and Duration rows removed and written dates left to the existing hover details.
Point Events retain their mark and name. The visual vocabulary revision is
recorded in Linear and its repository counterpart.

The comparison uses detached records and the active calendar read through a
SQLite read-only connection to Into the Wild. Its database was not edited.
Settlements on Kahlfels has independent year-precision endpoints 0 and 15;
Gotland Exploration has independent year-precision endpoints 15 and 30.
Landfall supplies the legacy point-event comparison.

- [Before](before.png)
- [After](after.png)

Both captures use the production TimelineView and EventItem, Segoe UI 10 pt,
1336 × 480 pixels, fantasy theme, and 0.036 pixels per day. Comparison rows
are held 125 pixels apart; this spacing is not a lane-packing demonstration.
The span item bounds shrink from 125 to 50 pixels high and Landfall from
41 to 32 pixels initially. The follow-up removes the Possible span wording and
its gutter, reducing the span bounds further to 48 pixels high. All three
tooltip strings compare exactly equal before/after.
The retained bars preserve the possible-presence hatching and guaranteed core.

## Verification

- 589 timeline-related tests passed, including movement and grouping integration
  tests. Coverage includes compact geometry, hit regions, authored endpoint
  anchors, tooltip preservation, drag, snap, selection, grouping, time context,
  dependency modes, disabled routing, keyboard focus and narrow toolbar overflow.
- Repository-wide mypy passed for 603 source files. Ruff and visual/complexity
  policy checks passed.
- Offscreen comparison renders were generated for all six themes at normal and
  480-pixel widths and at compact zoom. Inspected dark/fantasy normal and light
  narrow captures. Horizontal panning can clip a span or its label at viewport
  edges, as before; the temporal coordinates are not shifted to fit labels.

Event identity uses `event_main`; names use `text_main`, unbounded-span fallback
text uses `supporting_caption`, and selection/focus retain their shared roles. No new
control variants or visual-policy exceptions were introduced. Contracts
1/2/4/5/6/7/8/9 apply; stored dates, uncertainty, durations and references stay
unchanged. Existing selection, drafts, keyboard ownership, playhead/World time
separation and history paths are preserved. No usability improvement or human
acceptance is claimed from these offscreen checks.

Local supplementary captures, detached source snapshot and render metadata are
in the ignored `artifacts/krt137/` directory; the two linked images are retained
here as durable comparison evidence.
