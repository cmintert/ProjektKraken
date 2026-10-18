# KRT-78 — Event navigation and date-save feedback

Implementation and investigation: 2026-10-13. **Guided human review passed
2026-10-18; menu styling repair included with this review record.**
The owner accepted guided written review in this session. User-reported native
results and automated checks are recorded separately below.

## Implemented behavior

- The existing timeline **Go to date** slot opens **Go to selected event** and
  **Enter a date…**. There is no extra toolbar button or explanatory menu row,
  following the creator's review. Narrow allocations retain the same submenu in
  **More actions**.
- The target is the accepted global event selection and its saved cache snapshot.
  Non-event/deleted targets disable the action. Opening and activation refresh or
  revalidate the target; inspector hydration and pending selection are not sources.
- Both event routes reuse guarded time navigation and uncertainty disclosure.
  Selection, World Time, drafts and the existing saved-date semantics are retained.
- The Event temporal card is followed by view-at-event and secondary evidence/order
  actions. Persistence status stays above the pinned Save/Discard controls,
  independent of inspector scrolling. Typed validation and persistence
  acknowledgement remain different operations.
- Persistence status is revision-aware: Unsaved changes, Saving…, Saved, or Save
  failed — changes retained. Failed/stale delivery and newer typing do not replace
  content or move the caret. Hydration resets the feedback generation.

Contracts **1/2/4/5/6/7/8/9/11** apply. Menu buttons use shared secondary controls;
save captions use the shared supporting-caption role. No contract revision,
database migration, worker slot, or new choke-point feature logic was introduced.

## KA-07 January mismatch diagnosis

The reviewed source is `C:\Users\chris\Downloads\UX Part 1.mp4`, SHA-256
`afc5f2bb4c1522eadca527114e04d748bbef5faa784d36f8892b3d31a73177be`.
The hash was independently rechecked on 2026-10-13. Original source metadata and
transcript remain in [human run 1](../krt45/human-run-1.md).

Observed frames:

| Time | Visible date-entry state |
| --- | --- |
| 06:30–06:32 | Newly created Tribunal Session inherits 18 January 1228 and a time from the playhead. |
| 06:34 | The year/time suffix is selected in the text field; the leading `18 January` remains outside that selection. |
| 06:36 | The replacement year is still being typed after `18 January`. |
| 06:37–06:40 | The field reads `18 January 1187`, still pending local acceptance. |
| 06:55 | Save Changes is used with the field showing 18 January 1187. |
| 07:00 | The accepted date remains 18 January 1187. |

**Diagnosis:** the observed edit retained the existing day/month while replacing
the year/time suffix. The requested day `1` was not entered in that sequence.
This is an input/commit-clarity mismatch, not evidence that parsing converted an
entered 1 January into 18 January. This is frame-based observation, not a raw
keyboard-event trace; participant intention cannot be inferred beyond the task.

The reproduced suffix edit also yields 18 January 1187. Entering the complete
`1 January 1187` yields `433177.5` under the Gregorian day-precision convention;
`18 January 1187` yields `433194.5`. Tests compare field text, accepted date,
outgoing payload, command result, persisted event and reopened editor. They cover
Enter, editing-finished/blur, autosave and calendar selection. A structured year
edit retains day 18 until day 1 is deliberately selected; there is no silent reset.
Saved-event navigation and playhead snapping supply the same date, and a fixed
membership boundary persists that exact value. No parser change was warranted.

## Verification and presentation evidence

Focused tests cover global selection revalidation, absent calendars, deleted IDs,
direct/overflow routing, asynchronous feedback, stale saves, newer text/caret,
invalid input, January persistence and fixed relation timing. Existing navigation
tests protect draft cancellation/deferred save, custom calendars and representative
date disclosure.

Run the standalone presentation fixture with:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.venv/Scripts/python.exe docs/ux/evidence/krt78/render.py
```

Artifacts and the manifest are in ignored `tmp/krt78-presentation/`; source-video
samples are in ignored `tmp/krt78-video/`. Source videos and desktop screenshots
are not added to Git. The fixture isolates QSettings, loads Windows Segoe UI fonts
and the application stylesheet, captures all six themes at 360/760 px requested
widths and 100/125/150/200% text sizes, and records actual sizes, effective font and
device pixel ratio. It captures menu enabled/disabled, focus and overflow states.
These are **offscreen text-size probes**, not Windows OS scaling or native review.
The completed matrix contains 48 theme/width/text-size probes and 240 PNGs.
The [presentation manifest](presentation-manifest.json) records actual widths,
effective root fonts and successful focus acquisition for all 48 probes.
The capture helper bounds event processing and explicitly releases disposable
widgets; focus probes target the visible overflow access when the menu button
has moved into overflow. The manifest records whether focus was actually acquired.

## Acceptance and delivery evidence

### Guided native follow-up — 2026-10-18

The owner confirmed navigation to the disputed event's representative anchor,
the uncertainty explanation, and unchanged Event selection and World Time.
The supplied screenshot shows the uncertain-date disclosure and separately named
Viewing and World current time. The owner then confirmed exact navigation to
1 January 1219 with selection and World Time retained; the second screenshot
shows Viewing at that date and World current time at 1 January, Year 1.
The owner also confirmed both date-navigation commands remain accessible and
readable through narrow More actions overflow. These are guided user reports;
the screenshots do not independently establish selection preservation.

The disabled-state check exposed a presentation defect: Go to selected event
blocked activation for an Entity selection but did not visibly look disabled.
The owner's follow-up was interpreted as affecting both direct and overflow
menus. Shared QMenu styling lacked a disabled-item rule. The repair uses the
existing `action_secondary_disabled_text` role and restricts selection
highlighting to enabled items, covering both routes and other shared menus.
Contracts 5/6/7/8/9 apply; no selection, navigation, draft or keyboard behavior
changes. No theme literals or policy exceptions were added.

Verification: 35 focused navigation/theme tests passed; visual policy passed.
Offscreen enabled/disabled menu captures were inspected in all six themes at
`tmp/krt78-disabled-menu/`. These captures do not establish native acceptance.
The owner confirmed the restarted native disabled-appearance retest in both routes:
"Yes, works". Keyboard traversal then exposed a separate report: Tab moves across
panels/workspaces, enters the description editor and subsequently inserts tabs.
At the owner's request this complex focus-order/editor-keyboard work is tracked
separately in [KRT-94](https://linear.app/projektkraken/issue/KRT-94/define-predictable-tab-navigation-across-workspaces-and-description),
outside KRT-78 and without blocking its bounded review. No Tab behavior was changed.
After opening Go to date with the mouse, the owner confirmed arrow-key highlight
clarity and Enter activation of Enter a date. This passes bounded menu keyboard
operation without asserting that whole-workspace Tab traversal passes.
The owner then confirmed readable labels, distinct disabled appearance and clear
keyboard highlighting in a light theme at both normal and narrow widths.
Exact theme name and dimensions were not recorded.

On a disposable Event, the owner confirmed that entering the full 1 January 1187,
saving, selecting another entry and reopening retained 1 January 1187. The owner
also confirmed clear unsaved-versus-completed-save feedback. In the next prompted
check, the owner confirmed invalid-date rejection and retention of the previous
valid date after leaving and reopening. These are guided, self-reported native
passes; no independent database inspection or delayed-save timing measurement
was performed in this follow-up. Existing automated save-generation/caret checks
remain separate. Asked about native scaling/readability, the owner reported
"Scaling works". Exact Windows display/text percentages were not supplied; this
is a reported pass for the owner's reviewed configuration, not a measured native
scale matrix. Guided written review replaces the previous uncoached-discovery
gate for this bounded acceptance; video is optional, following the owner's
explicit evidence-method preference. KRT-94 owns workspace Tab traversal.
The menu fix and this review record form the same delivery batch.

### Disputed surrender follow-up — 2026-10-13

The owner reported navigation failing for the disputed surrender. Read-only
inspection of both Northwatch demos confirms that its saved layout anchor is
`0.0`, also used by The march begins. Direct menu navigation to that anchor works
from both another date and the already-coincident date, retaining uncertainty
disclosure and World Time.

A real pointer regression reproduced a selection failure at 0.5×, 1× and 2× zoom:
the playhead's 30-pixel-wide invisible drag hit area intercepted clicks on the
event's painted hollow anchor. Consequently the event was not selected for the
global navigation action. This is a reproduced failure path; it does not establish
every detail of the owner's original click sequence.

Occurrence marks now receive left presses through that overlapping hit area.
The hit test uses the painted device-space marker geometry, including uncertain
and precise starts. Qt still owns event mouse capture and event dragging. Ruler
scrubbing and playhead-line dragging away from the marker retain their behavior.
No uncertain date is converted into an exact historical date, and no saved world
data is changed. Contracts 2/5/6/8 apply; presentation roles and rendering are
unchanged. 95 focused gesture/presentation/coordinator tests passed; Ruff, mypy,
visual and complexity policies passed. No reviewed C901 hotspot was touched.

Owner report, 2026-10-13: “It works like a charm in human review.” In response
to the approximate-event → representative view → exact-date question, including
unchanged selection and World Time, the owner replied “yes, worked.” This records
successful human task feedback. An uncoached-participant classification and
specific native scale/configuration evidence have not yet been supplied; no video,
independent persistence check, or complete native scale matrix is inferred.

Completed automated checks: 121 focused tests passed; the final KRT-78-specific
set passed 14 tests, including a later pending-date caret check. 59 Event feedback and
presentation tests passed after pinning the status above Save/Discard. `ci_fast`
passed 1,933 tests with 2 skipped at the implementation checkpoint. Repository
Ruff, mypy (465 source files), visual policy and complexity policy passed. Sphinx
HTML built successfully, and the changed navigation/validation paragraphs were
checked in rendered HTML. No reviewed complexity allowance was touched.

The former uncoached/native-review closure gates above describe the 2026-10-13
checkpoint. The 2026-10-18 guided review supersedes the uncoached requirement
and records normal/narrow, light-theme, disabled, menu keyboard, date-persistence,
invalid-input and reported scaling passes with their limits. This does not claim
complete UI-GATE-01 native scale coverage or close KRT-45's wider comparison.

The delivery commit and verification are tracked in Linear. No additional
KRT-78 human task remains in this guided review; KRT-94 remains separate work.
