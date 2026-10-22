# KRT-105 documentation rollout

## Change and acceptance boundary

The [authoring standard](../../../developer/documentation.md) applies to all
current documentation. This rollout revises all twelve existing user-manual
pages, adds one tutorial and four explanation pages, and aligns contributor
and agent guidance. Developer, reference and historical release collections
are not being rewritten. Application APIs, UI presentation, topic schemas and
runtime Help behavior are unchanged.

Source/rendered/automated review is separate from human prose approval,
native live Help acceptance and independent reader observations. Those human
items are **Pending**. KRT-105 stays open; the delivery commit is recorded in
Git and linked from KRT-105. Delivery reuses the verification recorded below.

## Baseline and coverage inventory

The baseline is clean implementation-start HEAD
`a6e211e9f9ccf28c7c17af945b0fb16cf2372309`, recorded in
`artifacts/krt105/baseline.json`. That local inventory captures the revision,
full original text and hashes of all twelve pages, the complete topic registry
and inspection inventory. Original material is reproducible with `git show`
at the recorded revision. Artifacts are ignored local review aids, not a second
documentation source. Preserve them until acceptance or regenerate from Git.

`artifacts/krt105/coverage.json` enumerates every original heading, explicit
anchor, task topic, excerpt target and inspection binding by chapter, with the
source files reviewed below. The audit compares the original mappings and
control appendices with the revised sources. Keeping prose unchanged is not
a claim that every control explanation has received fresh independent review.

| Existing page | Primary purpose | Behavioral source reviewed | Revision focus |
| --- | --- | --- | --- |
| User Manual | Navigation/reference | Help coordinator, context registry and existing Help tests | Tutorial/concept routes; exact-reference entry points |
| Getting Started | How-to | UIManager, DatabaseManagerDialog, Windows package workflow and live GitHub asset names | Current package example, explicit Select & Restart, canonical installation |
| Workspace and Layouts | How-to | UIManager, workspace shell/registry | Layout confirmation, theme recovery, Explorer filtering |
| Events, Entities, and Relations | How-to with comparison reference | EditorCoordinator, Event/Entity editors and relation timing tests | Save/reopen checkpoints, creation/deletion consequences, separate representations |
| Wiki editor Markdown and links | How-to | Wiki editor and existing Rich/Source/navigation tests | Persistence checkpoint, remove speculative preview roadmap |
| Timeline and Calendars | How-to | Timeline navigation/date controls and temporal tests | Viewing/story-time distinction, date persistence, calendar consequences |
| Maps, Layers, and Rasters | How-to | Map feature actions, trajectory and historical geometry tests | Draft versus saved feature, verify historical shapes, visibility recovery |
| Longform Writing | How-to | Longform membership/outline and transfer dialog | Canonical publication route, link recovery procedure |
| Search, AI, and Analysis | How-to | AI settings/search, World Context services, panel registration and transfer composition | Current Analysis route, index/search steps, settings autosave, AI acceptance |
| Import, Export, and World Transfer | How-to with format reference | Transfer dialog/coordinator, BackupCoordinator and restore service | Correct world-switch route, explicit backup/restore steps and restart verification |
| Keyboard Shortcuts | Reference | Shortcut manager and Help chord tests | Make focus ownership visible in the table |
| Troubleshooting | Recovery how-to | Logging/startup, UIManager, AI settings and raster safeguards | Startup menu limits, actionable AI recovery, historical-state diagnosis |

New pages: **Explore a changing kingdom** (tutorial), **Understand time and
historical state**, **Understand attributes, relations and mentions**,
**Understand World Context and AI interpretation**, and **Understand world
portability and recovery** (explanations). The generator and demo integration
tests are the source for Northwatch's names, dates, ruler/border changes and
uncertain report. Generate a fresh copy for execution, never edit a personal world.

## Verification record

| Check | Result |
| --- | --- |
| Original headings, anchors, IDs, excerpts and inspection bindings | Passed: 12/12 revised pages; 123 original headings, 976 explicit anchors, 49 topics and 909 bindings retained; control appendices unchanged |
| Inspection validator | Passed: declarations, excerpts and source reviews agree |
| Offline Help generation | Passed: 17 manual pages, valid links/anchors/excerpts and source manifest |
| Generated schema / strict Sphinx | Passed: schema current; strict Sphinx succeeds |
| Help regressions and demo fixture | 127 passed, 1 skipped; see `artifacts/krt105/regressions.log` |
| Test-file Ruff and format check | Passed |
| Rendered HTML and offline Qt review | Browser: 21 pages at 390/1280 px; Qt: 17 pages at 360/640 px, light/dark; no horizontal overflow in final captures |
| Human prose approval and native live Help | Pending owner review |

Commands used: `python artifacts/krt105/audit.py`,
`python -m scripts.check_help_inspection`, `python -m scripts.build_help`,
`python docs/generate_schema_docs.py --check`, and
`python -m sphinx -n -W --keep-going -b html docs docs/_build/html`.
The focused pytest run covers `test_help_bundle`, `test_help_coordinator`,
`test_help_search_inspection`, `test_help_inspection_coverage`,
`test_help_explanation_shortcuts`, and `tests/integration/test_demo_world.py`,
with `QT_QPA_PLATFORM=offscreen`. No full release or package preflight was run.

Three original bundle tests hardcoded the old page count. They now verify
complete source-page inclusion and accurate smoke-report counts. The same
navigation test checks searchable, valid destinations for all five added pages.
The final run passes; topic meanings and registry contents were not changed
to accommodate the new pages.

Render artifacts live in `artifacts/krt105/html/` and `artifacts/krt105/qt/`,
with dimensions, page text/headings and overflow measurements in their
`review.json` files. Visual inspection covered the first viewport of every page;
full-page browser captures also retain the new tutorial, explanations and forms.
These are bounded agent-rendered checks, not a claim that every unchanged control
paragraph was independently read or every page was scrolled by a human.
The first Qt capture needed explicit Windows-font registration in the local
helper; the final screenshots use Segoe UI. The checksum example was shortened
to avoid horizontal scrolling in narrow offline Help. No runtime styling changed.

The Windows release's two 0.20.1-beta1 asset names were confirmed with the GitHub
API on 2026-10-22. Demo integration tests create fresh worlds and verify persisted
ruler, description, border, location, succession-boundary and uncertain-date
behavior. They do not demonstrate an inexperienced reader following the tutorial.

`artifacts/krt105/source-identity.json` records the final dirty-worktree file
hashes for owner review. These local artifacts remain available for acceptance;
the baseline and source checks can be reproduced from Git. Native
inspection must cover F1 and fallback; pointer/focused/menu explanations;
non-activating Inspect control; history, search and Escape; modal ownership;
return focus; drafts/caret/selection, map working copies and unchanged playhead.
Automated tests of those contracts do not establish human comprehension.

## Human review and reader rounds

Use the [review form](../../../developer/documentation-review.md) for each
approved batch. Record reviewer/date, exact revision and pages/topics, live
contexts, corrections and re-review. No owner approval is inferred from the
instruction to implement this plan.

Independent rounds use the [six-task protocol](../../../developer/documentation-reader-testing.md),
with separate novice and experienced cohorts of 3–5 readers as relevant.
The owner explicitly requested that the schedule remain **Pending**. No round
owner or milestone has been agreed. This is not a scheduled study. No participants,
timings, success rates or saved outcomes have been recorded.

These rounds use fresh generated Northwatch copies, with independently checked
saved outcomes and assistance recorded per attempt. They do not replace the
empty-world authoring benchmark or KRT-18's uncoached first-value observation.
KRT-90 owns additional integrity tooling; KRT-91 owns packaged Windows Help
acceptance. Do not claim either issue complete from this rollout.
