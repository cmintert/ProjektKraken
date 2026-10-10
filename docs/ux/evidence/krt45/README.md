# KRT-45 implementation evidence

Recorded 2026-10-04–05 for [KRT-45](https://linear.app/projektkraken/issue/KRT-45/define-and-validate-canonical-inspector-information-architecture).
Implementation and automated verification are complete. **Human acceptance is
pending.** This evidence does not establish fewer observed destination changes,
first-use discoverability, or completion of the full authoring benchmark.

The [first KRT-45 human review](human-run-1.md), recorded and reviewed on
2026-10-05, covers attempted KA-01–10 under catalog v1.2. It records dropdown
scroll mutation, missing Linked events orientation, relation-form ambiguity and
the needed optimizations, with source-video timecodes and the matching SRT.
The 26 full-frame screenshots were removed from the current worktree at the
user's request because they included VS Code; their capture metadata is retained.
Several semantic checks remain partial. The [second human review](human-run-2.md),
recorded on 2026-10-10, covers attempted KA-11–20 in the same continuing world.
Read-only database and log checks confirm KA-19 relation persistence and KA-20
charter/link persistence. The matched baseline comparison remains pending.
KRT-52/53 track the newly identified dropdown/link-action work;
KRT-45/22/14 retain their existing scope. Human acceptance is still pending.

The remaining KRT-45 work is now tracked in focused Linear children:
[KRT-77](https://linear.app/projektkraken/issue/KRT-77/show-viewed-date-position-in-linked-events-for-sparse-and-out-of-range)
for Linked events orientation,
[KRT-78](https://linear.app/projektkraken/issue/KRT-78/make-event-date-navigation-and-commit-feedback-predictable)
for Event date action/commit feedback,
[KRT-79](https://linear.app/projektkraken/issue/KRT-79/make-inspector-writing-tool-disclosure-state-recognizable)
for writing-tool state,
[KRT-80](https://linear.app/projektkraken/issue/KRT-80/center-and-bound-the-entity-and-event-writing-column)
for writing-column layout, and
[KRT-81](https://linear.app/projektkraken/issue/KRT-81/run-matched-ka-01-20-human-comparison-and-close-krt-45-acceptance)
for the matched human comparison. KRT-80's layout is now implemented in
`d062dc22`; this list does not claim the broader KRT-45 human acceptance.
KRT-79's disclosure-state repair is recorded in the
[writing-tool evidence](../krt79/README.md); its uncoached human recognition
check remains pending.

The user explicitly authorized preserving the baseline and continuing
implementation while the complete human v1.2 comparison remains pending.
The issue stays In Progress. Contract v1 is unchanged.

The [choice-wheel fix and inventory](human-run-1.md#f1-fix--krt-52-2026-10-05)
implements the F1/KRT-52 follow-up from this review. Closed unfocused choices now
pass wheel navigation to the form; focused editing and popup scrolling remain
available. Automated acceptance and before/after diagnostics are recorded there;
the broader KRT-45 human acceptance remains pending.

This report records the initial canonical implementation, commit `7f723d08`.
The later [supporting-feature refinement](supporting-refinement.md) replaces
the five large supporting rows with contextual writing actions and one quiet
History & context heading. The original renders below remain unchanged.

## Preserved baseline

Pre-change revision: `5e7942f7cdca032fc1c3af3be563799a8c04f366` (KRT-51).
The source archive was made before production edits. These local artifacts are
excluded from the implementation commit:

| Artifact | Purpose | SHA-256 |
| --- | --- | --- |
| `artifacts/worktree-cleanup/2026-10-05/temp-snapshot/krt45/baseline-source.zip` | Tracked source, docs, scripts, tests, dependency authority, themes and launchers | `1931399fb91788c2418f9741d6512fbfd46a51fff764cc8b5e686cb728b5a7cf` |
| `artifacts/worktree-cleanup/2026-10-05/temp-snapshot/krt45/baseline-runtime-support.zip` | Default assets, browser libraries, requirements, pytest settings and packaging metadata from the same revision | `6b76d22d42698b5c3f50327ed551f1b86c924192c4044e5dc8e134465e9c6d19` |
| `artifacts/worktree-cleanup/2026-10-05/temp-snapshot/krt45/baseline/` | Both archives extracted; baseline test failure reproduced here | Recoverable from the two archives |

The user-requested cleanup on 2026-10-05 moved the complete temporary tree
intact to the ignored local `artifacts/worktree-cleanup/2026-10-05/temp-snapshot/`
archive. All 2,411 file hashes were verified after relocation. Baseline archives,
QA worlds, exports, diagnostics and earlier performance evidence remain local;
the archived scratch files are no longer tracked in Git. The local
`cleanup-manifest.json` beside the archive records their paths and hashes.

The immutable Git revision is also retained. Recover the archives without
changing the implementation checkout:

```powershell
New-Item -ItemType Directory -Path artifacts/worktree-cleanup/2026-10-05/temp-snapshot/krt45 -Force | Out-Null
git archive 5e7942f7cdca032fc1c3af3be563799a8c04f366 -o artifacts/worktree-cleanup/2026-10-05/temp-snapshot/krt45/baseline-source.zip src docs scripts tests pyproject.toml themes.json launcher.py start-kraken.cmd README.md CHANGELOG.md
git archive 5e7942f7cdca032fc1c3af3be563799a8c04f366 -o artifacts/worktree-cleanup/2026-10-05/temp-snapshot/krt45/baseline-runtime-support.zip default_assets lib requirements requirements.txt pytest.ini packaging ProjektKraken.spec
```

To run the preserved application, use the repository virtual environment's
absolute Python path with `-m src.app.main`, with the extracted baseline as the
working directory. **Create a new empty world there**; do not reuse a seeded world
or an existing personal world. Recording must show that empty state and create
dependencies on camera. No human benchmark was recorded in this implementation
session. The [partial v1.1 video review](../krt46/human-run-1.md) and
[seeded assisted run](../krt46/baseline.md) remain separate supporting evidence.

## Complete destination and disclosure inventory

The initial tab order in both editors was **Details, Context, Tags, Relations,
Gallery, Attributes, Sheet**. The following inventory was traced on the preserved
source before the layout change. The actual widgets, documents, actions and
authoring signal connections remain live after composition.

| Existing capability and nested route | Canonical home | Preservation / visible route |
| --- | --- | --- |
| Name, type, Fast Inject | Persistent header | Same controls above destinations; injection moves to its own row at narrow widths |
| Entity viewed-state banner / editability | Persistent header | Wrapping banner; same source-aware mutation semantics |
| Save Changes / Discard, autosave feedback | Persistent footer | Same save signals, coordinator guards and acknowledgements |
| Description, formatting, MD/HTML, TOC, spelling, F11 Focus writing | Overview | Existing document and actions; visible writing overflow menu supplements native toolbar overflow |
| Entity description source / Start a new description at this time | Overview | Wrapping source caption and same deliberate ownership choice |
| Entity Timeline disclosure | Overview | Initially collapsed; same timeline renderer and event navigation |
| Summary disclosure / Generate, Edit, Done, Cancel, Copy, Delete | Overview | Initially collapsed; `Summary (available)` indicates retained content, including staged content, without implying a completed save |
| Generate description disclosure / provider, model, strategy, prompt and preset choices | Overview | Initially collapsed; same generator and preview/cancel actions |
| Generator RAG, spatial and World Context options | Inside Generate description | Same options and generation semantics |
| Raster maps disclosure / appearance links | Overview → Map appearances | Renamed visible route; same appearance data and navigation |
| Event text-first date / calendar picker | Overview | Same parser, precision, invalid draft and Enter/Escape behavior |
| Date fields disclosure → Year, Month, Day and qualification | Overview → Date details & uncertainty… | One disclosure; labeled components stack using actual date-widget width |
| Possible date limits… → enable Possible from / Possible until | Inside Date details & uncertainty… | Same exceptional dialog and inclusive-period semantics |
| Time… → time components | Overview beside date disclosure, below it when compact | Same disclosure and time semantics |
| Event has duration → End date / duration… | Overview | Same opt-in, advanced disclosure, summaries and independent endpoint semantics |
| Chronology… / ordering counts and dialog | Overview beside timing | Separate labeled action; same ordering constraints |
| Date evidence… / source counts and conflict feedback | Overview beside timing | Separate labeled action; same source evidence and date selection |
| Show world at this event | Overview | Same saved-date navigation and playhead guards |
| Context tab / bounded More… | Overview → World context (read-only) | Initially collapsed; existing renderer, links and bounded additional-context disclosure; Overview owns vertical scrolling while embedded |
| Authored outgoing/incoming relationships and their row actions | Connections | Existing lists, direction, notes, types and full relation dialogs |
| Event Participants / Locations / Custom relations disclosures | Connections | Existing groups and count indicators; existing Add/Edit/Remove and drop routes |
| WikiLink mentions / linked references | Writing / existing context and relation distinctions | No conversion of mentions into authored relationships |
| Tags / Add or Enter / individual removal | Details above Fields / Sheet | Same tag editor |
| Typed Attributes / Add, Remove, type and source columns | Details → Fields | Default view; same table and source information |
| Sheet / attribute values, types, rows, weights, headers, spacers, dividers, text | Details → Sheet | Same visual builder and synchronization; same context menu and Alt+arrow layout shortcuts; visible overflow menu for toolbar actions |
| Gallery / attachments, captions, Add/Edit/Remove | Media | Existing gallery; Entity context attachment links activate the stable destination and select the existing attachment |
| Tab drag/reorder, vertical splits, reset | Inspector More / drag | Four primary destinations; auxiliary World context and Sheet can independently move below their home |

## Composition and retention

`EditorPresentation` supplies existing widgets to the shared
`EditorInspectorComposition`. No command payload, migration, worker slot or new
application coordinator was introduced. KRT-40 save preparation and KRT-35
architecture guardrails remain separate concerns. The widget → coordinator →
command → worker mutation path and KRT-51 checkpoint path are unchanged.

`SplitterTabInspector.add_tab` accepts optional stable IDs; widget-based
activation remains compatible. IDs are `overview`, `connections`, `details`,
`media`, `world_context`, and `sheet`. More offers destination navigation, Split
active section below, Open World context below, Open Sheet below and Reset
inspector layout. Detached homes indicate relocation and offer Show / Return
here; the detached pane also offers Return here. Reopening activates that pane.
Moving a tab across independent inspectors is rejected. Failed or partially
inserted moves restore the original widget, title, tooltip and enabled state.

Construction starts on Overview / Fields. Object changes retain destination,
split layout and Fields/Sheet choice. Same-object refreshes retain disclosures.
Reset returns auxiliary content home and restores the four primary tabs without
changing data or inner view choices. Tests retain the live writing document,
caret, selection, scroll, undo and dirty state through navigation and resizing.
Deferred drag cleanup safely tolerates a reset that already removed a pane.

## Contract traceability

| Contract | Applied behavior / evidence |
| --- | --- |
| 1 — disclosure | Summary, generation and World context start collapsed; retained summary content, date/duration summaries and source/count feedback remain visible; opening/closing controls does not mutate authored values |
| 2 — keyboard | Existing local date Enter/Escape and multiline ownership retained; disclosures remain Space/keyboard accessible; shortcuts supplement labeled actions |
| 3 — surfaces | Ordinary authoring stays in inspectors; existing independent chronology, evidence and ownership dialogs remain justified multi-step exceptions |
| 4 — language | Overview, Connections, Details, Media; labeled Year/Month/Day and uncertainty route; existing source distinctions retained |
| 5 — context | Stable live widgets and document; split/return/reset and same-object refresh retain drafts, selection, caret, scroll and undo |
| 6 — state | Identity and temporal feedback stay above destination pages; save/discard remain visible; context is explicitly read-only; detached homes identify relocation |
| 7 — discoverability | Always-visible labeled inspector More, visible auxiliary routes and return controls; visible writing/Sheet action menus at narrow widths |
| 8 — consistency | One shared composition for both editors, shared disclosures and overflow presentation |
| 9 — feedback | Existing save/discard/cancel, failed-save recovery and newer-draft acknowledgement/checkpoint tests pass; no new mutation path |
| 10 — complexity | Destination and disclosure counts must remain separate; the [human comparison](benchmark-comparison.md) is pending, so no measured usability improvement is claimed |

## Rendered verification

[Before manifest](before/captures.json): 36 isolated component images captured
before production changes. [After manifest](after/captures.json): 144 component
images plus 12 More-menu images. Each matrix contains both editors, production
`main.qss`, Segoe UI 10 pt, dark/light themes, requested widths 331/560/871 px and
a 480 px short-height state. Normal height is 720 px. Python 3.13.14, Qt/PySide6
6.10.1, Windows 11, `QT_QPA_PLATFORM=offscreen`; settings and attachment loading
are isolated from personal worlds. After captures include populated synthetic
context, a summary, typed attributes, all four destinations and both auxiliary
splits. They verify rendered components, not worker/database persistence or
human task performance. The empty gallery uses an isolated snapshot provider.

The baseline Entity requested at 331 px expanded to **376 px** in both themes.
After composition, both inspectors render at the actual requested 331 px.
All after captures report zero Overview horizontal-scroll range and no visible
scroll area with a nonzero horizontal-scroll range. Visual review checked label
readability, wrapping, narrow action access, tags above the view switch,
light/dark Sheet contrast, read-only context and split/return placement. The
shared code uses actual available pane widths instead of only the outer dock.

Representative review images:

| Check | Dark | Light |
| --- | --- | --- |
| 331 px identity/source and writing | [Entity Overview](after/entity-dark_mode-331-overview.png) | [Entity Overview](after/entity-light_mode-331-overview.png) |
| 331 px structured date qualification | [Event advanced](after/event-dark_mode-331-advanced.png) | [Event advanced](after/event-light_mode-331-advanced.png) |
| 560 px timing + writing | [Event Overview](after/event-dark_mode-560-overview.png) | [Event Overview](after/event-light_mode-560-overview.png) |
| 871 px tags + typed fields | [Entity Details](after/entity-dark_mode-871-details.png) | [Entity Details](after/entity-light_mode-871-details.png) |
| 331 px Sheet actions and contrast | [Entity Sheet](after/entity-dark_mode-331-sheet.png) | [Entity Sheet](after/entity-light_mode-331-sheet.png) |
| 331 px relationship groups | [Event Connections](after/event-dark_mode-331-connections.png) | [Event Connections](after/event-light_mode-331-connections.png) |
| 560 px context without nested vertical scrolling | [Event context](after/event-dark_mode-560-context_embedded.png) | [Event context](after/event-light_mode-560-context_embedded.png) |
| 871 px independent Sheet pane and home | [Entity split](after/entity-dark_mode-871-sheet_split.png) | [Entity split](after/entity-light_mode-871-sheet_split.png) |
| 331 px independent World context pane | [Entity split](after/entity-dark_mode-331-context_split.png) | [Entity split](after/entity-light_mode-331-context_split.png) |
| 331 × 480 px footer/action accessibility | [Event short](after/event-dark_mode-331-short.png) | [Event short](after/event-light_mode-331-short.png) |
| Named destinations and layout routes | [More menu](after/event-dark_mode-331-more-menu.png) | [More menu](after/event-light_mode-331-more-menu.png) |

Reproduce using the capture script and source from commit `7f723d08`:
`.venv\Scripts\python.exe -m scripts.capture_inspector_evidence --output tmp/krt45/review`
with offscreen Qt. The after manifest records the pre-commit base revision and
SHA-256 hashes of source modules, capture script, stylesheet and themes. The
implementation commit containing this report identifies the reviewed change;
the base revision in the manifest is not a claim that the after images came
from unchanged baseline code.

The current capture script records the expanded refinement matrix instead.

## Automated verification

| Gate | Result |
| --- | --- |
| Focused editors, composition, splitter, presentation, focus writing, checkpoint, cursor/autosave, Sheet, Summary, editor mixin, context renderer and unsaved-change checks | **340 passed, 1 skipped, 1 deselected**; 23.38 s |
| Bounded `pytest -m ci_fast -q -o addopts= --maxfail=3` | **1,364 passed, 2 skipped**, 4,373 deselected, 23 subtests passed; 35.54 s; one existing Starlette/httpx deprecation warning |
| `ruff check src/ tests/ scripts/capture_inspector_evidence.py` | Passed |
| `mypy src/` | Passed, 430 source files |
| `scripts.check_test_policy --update`, then `scripts.check_test_policy` | Passed; 5,739 collected, 1,366 ci_fast; 40 new regression cases; zero unreviewed additions after update |

The deselected `tests/test_unsaved_changes.py::test_mainwindow_check_unsaved_changes`
fails at `MainWindow._init_widgets_skeleton`: its old `MockEditor` lacks
`show_world_at_event_requested`. The exact failure was reproduced against the
extracted immutable pre-change revision. It is not a new inspector failure.
Actual coordinator Save/Discard/Cancel guards and editor failure/checkpoint paths
pass in the focused run. Skips remain explicit; they are not counted as passes.

New cases cover stable routes and duplicate IDs, visibility, nested view choice,
same/new-object loads, independent auxiliary panes, return/reset, drag then return,
partial/rejected insertion recovery, attachment selection, invalid drafts,
selection/scroll/undo retention, tags/Sheet synchronization and overflow action
execution. Existing focused cases protect failed saves, rich/source and WikiLink
retention, delayed acknowledgements and newer drafts.

No executable was built. Unrelated tracked temporary-artifact deletions were
preserved and excluded from the commit. No push is authorized or performed.

## Remaining acceptance

Run all KA-01–20 twice under catalog v1.2, on the preserved baseline and on the
implementation commit, each starting in a new empty world. Use the comparison
record below, retain failures/assistance, and protect KA-08/10/15/19/20 explicitly.
If unnecessary destination changes do not decrease in affected workflows, or
advanced capability/context is lost, refine and repeat. KRT-45 may move to Done
only after that evidence is recorded and the verified implementation commit is
referenced in Linear.
