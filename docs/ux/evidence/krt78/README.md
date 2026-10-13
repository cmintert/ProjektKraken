# KRT-78 — Event navigation and date-save feedback

Implementation and investigation: 2026-10-13. **Acceptance is incomplete.**
Automated evidence does not establish uncoached discoverability or native Windows
scale acceptance. Keep KRT-78 In Progress until those gates are recorded.

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

## Remaining closure gates

Owner report, 2026-10-13: “It works like a charm in human review.” In response
to the approximate-event → representative view → exact-date question, including
unchanged selection and World Time, the owner replied “yes, worked.” This records
successful human task feedback. An uncoached-participant classification and
specific native scale/configuration evidence have not yet been supplied; no video,
independent persistence check, or complete native scale matrix is inferred.

Completed automated checks: 121 focused tests passed; 59 Event feedback and
presentation tests passed after pinning the status above Save/Discard. `ci_fast`
passed 1,933 tests with 2 skipped at the implementation checkpoint. Repository
Ruff, mypy (465 source files), visual policy and complexity policy passed. Sphinx
HTML built successfully, and the changed navigation/validation paragraphs were
checked in rendered HTML. No reviewed complexity allowance was touched.

- Record a fresh uncoached creator discovering selected-event navigation for an
  approximate-year event, identifying the view as representative, then entering
  an exact date without changing selection or World Time.
- Record native Windows normal/narrow/theme/focus/disabled review, supported
  application sizes and UI-GATE-01 OS/text scaling evidence. Do not infer this
  from offscreen captures or the historical video.
- Link the implementation commit and completed verification in Linear. Close
  KRT-78 only after the remaining acceptance evidence is complete.
