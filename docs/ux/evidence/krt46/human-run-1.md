# Human video review: KA-01–15, Run 1

Reviewed 2026-10-04 against authoring benchmark v1.1. This is a preliminary
evidence review, not a claim that all reported tasks meet every success check.

## Inputs and method

* Video: `KA-01-15.mp4`.
  SHA-256: `2beecc953ff191ef6870d7f5afa6297e1629946d38a5ed5f9e34942288378e90`.
  Duration: 24:27.486; recorded frame size: 1920 × 1080.
* Subtitles: `Video Project 7.srt`.
  SHA-256: `36826a1fa7d2f77b9641aa2b6f891b32ce06dd85e8e51f3a2f252192d57e5613`.
  Last cue ends at 18:15.105; the spoken task content ends around KA-11.
* Visible app title: v0.19.7 (Beta), revision label `3d402709`, world
  `UX Video 2026-10-04 Run 1`. Dark theme. Full revision, OS/Qt versions,
  calendar configuration, inspector measurements and image hash: not measured.
* Read the full supplied SRT; visually inspected timestamped video frames every
  30 seconds and additional outcome frames. This is sampled visual inspection,
  not continuous playback or an independent transcription of the audio.
* Subtitles contain recognition errors, especially names and UI terminology.
  Interpret them alongside visible UI; do not treat their spelling as lore data.
* No database was inspected. UUID identity, exact persisted relation settings,
  undo command boundaries and save/reopen checks cannot be inferred from a
  visible object name alone.
* Window capture appears to omit separate dialogs: underlying inspector remains
  visible during narrated relation editing. The precise capture cause is not
  established. Missing dialog pixels are an evidence limitation, not an app bug.
* All tasks were reported complete in chat. The statuses below describe only
  the evidence reviewed, and preserve partial or unverified checks.
* Time windows below locate activity; they are not clean completion times.
  Reading prompts, chat pauses, setup and discovery are mixed in the recording.

## Task evidence

| Task | Approximate evidence window | Observed outcome and limits |
| -- | -- | -- |
| KA-01 | 00:25–00:54 | Character creation supported: participant explicitly corrects Concept to Character; Character is visible at 01:00. Creation dialog/UUID not visible. |
| KA-02 | 01:10–01:36 | Participant narrates deselection/reselection and search; same named Character selected at 01:30. UUID identity not independently checked. Navigating away in an otherwise empty world is described as awkward. |
| KA-03 | 01:54–02:44 | Creates Freiburg as an extra Location to allow navigation, writes the Rhine-history sentence and narrates returning successfully. Text remains visible at 03:00 and 03:35. This extra object changes later map setup relative to the catalog. |
| KA-04 | 03:09–05:08; recovery 06:05–06:35 | Partial/deviated: House Bjornaer remains Concept, not the requested group. Plain description mention is interpreted as a relation; member_of is created and the relation arrow is followed. WikiLink recovery comes later during KA-05. Origin/caret restoration and link UUID not verified. |
| KA-05 | 05:45–06:40 | Generic-capture step not demonstrated separately: participant says the relation was already created. It was already member_of. WikiLink insertion is attempted instead; participant reports it requires prior knowledge and does not immediately change presentation. No observed generic connection should be counted as a separate success. |
| KA-06 | 06:55–08:32 | Membership already exists, so generic-to-membership refinement is not demonstrated. Participant narrates adding notes through Edit. At 08:04–08:24 reports unintentionally changing confidence, probably with the wheel, and not understanding its meaning. At 08:30 the row shows confidence=0.6000000000000001. Notes themselves and reopening are not visible. |
| KA-07 | 08:48–11:42 | Tribunal Session dated 1 January 1187 is visible. At 10:30/11:15 playhead is 1187 while World remains Year 1. Participant initially chooses a start tied to the event, then recognizes the prompt intended something else and retries. Fixed start equal to playhead is unverified because the timing dialog is not captured. |
| KA-08 | 11:53–14:02 | Partial: Winter Council dated 1 January 1201 and Tasgilla as involved participant are visible. At 12:50–12:56 participant explicitly asks what involvement means/in what. At 13:43–13:55 remains unsure about Ends at Event semantics. Dynamic binding and event-date change/restore are not demonstrated by the reviewed evidence. |
| KA-09 | 14:20–15:37 | Year-only charter is supported: input 1218, display of an uncertain occurrence across the year, and participant interprets it as sometime during 1218. Database precision and reopen not checked. |
| KA-10 | 15:58–16:57 | Approximate qualification visibly achieved: Date fields exposes Date qualification and c. 1218 is visible at 17:00. Participant searches several surfaces and says the control is difficult to find. No save/reopen test established. |
| KA-11 | 17:04–17:54 | Three-day duration visibly entered; participant calls entry relatively easy but timeline representation unclear. Later 19:40 frame retains 3 D and timeline label Starts: c. 1218 · Duration: 3 days. Persisted reopening is not independently established. |
| KA-12 | after 18:15; outcome frames 19:00–19:40 | Charter remains selected. Playhead first visibly reaches Year 1218 (19:00), then 1 January 1219 (19:40); World remains Year 1. Navigation dialog route and spoken interpretation are absent from SRT/capture. Positive visible temporal-context outcome. |
| KA-13 | around 20:00–20:30 | No Map Available at 20:00; map image with Freiburg and Tasgilla markers at 20:30. Map setup and placement supported visually. Image is a geographic background, not the earlier assisted schematic. Exact existing-object UUID, normalized position and duplicate-free placement not verified. |
| KA-14 | around 21:30–22:40 | Upper Rhein linked polygon visible at 22:00 and a changed border visible at 22:30/22:40. Explorer labels the object Location. Do not assume a separate Region entity type is required: catalog's spatial intention is a region polygon. Edit entry gesture, Enter/Escape ownership and persistence after reopen unverified. |
| KA-15 | around 23:00–24:27 | Two-point trajectory working copy visible. At 24:00/24:26 editor shows two points, second date 31 December 1249, allowed after first date 1 January 1219. Apply/Cancel remain visible at the end. Apply, reopen/edit and undo are not demonstrated by sampled evidence; do not count the working copy alone as fully verified completion. Basel identification is unverified. |

## Findings to carry forward

1. **Reference versus relation confusion (04:16–04:25, 06:05–06:35).** The
   participant interprets following a reference as creating a relation. Language
   switching in this facilitated session contributes to the confusion. WikiLink
   discoverability and rich presentation feedback deserve inspection; avoid
   attributing all confusion solely to the product.
2. **Type default missed for House Bjornaer (03:30 onward).** Character type was
   deliberately corrected, but House Bjornaer stays Concept throughout sampled
   later views. This is concrete evidence that default type can survive a
   different stated intention. Existing audit owner: <issue id="8e5a0482-523c-460c-a3fb-8c7b8ff5cbdb" href="https://linear.app/projektkraken/issue/KRT-14/require-deliberate-entity-type-choice-in-normal-creation">KRT-14</issue>.
3. **Small relation navigation affordance (04:48–05:04).** Participant describes
   arrow as very small and unlikely to be recognized without knowledge, while
   acknowledging the useful tooltip. The arrow is visible at 05:00.
4. **Scrolling unintentionally changes numeric values (08:04–08:24).** Participant
   reports an accidental confidence change. In the follow-up on 2026-10-04, the
   participant clarifies that mouse-wheel scrolling changes values in boxes even
   when those boxes are not selected, instead of scrolling the surrounding
   content. This is participant-confirmed behavior; the omitted dialog prevents
   independent visual verification of focus and wheel delivery. The primary
   problem is unintended data mutation during navigation. Wheel input over an
   unselected numeric control should scroll the surrounding content rather than
   edit its value. The visible `0.6000000000000001` is a separate formatting
   defect; formatting alone would not prevent the accidental change. The
   participant also expresses uncertainty about confidence's meaning. Existing
   relations owner: <issue id="81c67f3e-03a5-402d-912f-a16b9a0d5867" href="https://linear.app/projektkraken/issue/KRT-22/expose-loose-relation-capture-before-full-relation-editing">KRT-22</issue>.
5. **Date save expectation mismatch (09:31–09:41).** Participant expects autosave
   while editing the date but says it occurs only after leaving the field. This
   demonstrates unclear commit feedback, not proof of data loss.
6. **Fixed-versus-event-bound time and task wording (10:35–11:27,**
   **12:50–13:55).** Initial event-bound start differs from KA-07's fixed-playhead
   requirement. KA-08's word involvement is too ambiguous in this session;
   facilitator wording must identify the intended source-event relation before
   treating semantic failure as a product issue. Facilitator guidance repeated that
   ambiguity and should be corrected for continuation/comparable runs.
7. **Approximate date difficult to find (16:05–16:50).** Successful after searching
   elsewhere and expanding Date fields. The successful state also shows cramped
   structured-date labels. Existing inspector owner: <issue id="279cc00b-1d20-489e-aa48-a354a706d663" href="https://linear.app/projektkraken/issue/KRT-45/define-and-validate-canonical-inspector-information-architecture">KRT-45</issue>.
8. **Duration entry easy, timeline meaning unclear (17:27–17:43).** Keep the
   positive entry result alongside the representation complaint.
9. **Journey completion remains unverified (24:00–24:27).** Last reviewed frames
   show a two-point working copy with Apply still available. Before KA-16,
   establish whether this journey was applied after recording; do not assume a
   persisted baseline from the chat completion message.

## Continuation

Preserve this world and recording. KA-16–20 remain pending. For future recording,
capture the entire desktop or include separate dialogs, and extend subtitle
coverage through the actual end. Before KA-16, check the saved baseline journey;
if recovery is required, record it as setup/assistance rather than rewriting the
KA-15 result. Preserve previous failed attempts and uncertain outcomes.

No completion-rate score or performance improvement is inferred. No production code or commit was changed by this review.

## First conclusions and wording correction

The working hypothesis is that capabilities are available but their meaning, discovery path and completion state are not consistently clear. Participant familiarity helped progress; this one session does not establish unfamiliar-user performance.

Prioritize prevention of accidental data edits, semantic clarity, then discovery and save/finish feedback. Preserve advanced temporal and relational capabilities. A mention is a reference in prose; a linked mention connects that text to an existing entry; an authored membership relation records an explicit fact. The facilitator had blurred mention and linked mention. That ambiguity must not be presented as wholly a product defect.

Repository catalog is now v1.2. All twenty participant prompts were clarified; observer success/recovery columns remain unchanged. KA-04 explicitly says to link the group's name to its existing entry and follow that link. KA-05 asks for a separate connection. KA-07 specifies a fixed start that does not follow event rescheduling; KA-08 identifies participation in Winter Council and checks an event-linked end by moving the council to 1202 and restoring 1201. Other prompts clarify unknown precision, duration, save/reopen, map landmarks, undo/redo and unfinished edits. Run 1 KA-01–15 remains v1.1; continuation with revised prompts must record the version per task.

## Tracking and publication

[Linear review](https://linear.app/projektkraken/document/krt-46-human-video-run-1-ka-01-15-review-and-first-conclusions-c98ce75c4455).

Timecoded findings were added to KRT-14, KRT-16, KRT-22, KRT-25, KRT-45,
KRT-46 and KRT-48. Dedicated Authoring UX backlog follow-ups:

- [KRT-49 — Prevent unintended numeric edits while scrolling](https://linear.app/projektkraken/issue/KRT-49/prevent-mouse-wheel-scrolling-from-changing-unselected-numeric-inputs).
- [KRT-50 — Validate uncertain-date and duration readability](https://linear.app/projektkraken/issue/KRT-50/validate-timeline-readability-for-uncertain-occurrence-dates-with).

The source video and subtitles remain external evidence; media, decoder packages
and temporary extracted frames are not part of this repository report. The
v1.2 task wording is in [the benchmark](../../authoring-benchmark.md).
