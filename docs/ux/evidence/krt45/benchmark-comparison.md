# KRT-45 acceptance register

## Current method — guided native review, 2026-10-18

The owner authorized completing KRT-81/KRT-45 through guided written native
checks, one task at a time. Video, matched baseline reruns, numerical improvement
measures and uncoached first-use classification are no longer closure requirements.
Historical records below retain their original limits and NM values; the matched
comparison was not executed. No measured before/after improvement is claimed.

KRT-77–80 are Done. Their recorded acceptance is reused where applicable.
KRT-81's guided human checks below are complete, covering destination
predictability, tags/typed fields/Sheet, Media, World context, independent
supporting views, save lifecycle and advanced authoring semantics.
Workspace Tab traversal is separate KRT-94 work. This record completes the
revised acceptance; the delivery commit and issue closure are tracked in Linear.

### Guided outcomes

Each row is a prompted native task confirmed by the owner with "yes" on
2026-10-18. These are user reports, not independently observed persistence checks.

| Prompted check | Reported outcome |
| --- | --- |
| Find/add an Entity tag, save and reopen | Easy to find; addition persists |
| Remove that tag, save and reopen | Removal persists |
| Edit text, number and Boolean fields in Details, save and reopen | Values and types remain correct |
| Switch Fields/Sheet, edit in Sheet and reopen | Values agree; Sheet edit persists |
| Rearrange a Sheet row, save and reopen | Layout retained |
| Add Media attachment and caption, save and reopen | Both retained |
| Edit caption, save and reopen | Caption change persists |
| Remove disposable attachment and reopen | Removal persists |
| Open World context and use its links | Links easy to use; clearly read-only |
| Split World context, continue writing and return pane | Writing remains available; draft preserved |
| Split Sheet and return pane | Draft and Sheet values preserved |
| Switch entries with unsaved draft | Warning appears; Cancel/Keep editing preserves draft |
| Switch entries and choose Save, then return | Draft saved correctly |
| Make disposable edit, switch and Discard, then return | Last saved version restored |
| Change the Event date for an event-linked relationship end | Relationship end follows the Event date |
| Save/reopen approximate-date Event with duration | Uncertainty and duration retained |
| Apply, Undo and Redo a disposable journey | Map position reverses and restores correctly |
| Inspect relationship advanced timing/values and reopen without edits | Values unchanged |
| Follow description link and return | Writing and editor context preserved |
| Round-trip description source/rendered modes, save and reopen | Text, formatting and links intact |
| Split supporting view, reset inspector layout | Views return correctly; draft preserved |
| Inspect a field supplied by an Event | Source clearly identified |
| Reveal additional World context items using More | Additional items appear without awkward nested scrolling |
| Follow World context attachment link | Correct Media item selected |
| Request attachment removal and cancel | Attachment remains intact |
| Find writing, timing, Connections, Details and Media at normal/narrow widths | Destinations easy to find; supporting tools unobtrusive |

Failed/delayed-save safeguards are covered separately by the existing
`test_event_timing_navigation.py` regressions for newer text/caret retention,
failed-save feedback, pending date caret and old hydration generations. The
completed 35-case KRT-78 navigation/theme run in this session included these
cases; this is reused automated evidence, not a native failure-injection test.
No additional guided human task remains. No unasked task or measured improvement
is inferred from these confirmations. The owner accepted the revised method;
historical comparison counts and partial outcomes below remain unchanged.

## Historical comparison plan and evidence

Use [benchmark v1.2](../../authoring-benchmark.md) verbatim. This is a comparison
register, **not an executed run**. The user authorized preserving the baseline
and implementing before human measurement. Earlier partial v1.1 and seeded
assisted runs are separate evidence, never substitutes for these twenty tasks.

**Partial implementation recordings:** [Human run 1](human-run-1.md) reviews
`UX Part 1.mp4` and KA-01–10. [Human run 2](human-run-2.md) reviews
`Video Project 11.mp4` and KA-11–20, including a read-only log/database
persistence cross-check. Both have partial semantic outcomes. They are
continuations in one existing world, not a complete new-empty-world matched
baseline/implementation pair. The first title appears to show `b2fa333b`;
the exact runtime revision and environment remain incomplete. This register
therefore remains a pending comparison, with NM counts. Do not infer zeros or
complete task acceptance from completion messages.

| Run metadata | Baseline | Implementation |
| --- | --- | --- |
| Revision | `5e7942f7cdca032fc1c3af3be563799a8c04f366` | Partial run title appears `b2fa333b`; full runtime hash unverified |
| Catalog | v1.2 | v1.2 |
| Participant / experience / prior exposure | Not recorded | Familiar participant; exact experience not measured |
| Date / app version / OS / Qt / theme | Not recorded | 2026-10-05 and 2026-10-10 / v0.19.7 Beta visible / Windows / Qt unverified / dark |
| Viewport / inspector width / height | Not recorded | Not recorded |
| Calendar / initial playhead | Not recorded | Gregorian labels; initial viewed date around 18 January 1228; World Year 1 |
| Empty-world video / dependencies created on camera | Not recorded | Empty state visible in run 1, but setup/restart precedes capture; run 2 continues in the existing world |
| Map image / hash / recording path | Not recorded | Video/SRT pairs and hashes in [run 1](human-run-1.md) and [run 2](human-run-2.md); KA-13 reused an existing map; supplied image not verified |

For each run and task, copy the benchmark's full task record. Additionally record
**destination changes, disclosures, wrong turns, and ambiguity separately**.
Count the Fields/Sheet view switch as a view change. A move from a primary tab
to a disclosure must not become a manufactured reduction in complexity. Count
the World context More disclosure, auxiliary open/return actions, action menus,
dialogs and source-mode switches explicitly. Record assistance and subsequent
observer verification separately from the initial attempt.

The [supporting-feature refinement](supporting-refinement.md) adds direct
Summary… / Draft with AI… panel actions and groups three read-only views under
History & context. Record each writing-panel opening and the shared information
disclosure. The intermediate `7f723d08` renders are structural comparison
evidence, not a completed human baseline or a substitute for the final revision.

KRT-77's Linked events repair now places labeled Viewing and World
Time markers before, between or after event cards, including an empty list.
Focused offscreen widget checks cover zero, one, two and three events and viewed
dates before, at, between and after the event dates. This is automated
presentation evidence. On 2026-10-10 the user reported that KRT-77 looked good
in human review. This is a separately recorded human pass; no source video,
route-coaching details or measured inspector widths were supplied. The report
does not complete KRT-45's matched KA-01–20 comparison.

On 2026-10-18 the user completed a guided, self-reported native follow-up.
At normal inspector width, the user answered "All three is a yes, it is under
history and context" when asked whether the viewed date, its position relative
to linked events, and its distinction from World Time were understandable.
After being asked to narrow the inspector to approximately 360 px, the user
confirmed the same details remained readable and understandable: "yes clearly".
This records a human clarity pass at both reported widths. Exact dimensions,
runtime revision, theme, event count and dates were not independently measured;
no recording was supplied. The participant had prior exposure and received task
prompts, so this follow-up does not establish first-use discovery without
coaching or native coverage of every sparse/out-of-range case. The existing
automated boundary coverage remains separate. On this checkout, the focused
`tests/unit/test_timeline_display.py` suite passed all 20 cases on 2026-10-18.

On 2026-10-18 the user explicitly accepted this guided question-and-answer
review method for KRT-77 and requested removal of the video requirement.
KRT-77's acceptance now permits guided, self-reported native review with written
outcomes at normal and approximately 360 px widths; video and uncoached first-use
discovery are not required. The review above satisfies that human acceptance.
Implementation is committed as `e4da0974`, and the focused automated boundary
checks pass. This changes KRT-77's evidence requirements without asserting an
uncoached discovery result or completing KRT-45's wider matched comparison.

`NM` below means **not measured**, never zero. The baseline is **not executed**;
the two partial implementation recordings attempted KA-01–20. B/A are
baseline/after counts. The after verification cells summarize evidence limits
from those recordings, not full task passes.
Verification includes
semantic correctness, save/reopen, UUID identity and context retention, as
specified by the catalog.

| Task | Destination changes B/A | Disclosures B/A | Wrong turns B/A | Ambiguity B/A | Assistance B/A | Verification B/A |
| --- | --- | --- | --- | --- | --- | --- |
| KA-01 create character | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / Character observed; UUID unverified |
| KA-02 reopen same character | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / Return observed; UUID unverified |
| KA-03 description persistence | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / Text remains after return |
| KA-04 linked mention and return | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / Link visible; follow/return unverified |
| KA-05 independent authored connection | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / Connected row visible; timing unverified |
| KA-06 membership and note | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / Member/note visible; reopen unverified |
| KA-07 fixed start at playhead | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / Exact-date setup mismatch; fixed-start independence unverified |
| **KA-08 dynamic event-linked end** | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / Date change/restore visible; bound-end verification partial |
| KA-09 unknown month/day | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / Year-only controls visible; stored precision unverified |
| **KA-10 approximate year** | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / c. 1218 visible; reopen unverified |
| KA-11 independent duration | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / Approximately 1218 and 3 days persisted |
| KA-12 viewed date vs World Time | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / Date navigation and selection observed; direct action not found |
| KA-13 map placement | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / Existing map/marker reused; creation not shown |
| KA-14 region geometry | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / Base polygon created; dated revision not shown |
| **KA-15 journey Apply/undo/redo** | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / Journey applied and playhead effect observed; undo/redo not captured |
| KA-16 map-switch working copy | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / Guard offered; participant chose Discard of separate draft |
| KA-17 graph temporal scope | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / Declared untestable; filters/date retention not checked |
| KA-18 document organization | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / Reorder visible; hierarchy/return/undo not established |
| **KA-19 inspect advanced values unchanged** | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / Original relations and advanced values persisted; fixed start differs from KA-07 request |
| **KA-20 writing/link/mode/save/navigation** | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / Charter text/link persisted; other interaction checks not shown |

The implementation has four primary destinations instead of seven. This source
fact is not a participant result. Writing and timing remain together as before;
tags and custom fields now share Details; Sheet is an alternative view, and
World context is a disclosed supporting view. Confirm the five creator task
categories — writing, timing, connections, structured details and media — are
predictable through observation, not a facilitator naming their destinations.

Supplementary human checks remain pending:

| Check | Success criterion | Status |
| --- | --- | --- |
| Tags | Add/remove tags above Fields/Sheet; save and reopen | Not executed |
| Typed fields | String, number, Boolean and source indicators retain meaning | Not executed |
| Sheet | Edit a value, switch Fields/Sheet, arrange rows/weights and save/reopen layout | Not executed |
| Media | Add attachment/caption, select via context link, edit/remove through guarded actions | Not executed |
| World context | Read-only object/map/attachment links and bounded More work; no competing embedded scrollbar | Not executed |
| Independent supporting views | Split World context and Sheet, write concurrently, show/return/reset; retain drafts and inner views | Not executed |
| Save lifecycle | Save/Discard/Cancel, failed save and delayed acknowledgement preserve selection, caret, scroll, undo and newer drafts | Not executed |

Automated and component-render results for these capabilities are recorded in
[implementation evidence](README.md). They do not fill this human register.
