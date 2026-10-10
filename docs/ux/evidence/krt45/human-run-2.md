# KRT-45 human video review 2 — KA-11–20

Reviewed 2026-10-10. This is a continuation in the existing
`UX Video 2026-10-04 Run 1` world, not a new empty-world run or a matched
baseline comparison. It supplies task observations, not missing interaction
counts or complete KRT-45 acceptance.

## Sources and method

- `C:\Users\chris\Downloads\Video Project 11.mp4`: 19:13.70,
  SHA-256 `133d988fc709ab4536304f3f3a2cc16810b9e1f19fbe6d6e264fdec48b3ec1a2`.
- Matching `Video Project 11.srt`: cues 00:02.560–15:04.209,
  SHA-256 `5627b3e5742811e5bedd5577ce534b202de0556ee5352f6ce623c54002b4e9c2`.
  The remaining footage was reviewed visually. Automatic captions contain errors.
- Read-only cross-check: closed
  `worlds/UX Video 2026-10-04 Run 1/UX Video 2026-10-04 Run 1.kraken`,
  SHA-256 `933348D57E05CACDCCC72B00E035E25968CF737BB186EA74D3EBF50A7D504E00`,
  and `logs/kraken.36640.log`.

The log opens this world at 14:05:21 UTC and closes its connection at
14:29:48 UTC (16:05–16:29 Berlin). The video export has no independently
calibrated wall-clock offset, but the session and task sequence are consistent.
No full-frame screenshots were retained because the recording includes VS Code.
Source video timecodes below refer to the supplied file. An unobserved check is
not a failure or a zero count.

## Task observations

| Task | Video time | Observed result and limit |
| --- | --- | --- |
| KA-11 | 00:24–01:31; 15:10–15:30 | Charter duration entered as 3 D and later displayed with `c. 1218`; the closed database retains both. |
| KA-12 | 01:47–03:14 | Participant reached a representative position for the uncertain charter and then exactly 1 January 1219. Selection remained and World Time stayed Year 1. They searched for a direct selected-event view action and used zoom/drag/snap; `Show world at this event` was visible lower in the editor later but not discovered during this task. |
| KA-13 | 03:39–04:10 | Opened an existing map with Tasgillia already placed. Creation from the supplied image and placement of the existing character were not demonstrated. |
| KA-14 | 04:28–05:46 | Created Upper Rhine and drew a linked closed polygon. Dated corner revision, other-date comparison and reopened-map persistence were not shown. |
| KA-15 | 05:59–09:28 | Created and applied Tasgilla's two-point journey. Playhead changes showed position changes, and the participant confirmed completion. A later discarded edit was separate. Terminology and Travel/Relocation meaning caused confusion; undo/redo of the completed journey was not independently captured. |
| KA-16 | 09:31–11:38 | A separate unfinished journey edit triggered the map-switch guard. The participant recognized it, then chose Discard. Retention/continuation of that new draft was not demonstrated; KA-15's completed journey remained distinct. |
| KA-17 | 12:07–12:21 | Participant declared the graph check untestable before relation recovery. At-playhead/Show possible semantics and date retention on node selection were not verified. |
| KA-18 | 12:37–14:44 | Reordered Longform content, but the requested charter-as-section hierarchy and leave/return/undo checks were not established. |
| KA-19 | 13:57–17:50 | The original `member_of` and `involved` relations are visible and remain in the closed database. Membership note, fixed start and an unknown end persist; involvement retains an event-bound end. The fixed membership start is **18 January 1187**, unlike KA-07's requested **1 January 1187**. Requested graph timing filters and inspection without mutation were not fully demonstrated. |
| KA-20 | 17:50–19:13 | Pasted the task prompt into the charter description and created a UUID-targeted Tasgilla link; Source and Rich representations were visible. The charter text and link persist in the closed database, and the app log records two successful saves. An authored sentence, link follow/return, prose revision, leave/reopen interaction and unfinished-edit decision were not demonstrated. |

## Persistence details

The `member_of` and `involved` rows were created on 2026-10-05 at
19:02:14 and 19:07:22 UTC and survived the 2026-10-10 session. The
membership row retains `notes: She is a member of House Bjonaer`, fixed
start `433194.5` (18 January 1187), and unknown end. The involvement row
retains `temporal.end.binding: source_event` for Winter Council, whose
restored date is 1 January 1201. These values establish persistence;
the wrong fixed start is a separate KA-07 semantic mismatch. The participant's
statement about previous relation damage does not itself establish a new loss bug.

At 14:24:42 and 14:24:50 UTC (16:24:42 and 16:24:50 Berlin),
`logs/kraken.36640.log` records `UpdateEventCommand` terminal and received
outcomes as `succeeded` for Benchmark Charter 1218. Its database
`modified_at` is 14:24:50.803850 UTC. The row retains the approximate
1218 occurrence, 3-day duration, pasted text and UUID link to Tasgilla.
The save and disk persistence in KA-20 are confirmed.

## Disposition

KRT-45 findings at the time of this review: the selected-event date action was
not found in KA-12;
the first review's Linked events orientation, date action/commit feedback,
writing-tool state and centered writing-column concerns still need resolution
or a documented verification. KA-19/20 persistence is positive evidence.
The writing-column layout was subsequently implemented in KRT-80 (`d062dc22`);
that rendered verification does not establish the matched human comparison.

Cross-surface findings belong with existing work: KRT-25 (map journey vocabulary
and mode clarity), KRT-26 (unfinished map-edit guard), KRT-47/56 (Longform),
KRT-48 (visible region actions), KRT-22 (relation authoring), and KRT-53
(visible writing link action). Their existing issue status is not overturned
by unverified subtasks in this continuation.

The [comparison register](benchmark-comparison.md) retains unavailable counts
as `NM`. KRT-45 still requires a matched, new-empty-world v1.2 baseline and
implementation comparison, including normal/narrow layouts and advanced-value
checks. The [Linear review](https://linear.app/projektkraken/document/krt-45-human-ka-11-20-video-review-and-evidence-limits-759062cbc829)
records the same task-level evidence and limits.
