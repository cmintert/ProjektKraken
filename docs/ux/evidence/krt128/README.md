# KRT-128 — Timeline movement preserving authored timing

Implemented on 2026-11-01 in an uncommitted worktree. This is implementation and
verification evidence, not independent human acceptance or a packaged release.

## Behavior and safeguards

The Timeline exposes **Drag: Adjust offset** and **Move chain**. Offset mode keeps
the source and reference endpoint fixed; calendar units snap without conversion.
Chain mode shifts the manual authorities of the connected Event-reference network
and recalculates followers without changing offsets. Ordinary chronology links do
not add chain members. They still constrain acceptance.

Previews use detached snapshots and cancellable background calculations. The GUI
does not author dates or access SQL. The dedicated command passes through the
existing timing review, worker-owned registration, stale-state checks and atomic
history wrapper. Rejected review, Escape, invalid timing and changed worlds leave
saved records intact. Undo restores complete original definitions.

Precision, qualifiers, calendar identities, explicit windows and fractional-day
instants are retained. A move cannot change range shape or inclusivity. Calendar
offsets with non-exact source timing, and uncertain chronology whose correlation
cannot safely be retained, are rejected. Chain authorities must admit one common
translation at their existing precision. These conservative limits are deliberate.

## Interaction and presentation review

Contracts **2/3/5/6/7/8/9** apply: ordinary selection remains available; the toolbar
and its More actions submenu expose both modes; keyboard menu activation changes
mode; Escape cancels only an active movement; changed dates require review and
one Undo reverses the accepted operation. Previews retain Y positions, selection,
viewing time, source records and the viewport rather than repacking the timeline.

The mode button uses shared **secondary** tool-button and menu-caret styling.
Existing focus, disabled, selection and dependency-identity roles remain in use;
no new colors or baseline exceptions were introduced.

- [Native preview](native-preview.png): calculated follower position and rerouted wire.
- [Dark, normal width](dark_mode-1100.png) and [dark, narrow](dark_mode-360.png).
- [Light, narrow](light_mode-360.png) and [disabled control](disabled-wide.png).
- [More actions submenu](overflow-menu.png).
- [Rendered offline movement instructions](offline-help.png).

The native probe renders all six built-in themes at 1100 and 360 pixels. Selected
normal, narrow, focus, disabled and Help captures were visually inspected by the
agent. The probe uses a disposable widget and isolated settings, not a personal
world. [Probe metadata](native-probe.json) identifies the Windows platform and
automated preview/Escape assertions. This does not establish full-application
acceptance, measured usability, or independent human approval.

## Verification

Recorded checks include focused movement/history and pointer regressions;
existing Event timing, Timeline rendering/routing and MainWindow regressions;
architecture direction, Help inventory and Help bundle checks; Ruff; full-source
mypy; visual and complexity policies; strict Sphinx; and offline Help generation.
The broad focused matrix passed **456 tests**, with **1 existing Help skip** and
an existing Qt mouse-constructor deprecation warning. Subsequent targeted checks
passed **32 movement/pointer tests** after the final interval guard, and **22
review tests** including explicit-movement Apply, Cancel and world cancellation.
These batches overlap and are not summed. Custom-calendar negative-year/month-count
variation and unchanged-marginal correlation rejection have dedicated regressions.
Full-source mypy checked **592 files**. Ruff, the Help/visual/complexity policies,
offline Help generation and strict Sphinx passed.

## Documentation review record

| Field | Record |
| --- | --- |
| Reader/task | World author moving a followed Event without changing dependency meaning |
| Primary purpose | How-to in the Timeline chapter; contextual reference and Event timing cross-link |
| Canonical pages | Timeline and calendars; Events, Entities and Relations; Unreleased |
| Source identity | Uncommitted KRT-128 changes; exact source fingerprints in the inspection inventory |
| Verified sources | Movement service/presenter/coordinator, dedicated command, timing planner and history wrapper |
| Help destinations | Existing `timeline.viewing` and `event.timing` topics and anchors retained; new drag-mode anchor |
| Procedure | Select mode, drag marker, inspect preview, release, review, Apply changes or Cancel |
| Rendered evidence | Native Qt toolbar/theme captures and the offline movement section above |
| Human prose/live Help approval | Pending |
| Reader testing | Pending; no completion-time or usability-improvement claim |

Review uses the [documentation review form](../../../developer/documentation-review.md).
Future reader observations follow the
[reader-testing protocol](../../../developer/documentation-reader-testing.md).
