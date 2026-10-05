# KRT-45 human review — KA-01–10, run 1

Reviewed 2026-10-05. **KRT-45 remains In Progress.** This partial run exposes
specific problems to repair and retest; it does not satisfy the full human
acceptance gate or establish a before/after improvement.

[Concise Linear review](https://linear.app/projektkraken/document/krt-45-human-ka-01-10-review-and-optimization-priorities-576c64824165)
records the priorities and issue ownership. Source paths, hashes and detailed
widget diagnostics are retained in this repository evidence.

The highest-priority findings are unintended dropdown changes during scrolling,
missing temporal orientation in Linked events, and a relation form that separates
a start date from its Starts choice. Relation capture still requires the full
expert form. Successful writing, navigation, year precision and approximate-date
entry should be preserved while these problems are addressed.

## Source pair and review method

| Item | Evidence |
| --- | --- |
| Run | `krt45-human-run-1`; one familiar participant, think-aloud review |
| Recording | `C:\Users\chris\Downloads\UX Part 1.mp4`; 104,915,679 bytes |
| Video SHA-256 | `afc5f2bb4c1522eadca527114e04d748bbef5faa784d36f8892b3d31a73177be` |
| Media | H.264 / AAC, 1280 × 720, 30 fps, 16:31.67 |
| Matching subtitles | `C:\Users\chris\Downloads\Video Project 9.srt`; 9,865 bytes |
| SRT SHA-256 | `d3446f9441943bd883ebedf5160e9539a2975c855db624539a35b88fcbd6f064` |
| Subtitle coverage | 00:04.540–16:29.813; German automatic transcription with mistranscriptions and blank segments |
| Catalog | v1.2 intentions visible beside the application; KA-01–10 attempted, KA-11–20 not executed |
| Application | v0.19.7 Beta; final four-destination inspector and supporting refinement visible |
| Revision | Title appears to show `b2fa333b`; full runtime hash not independently recorded. Review checkout: `b2fa333b88cb11d99a2cac558730d60e635e9327` |
| Environment | Dark theme, Windows desktop, Gregorian date labels; recording does not independently establish Qt version or native viewport/inspector dimensions |
| Start | Empty Explorer and history visible at 00:20. World creation/restart precedes this capture; do not claim the full setup protocol was recorded |
| Initial time | World Year 1; playhead already around 18 January 1228. An empty world's inherited playhead is not the same as seeded lore |
| Assistance | Task prompts and participant completion messages visible. No route coaching established by reviewed evidence; unavailable assistance information remains not measured |

The video and SRT are one source pair. Subtitle timecodes were checked against
the corresponding visible actions. A 20-second frame survey covered the recording;
closer samples covered linking, boundary changes, start-date placement, event
rescheduling, history search and approximate-date entry. This is frame-based
visual review plus transcript analysis, not a frame-by-frame input-event trace or
an independent audio transcription. The exported desktop image is smaller than
the video frame; enlarging it cannot recover missing detail.

The [capture manifest](human-run-1/captures.json) records both source hashes and
the historical metadata for 26 full-frame PNGs. Those screenshots were removed
from the current worktree at the user's request because they included VS Code
and the video borders. They remain in commit `69c05724`; no replacement images
are currently supplied. Visual references below identify source-video timestamps.
The [matching transcript](human-run-1/transcript.srt) is retained byte-for-byte,
including the nonstandard `00:06:49,1000` timestamp and empty entries. The source
video stays at its supplied path; it has not been copied into Git. Disposable
survey frames/scripts are separate under ignored `tmp/krt45-human-review/`.

**Evidence labels:** observed means visible in reviewed frames; reported means
spoken in the SRT or stated by the participant; reproduced means independently
checked against current source/widgets; inferred means a plausible explanation;
unverified means the recording/review does not establish the criterion.

## Per-task observations

Windows below are review segments, including prompt reading, setup and commentary.
They are **not measured task-completion times**. UUID identity, database contents,
undo and persistence after application restart were not inspected. Do not turn
participant completion messages into verified semantic completion.

| Task | Review window | Observed route and outcome | Remaining criterion / friction |
| --- | --- | --- | --- |
| KA-01 — create character | 00:04–00:45 | Create Entity → name dialog → ordinary inspector; type corrected to Character. Empty start and Character label visible. | Participant questions whether Entity communicates Character (00:10–00:25). Type choice remains a correction after creation; UUID unverified. |
| KA-02 — leave and find character | 00:59–01:25 | Creates Freiburg as a Location to navigate away, then selects Tasgillia again in Explorer. Participant says return is easy. | Additional object was unnecessary under v1.2; record it as participant setup, not a required route. Same UUID unverified; no visible duplicate character. |
| KA-03 — write, leave, return | 01:41–01:57 | Writes the history-of-the-Rhine description, leaves and returns; text remains visible at 01:54. | Positive observed reopen result. Full database/restart persistence and caret retention unverified; no demonstrated text loss. |
| KA-04 — linked mention and return | 02:08–03:34 | Creates House Bjornaer; deliberately chooses Faction; writes its name in the description and uses wiki completion to produce a blue link. | Participant proposes selected text → Create link (03:15–03:31). Following the link to the group and returning to the writing origin are not demonstrated by reviewed samples. Link UUID and rename behavior unverified. |
| KA-05 — generic connection | 03:52–05:09 | Connections → Add Relation → full dialog; target House Bjornaer; type `connected`; authored relation row visible afterwards. | Advanced metadata/timing occupies the ordinary capture form. Starts/Ends choices change during scrolling (04:20–04:42). Connections/Add Relation vocabulary mismatch reported at 04:56–05:06. Exact retained timing attributes unverified. |
| KA-06 — membership and note | 05:23–06:07 | Edit existing connection; type becomes `member_of`; explanatory note visible in dialog; same row is refined rather than visibly duplicated. | Notes field looks insufficiently like an editable field (06:02–06:07). Saved/reopened note and identity unverified. No sampled confidence change: it remains 1.00. |
| KA-07 — fixed membership start | 06:20–09:07 | Creates Tribunal Session; edits date; initially reports completion, rereads full prompt at 07:13, moves/snaps playhead to the session, returns to membership Edit and uses fixed/manual timing. | Requested 1 January 1187, but date and playhead visibly show **18 January 1187**. Do not accept exact-date setup. Date commit expected during typing but reported only on leaving field. At 08:41 the start's Valid From date sits below the Ends choice; participant questions this (08:43–09:02). Fixed start survives session reschedule remains unverified. |
| KA-08 — event-linked participation | 09:07–14:42 | Creates Winter Council on 1 January 1201; Connections → Participants → Add participant/full dialog; default `involved` relation. Revisits timing to choose End at Event. Council is rescheduled to 1202, temporal context inspected, then restored to 1201. | Participant questions whether `involved` is required to be a participant or can be replaced (10:03–10:19). At 11:50–14:13 searches for temporal orientation, opening History & context and writing panels. A single Linked event has no visible playhead marker. Date change/restore and context refresh are supported; inspecting the bound relation after rescheduling is not demonstrated, so dynamic-end semantics remain partial. |
| KA-09 — year-only event | 14:45–15:36 | Creates Benchmark Charter 1218 and sets 1218; structured controls show Month unknown / Day unknown. No duration enabled. | Positive observed year-only meaning. Stored precision and reopen unverified. |
| KA-10 — approximate year | 15:57–16:31 | Date details & uncertainty remains open from KA-09; selects Approximate; `c. 1218`, unknown month/day and an uncertain timeline occurrence visible. | No fresh discovery trial: qualification was already exposed. Leaving and reopening the event after this edit is not demonstrated. Do not call the full save/reopen criterion passed. |

This run gives useful positive evidence for ordinary description persistence,
Explorer return, deliberate Faction selection, relation refinement, year-only
precision and approximate qualification. It does not measure first-use behavior
for an unfamiliar creator. The earlier KRT-46 run used v1.1 and different capture
conditions; retain its findings separately instead of pooling task times.

## Prioritized optimization register

### F1 — Scrolling changes authored boundary choices

**Priority: first repair. Owner: [KRT-52](https://linear.app/projektkraken/issue/KRT-52/prevent-scrolling-from-changing-unselected-choice-fields).**
At 04:16–04:42, the form scrolls and Starts/Ends cycle through Unbounded,
Manual date and Date not known. The participant says settings change and expected
the issue to have been fixed. Compare 04:16,
04:25,
04:31 and
04:43.

Independent current-widget reproduction confirms a new input-family gap:
with notes focused, a +120 wheel step over the unfocused Starts `QComboBox`
changes `open` → `unknown`, acquires focus, leaves the scroll position at zero,
and changes `get_data()` to contain `temporal.start.status=unknown`. This is
draft mutation, not just a misleading display. No command was executed and no
stored corruption is claimed. The video itself does not expose raw wheel input.

KRT-49's numeric spin-box fix is present. Confidence remains 1.00 in these
samples; do not reopen that issue as a numeric regression. Apply a shared
scroll-safe policy to closed, unselected dropdowns; inventory other authoring
choices, preserving deliberate keyboard/click editing and popup scrolling.
Contract 2, 5, 8, 9.

### F2 — Linked events loses orientation before/after the list

**Priority: first repair. Owner: KRT-45.**
At 12:32–14:13 the participant searches for the entity timeline/playhead and says
the old marker is gone. History at 12:21
and 13:03 show one linked event
with no playhead separator while the main timeline still has its playhead.

Current `TimelineDisplayWidget._refresh_display()` inserts PLAYHEAD only when
there is a following event and `event_date <= playhead < next_date`. Isolated
checks show no marker for a single event before, at or after its date, or outside
a two-event list; it appears between two events. This is a conditional-rendering
gap. The inspected source does **not** support a claim that KRT-45 deleted the
timeline widget or its playhead wiring.

Show the viewed date and clear before/after position even with zero/one event or
when viewing outside the linked-event range. Preserve distinct World Time,
read-only context, event navigation and supporting split/return behavior. Keep
the purpose recognizable under History & context; validate whether Linked events
needs a stronger timeline cue. Contract 5, 6, 7, 9.

### F3 — The start date appears beneath Ends

**Priority: high. Owner: [KRT-22](https://linear.app/projektkraken/issue/KRT-22/expose-loose-relation-capture-before-full-relation-editing).**
08:41 shows Starts, Ends, then
Valid From and its date. The participant asks why the date is under Ends rather
than Starts (08:43–09:02). Source confirms layout ordering: boundary choices are
inserted at form rows 0/1, ahead of both pre-existing manual-date rows. This is
misleading grouping; it is not evidence that stored start/end values are swapped.

Group each boundary's intent, date/preview and applicable event-relative controls
together. Show only controls for the selected intent. Clearly distinguish
“Starts on the viewed date” (fixed snapshot) from “Ends when Winter Council
happens” (dynamic binding). Keep unknown/unbounded, offsets, independent endpoints
and existing advanced attributes reachable and lossless. Contract 1, 4, 6, 8.

### F4 — Ordinary connection and participation use the expert form

**Priority: high. Owner: KRT-22.**
04:04 and
11:03 show metadata,
timing and state-change machinery alongside common capture. Complaints cover
overload (04:44–04:51), Connections/Add Relation naming (04:56–05:06), weak Notes
field affordance (06:02–06:07), and whether `involved` defines participation
(10:03–10:19). The generic connection was achieved; the cost is semantic work
and scrolling, not a missing engine capability.

Use the existing KRT-22 Connected to… → Refine connection… direction. Ordinary
capture should require the target and show a plain-language preview; membership,
note and timing refinement should stay on the same relation. Present Participant
as creator intent and explain how advanced relation type relates to that role.
Keep custom types, confidence/weight, payloads, bidirectionality and full timing.
Make Notes visibly editable. Contract 1, 3, 4, 7, 9.

### F5 — Link creation needs a visible writing action

**Priority: high after safety/orientation. Owner: [KRT-53](https://linear.app/projektkraken/issue/KRT-53/expose-a-visible-way-to-link-selected-writing-to-an-existing-entry).**
At 03:15–03:31 the participant proposes selecting prose and creating a link;
03:08 shows the current completion
route. Add a visible Link to entry… action for selected text or caret insertion,
with the same optional context-menu accelerator. Preserve the label, select an
existing stable identity, and make acceptance one reversible writing edit.
Teach how to open/return without requiring undiscoverable modifiers. Keep syntax,
completion, Peek and supported Rich/Source round-trips. Never create an authored
connection or duplicate lore object as a side effect. Contract 2, 4, 5, 7, 9.

### F6 — Event timing actions and date-commit feedback need coherence

**Priority: high. Owner: KRT-45.**
At 06:43–06:57 the participant points out scattered timing buttons and expects
autosave before leaving the date input. 06:38
shows Chronology…, Date evidence… and Show world at this event separated across
rows/columns. `CompactDateWidget` commits text through `editingFinished`; the
observed delay is consistent with the current local date-commit boundary.
No date data loss is demonstrated.

Group the ordinary date entry, qualification/duration disclosures and view-at-date
action predictably, with secondary evidence/order tools nearby. Make pending
date validation versus acknowledged save visible; clarify local Enter/blur
behavior without autosaving invalid or half-typed dates. Do not conflate date
validation with autosave delivery or move the caret on acknowledgement.

The exact-date task also needs a recorded observer correction: the session is
18 January 1187, not the requested 1 January. The review cannot determine whether
this came from input, retained components or parsing. Reproduce the precise
entry path before diagnosing a parser defect; then verify the formatted result
and playhead. Contract 1, 2, 5, 6, 9.

### F7 — Quiet writing tools lack recognizable toggle state

**Priority: medium. Owner: KRT-45.**
During the history search, Summary/Draft with AI are opened and closed. At
13:25–13:34 the participant questions their toggle appearance and theme consistency.
Compare 13:21 open and
13:39 closed.

The current scoped StyleHelper rule deliberately uses transparent writing actions
and changes checked text weight/color; it does not provide a distinct checked
surface. Theme deviation is participant-reported, not proof of hardcoded colors.
Validate a consistent, quiet disclosure/state affordance in dark/light themes
and normal/hover/focus/checked states. Preserve simultaneous panels and unfinished
summary/generator inputs. Contract 6, 7, 8; no requirement to restore large bars.

### F8 — Entity/type vocabulary still needs deliberate creation

**Priority: existing high-priority backlog. Owner: [KRT-14](https://linear.app/projektkraken/issue/KRT-14/require-deliberate-entity-type-choice-in-normal-creation).**
At 00:10–00:25 the participant questions Entity terminology, then corrects
Character at 00:32–00:37. Unlike the earlier run, House Bjornaer is deliberately
set to Faction here. Preserve this positive distinction. Add lightweight type
choice in normal creation and explain Entity through familiar examples. Keep
intentional provisional Concept capture separate. Contract 4, 7.

## Independent diagnostics and implementation boundary

[Widget diagnostics](human-run-1/widget-diagnostics.json) were produced against
the current review checkout using Python 3.13.14, PySide6 6.10.1, Windows 11,
offscreen Qt and isolated INI settings. They constructed existing widgets only;
no personal world, worker, database or command was opened.

The dropdown check used the production RelationEditDialog with notes focused and
`QTest.wheelEvent(dialog.windowHandle(), start.mapTo(dialog,
start.rect().center()), QPoint(0, 120))`. The marker check used one/two synthetic
linked-event snapshots and playheads before, at, between and after their dates;
the JSON records the resulting document text. These diagnostics verify narrow
mechanisms, not human performance, persistence or production visual quality.
Offscreen SVG-loading warnings occurred; icon appearance is not assessed by them.

This work records findings, screenshot evidence and actionable follow-ups.
Production code, normative contract v1 and benchmark prompts are unchanged.
No executable build, implementation commit or push was requested or performed.

## Retest and acceptance

Repair F1/F2 first, then validate F3/F4 with the existing KRT-22 refinement work.
Review the smallest coherent KRT-45 changes for F6/F7; track F5 and F8 in their
own issues. Retest KA-04–08 and KA-10 with explicit observers for link navigation,
exact event dates, unchanged opposite boundaries, fixed-start independence,
dynamic-end rescheduling and save/reopen. Confirm scrolling never changes a fact.

For comparable measurement, begin a new empty-world recording before setup,
record exact revision/calendar/playhead/native dimensions, and run all twenty
v1.2 tasks. Count destination changes, disclosures, writing-panel openings,
dialogs, wrong turns and assistance separately. The current wide-layout recording
does not establish approximately 360 px behavior; repeat narrow layouts.
KA-11–20 and the supplementary tags/fields/Sheet/media/split/save-lifecycle checks
remain pending. Protect KA-08/10/15/19/20 and keep earlier v1.1 evidence separate.
The [comparison register](benchmark-comparison.md) retains unavailable counts as
NM and records this partial after run without manufacturing a baseline.

## F1 fix — KRT-52, 2026-10-05

The user subsequently requested the F1 fix. The review and original diagnostics
above remain historical evidence against `b2fa333b`; this section records the
implementation separately. KRT-52 owns this repair under KRT-45. KRT-45's remaining
review findings and human acceptance are still open.

`src/gui/widgets/choice_inputs.py` supplies `ScrollSafeComboBox`. `StrongFocus`
allows explicit click/Tab focus but excludes wheel-acquired focus. A closed field
without focus ignores wheel events so Qt propagates navigation to its surrounding
scroll area. A focused field retains Qt wheel selection. Open popups retain normal
view scrolling and deliberate selection. Editable combo line edits use the same
policy through their parent; typed custom values remain supported. There are no
new editor-specific wheel filters.

This applies contracts **2, 5, 8, 9**: the visible dropdown arrow opens choices;
Tab enters editing, arrows select, popup Enter selects and Escape dismisses;
unfocused navigation preserves the draft and caret owner. Focused wheel editing
matches the explicit-focus policy of KRT-49. No normative contract change or new
exception is introduced. Existing date Delete/Backspace and local Escape handlers
remain in place. Command and worker paths are unchanged.

### Choice inventory and scope

| Surface / choice family | Finding and disposition |
| --- | --- |
| Relation Starts/Ends, named-event anchors | Raw Qt reproduction changes boundaries, including Unbounded → Date not known; replaced by the shared control. Event anchors are choices in these same combos. |
| Relation Meaning, editable type, before/at/after event | Raw Qt reproduction changes each selected value; protected, including the editable line-edit hit area. Disabled relative choices remain disabled until an event anchor is selected. |
| Compact date month/day/qualification | Raw Qt reproduction changes each selected value; protected. The separate calendar popup's month selector uses the same control. |
| Lore date month/day/hour/minute | Raw Qt reproduction changes all four values; protected. Numeric year/hour/minute controls elsewhere retain KRT-49. |
| Entity/Event type; relation type picker | Source inventory finds ordinary editable QComboBox constructors without a wheel guard; adopted the shared policy for authored types. Existing editor/picker regressions pass. |
| Attributes and Sheet value type | Source inventory finds ordinary QComboBox constructors whose change signals alter value interpretation; protected. Existing 95 metadata regressions pass. |
| Event chronology order/target; map validity boundary; preferred date evidence | Source inventory finds ordinary authoring QComboBox constructors; protected consistently. Chronology and temporal authoring regressions pass. |
| Explorer/graph/analysis/search filters, map navigation, settings/provider/model choices, transfer/import and generator configuration | Inventoried by constructor search; unchanged in this repair. These distinct browse/configuration workflows have not been individually wheel-tested, and this record does not claim they are affected or safe. Other map styling/creation and fast-inject choices remain outside this measured repair. |

### Verification and evidence limits

`human-run-1/widget-diagnostics.json` retains the original review keys and adds
`choice_wheel_fix_2026_10_05`: 48 delivered observations, twelve relation/date fields
at 400/800 px, comparing raw Qt constructors restored **only in probe memory** with
the protected constructors. All twelve baseline fields emitted an index change.
All 24 protected cases retained authored data and focus, emitted zero index/text
changes and moved the surrounding scroll bar. This reconstructed mechanism check
is distinct from the original revision-specific diagnostic. It uses no database.
The local probe is retained at `artifacts/krt52-choice-probe.py`; permanent tests
below reproduce the protected behavior.

`tests/unit/test_choice_wheel.py` adds 45 `ci_fast` cases delivered through actual
QWindow hit testing and propagation. Targets use their visible viewport intersection
to avoid delivering to clipped portions of narrow forms. Cases cover angle/pixel
deltas, exact reported +120 empty-boundary behavior, editable child inputs,
event-relative choices, date qualification, focused wheel/Tab/keyboard editing,
click-opened popup scrolling and selection, and geometry expanded by Starts now.
The save/undo/redo case preserves a dynamic source-event start, a fixed playhead
end, custom type, notes, custom metadata and state-change payload through the
existing UpdateRelationCommand. Other existing timing/reopen tests remain passing.

On Windows, Python 3.13.14, PySide6/Qt 6.10.1, `QT_QPA_PLATFORM=offscreen`:

- Focused choice/numeric/relation/date/chronology/temporal/picker/editor tests:
  **194 passed**.
- Attribute/Sheet tests: **95 passed**.
- Bounded `ci_fast`: **1,424 passed, 2 skipped**; 45 new cases included.
- Ruff `src/ tests/`, changed-module mypy (12 modules), test policy and diff
  whitespace checks pass. Collection baseline includes the 45 new cases.

Offscreen popup capabilities and SVG warnings limit native visual conclusions;
these results establish the tested delivery and data behavior, not a new human
benchmark or native Windows appearance. No executable build was performed.
Commit/completion status is tracked in KRT-52. Broader KRT-45 human acceptance
remains pending.
