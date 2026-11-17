# B: connected-map points

## Scope and source review

KRT-174 implements milestone B of KRT-167 on `detail-maps` after A2 commit
`c42dbc4c`. Map-to-map transforms, temporal resolution, source eligibility and
conflict decisions live in services. A feature-owned adapter reads on the existing
database thread; the GUI receives serializable derived frames. Cached inputs
invalidate after commands, maps/world/calendar changes. At most one request is in
flight; map/date/world/settings generations reject obsolete replies.

Authored target placement wins, including hidden local placements. Eligible
sources must agree before target containment is applied. Unresolvable competitors
suppress the object rather than making another source appear authoritative.
Trajectories use base-before-first, step/linear interpolation and last-point hold.
Invalid saved tracks are reported without deletion or migration. No marker,
history, geometry, calibration or temporal facts are written by this feature.

## Presentation and authoring review

Visible route: Map settings > Show connected map features. Include smaller-map
detail is a deliberate secondary opt-in; source manual/inherited temporal/scale
visibility and opacity remain effective. View projection issues explains omitted
ambiguous sources. Hollow identity-colored points have source tooltips, selection
and deliberate double-click/Enter source navigation. They cannot move or delete.
Navigation uses the existing protected-edit route. Overlay items are separate
from authored markers/layers and clear independently.

Contracts 1/2/4/5/6/7/9/11 apply: bounded disclosure, explicit mode/ownership,
keyboard consistency, protected editing and preserved authored context. Native
menu, focus/disabled actions and theme-owned entity/event identity colors are
reused; no local color or policy exception is introduced. Source-layer zoom bounds
use the transformed display scale, respecting fit-ratio bounds when authored.
No contract revisions or new persisted authoring workflow are introduced.

## Documentation review

Reader: existing map authors. Primary purpose: how-to in the existing map manual;
architecture is an explanation. Canonical task map.hierarchy and existing anchors
remain; new connected-display and issue excerpts describe opt-in, precedence,
ambiguity, temporal/scale rules and source editing. Source review covers the
projector, coordinates, reader, coordinator, menu and overlay. Menu inspection
bindings and fingerprints are reviewed individually. Human prose/live Help
approval and reader-round owner/cohort/date remain Pending under the
[review form](../../../developer/documentation-review.md) and
[reader protocol](../../../developer/documentation-reader-testing.md).

## Verification boundaries

Focused tests exercise map-pair round trips; isolated roots; target precedence;
equal/conflicting/outside competitors; conservative detail; inherited half-open
dates, opacity and zoom; dated/step trajectories; invalid/ambiguous tracks; 2,000
points; no persistence writes; actual queued owner-thread delivery; stale replies;
opt-in and source navigation. Related hierarchy, dependency and choke-point
regressions pass. Static/Help/presentation checks are recorded in the Linear issue.
The final B group has 34 passing tests, including 12 native-action/overlay
presentation cases across all six themes at 10pt and 20pt. Related hierarchy and
choke-point checks passed; the corrected database import boundary passed 56
dependency tests. Repository Ruff/mypy (708 source files), complexity/visual
policy, Help inspection/build, strict Sphinx and test inventory checks pass.

The earlier search refactor left 13 obsolete test identities in the inventory.
Only those removals and the verified successor files plus new projection tests
are reconciled. No visual/complexity baseline is regenerated. Existing unrelated
added tests remain additions rather than a bulk inventory refresh.

Automated/offscreen results are separate from native DPI/GPU and human acceptance,
which remain Pending. C geometry projection is implemented and committed next.
