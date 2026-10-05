# KRT-45 human comparison — pending

Use [benchmark v1.2](../../authoring-benchmark.md) verbatim. This is a comparison
register, **not an executed run**. The user authorized preserving the baseline
and implementing before human measurement. Earlier partial v1.1 and seeded
assisted runs are separate evidence, never substitutes for these twenty tasks.

**2026-10-05 partial implementation run:** [Human run 1](human-run-1.md) reviews
`UX Part 1.mp4` with its matching SRT. KA-01–10 were attempted, with partial
semantic outcomes; KA-11–20 were not executed. The recorded inspector matches
the final refinement; the title appears to show `b2fa333b`. World setup precedes
the capture, exact runtime/environment metadata is incomplete, and no matched
human baseline or exhaustive interaction counts were recorded. This register
therefore remains a pending comparison, with NM counts. Do not infer zeros or
completed task acceptance from the participant's completion messages.

| Run metadata | Baseline | Implementation |
| --- | --- | --- |
| Revision | `5e7942f7cdca032fc1c3af3be563799a8c04f366` | Partial run title appears `b2fa333b`; full runtime hash unverified |
| Catalog | v1.2 | v1.2 |
| Participant / experience / prior exposure | Not recorded | Familiar participant; exact experience not measured |
| Date / app version / OS / Qt / theme | Not recorded | 2026-10-05 / v0.19.7 Beta / Windows / Qt unverified / dark |
| Viewport / inspector width / height | Not recorded | Not recorded |
| Calendar / initial playhead | Not recorded | Gregorian labels; initial viewed date around 18 January 1228; World Year 1 |
| Empty-world video / dependencies created on camera | Not recorded | Empty state visible; setup/restart precedes capture; KA-01–10 dependencies created on camera |
| Map image / hash / recording path | Not recorded | Partial video/SRT pair and hashes in [run 1](human-run-1.md); map tasks not run |

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

`NM` below means **not measured**, never zero. The baseline is **not executed**;
the partial implementation run attempted KA-01–10. B/A are baseline/after counts.
The after verification cells summarize evidence limits from that run, not passes.
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
| KA-11 independent duration | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM |
| KA-12 viewed date vs World Time | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM |
| KA-13 map placement | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM |
| KA-14 region geometry | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM |
| **KA-15 journey Apply/undo/redo** | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM |
| KA-16 map-switch working copy | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM |
| KA-17 graph temporal scope | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM |
| KA-18 document organization | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM |
| **KA-19 inspect advanced values unchanged** | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM |
| **KA-20 writing/link/mode/save/navigation** | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM | NM / NM |

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
