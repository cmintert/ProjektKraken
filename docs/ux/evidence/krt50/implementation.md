# Timeline temporal presentation implementation

Implemented 2026-10-07 for KRT-50, KRT-57 and KRT-58 against baseline
`e8a00a8bdc30efa42985883940901d395750712a`. Prepared for the user-approved commit
and push after implementation and startup verification.
The [original investigation](README.md) and [indicator review](indicators-review.md)
remain the before-state evidence.

## Result

Uncertain-start durations now show three separate, always-visible channels:
Starts, a detached Duration length ruler, and Possible span. Approximate and
one-sided assertions retain their occurrence grammar. Valid unbounded spans no
longer become error boxes. Independently asserted endpoints show Starts/Ends/
Possible span without inventing a fixed duration. Existing possible/certain
presence bounds remain unchanged.

The [year comparison](after/krt50/year-visible.png) and
[tighter comparison](after/krt50/year-tight.png) show three-day measures separately
from the year-wide occurrence/presence envelopes and a genuine 240-day event.
The [endpoint comparison](after/indicators/endpoints-errors.png) preserves certain
presence cores and distinguishes valid open assertions from actual errors.

Collapsed groups use the same occurrence marks with device-space strokes:
[production expanded group](after/indicators/grouped-production-expanded.png),
[production collapsed group](after/indicators/grouped-production-collapsed.png).
Their tooltips retain names and authored timing. Production grouping screenshots
also exposed and led to fixes for stale zoom on duplicate items and insufficient
header/title spacing. Originals and duplicates now share the current geometry.

Viewed time and world current time are pinned in a wrapping status strip. Their
solid/handled versus dashed/unhandled marks have separate identity rows below
calendar ticks; coincident marks identify both roles. Examples:
[separate times](after/indicators/state-during.png),
[coincident times](after/indicators/navigation-coincident.png),
[narrow dock](after/indicators/navigation-narrow.png).

[Uncertain snapped navigation](after/indicators/navigation-snapped-uncertain.png)
discloses the representative position after acceptance. Accepted context survives
pan, zoom, selection and presentation refresh. Deleted/rescheduled targets or
independent time navigation clear stale disclosure. Deferred save, cancellation
and failure retain the previous accepted context until the guard accepts a target.
The modal event loop is covered using the real timeline widget and TimeCoordinator.

Future events show Not yet while names and dates remain fully opaque. Captions
use supporting_caption. Toolbar actions share normal/checked/disabled/focus
presentation. [Focus](after/indicators/theme-dark_mode.png),
[unfocused](after/indicators/toolbar-unfocused.png), and
[disabled](after/indicators/toolbar-disabled.png) captures make the state reviewable.

## Interfaces and boundaries

- Immutable TemporalPresentation separates start/end occurrence, authored duration
  and the existing TemporalDisplay presence projection. No stored fields change.
- Shared TimelineItemLayout provides painted rows, measured text, hit regions and
  packing extents. Selection/future state does not resize the item.
- Collapsed bands accept immutable occurrence projections; their date-only setter
  remains compatible with explicitly precise legacy dates. Cached event callbacks
  supply refreshed captions and projections without GUI SQL.
- TimelineTimeIndicators owns pinned status, device-space lines, target snapshots
  and the narrow acceptance predicate. Existing float time APIs/signals remain
  compatible; a separate navigation_context_changed dict signal exposes accepted
  context. Event-directed navigation queues context separately from its time request.
- No worker slot, storage migration, MainWindow/ConnectionManager responsibility,
  database access, executable build, commit or push was added.

The reviewed TimelineView.set_events method is untouched: complexity remains 19
under allowance c901-020f2d0c9c6b. New rendering/controller helpers satisfy normal
Ruff limits. Dependency-direction checks cover the new core/GUI boundaries.

## Roles, policy and context

The [visual vocabulary](../../visual-interaction-vocabulary.md) and its matching
Linear document contain the same timeline addendum. Contracts 1/2/4/5/6/7/8/9
apply; no authoring-contract rule is changed.

event_main retains event identity. supporting_text/supporting_caption provide
readable boundaries and captions; selection and focus use their shared roles.
timeline_viewed_time, timeline_world_time and timeline_grid are theme-owned.
Halo/window opacity is also theme-owned. Shared secondary actions and quiet
overflow preserve keyboard ownership and disabled routes.

Exactly 20 eliminated legacy expressions were removed from the visual-policy
baseline. They belonged to the replaced occurrence/duration painters, group-band
paint, time-line constructors, ruler/handle/axis paint and obsolete timeline
literal constants. No new exception was added or baseline regenerated.

[Contrast diagnostics](after/indicators/text-contrast.json) show normal and future
date captions at the same opacity. All six palettes exceed 4.5:1; the lowest
caption ratio is approximately 4.54:1 in light mode. Time roles and shared meaningful
boundaries/focus meet the policy's 3:1 requirement. These are token/compositing
calculations, supported by rendered review, not anti-aliased pixel measurements.

## Evidence and verification

After-state evidence contains six KRT-50 comparison captures and 27 other-indicator
captures, including all six palettes, precision/compact states, selected/unselected,
focus, disabled, simulated handle hover/drag, real snapped navigation and actual
production grouping layout. Original source images remain in their original
locations. Renderers now default to after-state destinations and accept --output.

Reproduce from the repository root:

```powershell
.venv\Scripts\python.exe docs/ux/evidence/krt50/render.py
.venv\Scripts\python.exe docs/ux/evidence/krt50/indicators.py
```

The JSON diagnostics distinguish actual layout rows from legacy presence geometry.
Settings are isolated in temporary directories; no world database is opened.
The screenshot harness reserves enough space for every full item and caption.

Added 27 regression cases: 24 for temporal channels, shared extents, contrast,
snapping/context, device-space dashes and grouped zoom/refresh; three real-widget
authoring-guard cases for cancel, deferred-save acceptance and failure. Existing
tests were updated for deliberately changed opacity, caption roles and ruler tiers.
Focused relevant suites passed, including 90 temporal/coordinator/calendar cases
after the final changes. Final bounded CI results are recorded below.

- Bounded `ci_fast`: **1,668 passed, 2 skipped**, 4,368 deselected. One existing
  Starlette/httpx deprecation warning was emitted.
- Repository Ruff and evidence-script Ruff: passed.
- Full-source mypy: no issues in 448 modules.
- Visual policy and complexity policy: passed; no new exceptions/allowances.
- Git diff whitespace check: passed. Existing reviewed hotspots remain untouched.

World switching currently requires an application restart. Navigation context is
session-only and is never persisted, so the new timeline instance starts without
the previous world's disclosure.

### Saved-playhead startup follow-up

The 2026-10-07 user startup log exposed an initialization-order regression: a
nonzero saved playhead called set_playhead_time before time_indicators existed.
Restoration now runs after the complete TimelineView initialization. Four new
regressions construct the real TimelineWidget with zero, positive, negative and
fractional saved coordinates, process queued updates, and verify the exact saved
value, unchanged world time, empty navigation context and no settings writes.
This preserves the user's saved playhead; no settings reset is needed.
Focused startup/navigation/application-construction checks: 79 passed. Ruff,
full-source mypy, visual policy and complexity policy also pass after the repair.

## Remaining human acceptance

**Fresh unprompted interpretation is pending.** The
[neutral-name review image](after/indicators/human-interpretation.png) is prepared.
Ask a participant who has not been told the intended meanings to describe when
Councils A/B/C occurred, how long they lasted, what each mark communicates, and
which date is viewed versus the world's current time. Record their first wording,
the image reviewed, participant familiarity and any assistance. Ask which marks
informed the answer; caption-only answers do not establish visual acceptance.

Offscreen captures establish rendered behavior, not native desktop task performance
or persistence. Mouse navigation remains covered by existing interaction tests;
the hover/drag images demonstrate presentation flags. KRT-50 retains its separate
fresh-interpretation gate; implementation review does not supply an unprompted
participant interpretation.

## Author review

On 2026-10-07 the user reviewed the result and confirmed:
“I reviewed it and it looks good. commit and push”. This records author acceptance
of the implementation and publication authorization. It does not claim a fresh
participant interpretation. KRT-57/KRT-58 may close after the verified commit;
KRT-50 stays open for its remaining interpretation criterion.
