# Test documentation through reader tasks

This protocol tests whether readers can use the manual and contextual Help.
It complements the [authoring standard](documentation.md); it does not replace
the [20-task authoring benchmark](../ux/authoring-benchmark.md) or the
[Northwatch first-session observations](../ux/northwatch-demo.md).

## Prepare a round

Recruit worldbuilders with little Kraken experience for introductory material,
and experienced Kraken users for specialist tasks. Start with 3–5 readers per
relevant audience for qualitative discovery. Do not infer statistical completion
rates or enforce numerical release thresholds before establishing a baseline.

Record the round owner, agreed milestone/date, audience, app version/revision,
documentation revision, theme, viewport, active calendar and starting time.
Generate a fresh Northwatch world for each participant using the maintainer
instructions in [Northwatch](../ux/northwatch-demo.md). Record the generator
revision and fixture identity. Never reset a participant's personal world.

Use a separate fresh copy for an unassisted attempt and a Help-assisted attempt;
record prior exposure and task order. Do not pool practice effects with first
attempts. Run introductory tutorial reading separately from intention-only
tasks. The existing authoring benchmark still starts with an empty world.

## Task cards

Read only the intention to the participant. Give one task at a time. Observer
checks and recovery instructions are not participant coaching.

| ID | Participant intention | Starting state and observer checks |
| --- | --- | --- |
| DOC-01 | Record a charter that happened sometime in year 2; its month and day are unknown. | Fresh demo. Verify year precision, no invented month/day, and no duration after save/reopen. |
| DOC-02 | Record two competing accounts of a succession date and connect a ruler's role to the event you follow. Keep the competing account. | Fresh demo; create a separate test succession rather than altering the fixture's shared transition. Verify both source claims, chosen date, relation direction, and event-bound start. Reschedule the test event and verify the boundary follows. |
| DOC-03 | Record a later expansion of Ashford's border while preserving its earlier shape. | Fresh demo at a date after the existing succession. Verify a new dated geometry state, earlier/Base Geometry retained and existence dates unchanged. |
| DOC-04 | Record a person's participation in an existing event. | Fresh demo. Verify one deliberate relation between the intended IDs and correct source/target/meaning, independently of prose mentions. |
| DOC-05 | Ask for Help during an unfinished edit, then return to the same unfinished work. | Fresh demo; separately exercise writing, relation/date and map drafts. Verify no unintended save/cancel, selection/caret loss or playhead movement. |
| DOC-06 | Find out what a control under the pointer does without running it. | Pointer over a supported date/meaning control; keyboard focus deliberately elsewhere. Verify Shift+F1 explains the pointer target, does not activate it, and reaches the correct task link. Repeat Ctrl+Shift+F1 for focus. |

For Help-assisted attempts, allow the manual and its search, but ask readers to
invoke F1 from the actual working context. Record the entry point and topic
found. Do not send them directly to the expected page. Pause timing for fixture
failures; record facilitator recovery and label subsequent work assisted.

## Observation form — one record per attempt

| Field | Observation |
| --- | --- |
| Round/participant alias, cohort, prior exposure | |
| Task ID, attempt order, assisted/unassisted condition | |
| Starting fixture, revision, world identity and time | |
| Start/end, elapsed time and interruptions | |
| Entry points, queries and topics found | |
| Incorrect actions, misunderstandings and reader explanation | |
| Coaching/recovery, who intervened and when | |
| Initial completion/failure and participant report | |
| Independent final saved-result check and method | |
| Consequences understood; draft/data preservation | |
| Documentation defect versus UI discoverability defect | |
| Correction/issue, retest and unresolved limitations | |

Verify the saved result after the reader declares completion, preferably by
reopening the record and comparing its identity/state, or by inspecting the
closed disposable world's data. Do not silently correct a result before
recording the first outcome. Keep observer checks separate from self-report.

## Schedule and acceptance

Use explicit states: **Proposed**, **Scheduled**, **Observed**, **Needs correction**,
and **Retested**. A schedule needs an agreed owner and date or review milestone;
empty fields are pending, not scheduled evidence. Record consent and any recording
location without putting participant identities into public reports unnecessarily.

Broken contextual destinations, false destructive instructions, Help-triggered
mutation and documentation-induced data loss block release. Diagnose other
failures individually and create specific documentation or UI follow-ups.
Four of five newcomers completing an essential task without coaching is a
provisional aspiration only, not an established acceptance statistic.
