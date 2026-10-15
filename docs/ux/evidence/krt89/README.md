# KRT-89 expert topic curation and review

Implementation/review date: 2026-10-14. Source baseline:
`32e391d206b0a4681eaf5b6dc930b377f4531a2e`. Local commit delivery was authorized
on 2026-10-14 together with the KRT-88 test/acceptance follow-up. The resulting
delivery hash is recorded in Linear.

## Human content review

Christian reviewed the 20 texts individually in the implementation conversation,
approving every text, with the explicit condition: “If they fit the code they
stay.” This is human prose review, not a claim that the three workflow scenarios
were manually executed. The reviewed drafts were integrated into the existing
canonical manual; detailed reference instructions remain alongside them.

The code check found two label discrepancies. Christian separately approved both
corrections on 2026-10-14: Text 6 uses **Duration / End Date** (the button labels
do not include “Keep”), and Text 14 uses **Timing…** rather than “Temporal
Settings”. No runtime behavior was changed to match the prose. The nine KRT-88
control excerpts remain byte-for-byte unchanged; all topic IDs/targets survive.

| Text / topic | Canonical destination | Implementation cross-check |
| --- | --- | --- |
| 1 `authoring.create` | {ref}`Create <help-authoring-create>` | EditorCoordinator creation, viewed-time default, EntityCreationDialog |
| 2 `authoring.details` | {ref}`Details <help-authoring-details>` | Event/Entity inspector fields, attributes, tags and Connections |
| 3 `writing.edit` | {ref}`Writing <help-writing-edit>` | WikiTextEdit Rich/Source safety, formatting/view actions |
| 4 `writing.links` | {ref}`Links <help-writing-links>` | Link selection, Peek, writing-return navigation and mentions setting |
| 5 `writing.focus` | {ref}`Focus <help-writing-focus>` | FocusWriting controller, existing F11/Help document-preservation tests |
| 6 `event.timing` | {ref}`Timing <help-event-timing>` | TemporalRangeWidget locks, CompactDateWidget validation, Event save status |
| 7 `date.precision` | {ref}`Precision <help-date-precision>` | Date parser qualification/precision and occurrence bounds |
| 8 `date.evidence` | {ref}`Evidence <help-date-evidence>` | TemporalEvidenceDialog source rows, preferred source and independent claims |
| 9 `event.chronology` | {ref}`Chronology <help-event-chronology>` | EventChronologyDialog ordering/gap and chronology validation |
| 10 `timeline.viewing` | {ref}`Viewing <help-timeline-viewing>` | TimeCoordinator navigation vs deliberate Set Current Time |
| 11 `entity.historical-editing` | {ref}`Historical editing <help-entity-historical-editing>` | Entity source correction, destination choice and removal actions |
| 12 `entity.value-source` | {ref}`Source <help-entity-value-source>` | Description/attribute provenance and temporal save patches |
| 13 `relations.create` | {ref}`Connections <help-relations-create>` | RelationAuthoring capture/refine/drop direction and detailed/full menu routes |
| 14 `relations.timing` | {ref}`Validity <help-relations-timing>` | RelationForm Meaning, Timing, boundary choices, shared-event identity |
| 15 `authoring.representations` | {ref}`Representations <help-authoring-representations>` | Independent attributes/relations and optional saved mentions reconciliation |
| 16 `map.features` | {ref}`Features <help-map-features>` | Feature tools, selection vs deliberate inspector navigation |
| 17 `map.historical-geometry` | {ref}`Borders <help-map-historical-geometry>` | Geometry working-copy/state resolution and dated/base editing |
| 18 `map.visibility` | {ref}`Visibility <help-map-visibility>` | TemporalValidityDialog, inclusive/exclusive bounds, independent geometry |
| 19 `map.trajectories` | {ref}`Journeys <help-map-trajectories>` | TrajectoryEditCoordinator, timed/automatic points and Apply/Cancel |
| 20 `longform.recovery` | {ref}`Longform <help-longform-recovery>` | Membership exclusion vs world deletion, refresh and backup/restore safeguards |

## Navigation and discoverability

Christian separately approved the supporting inspection-target guide on
2026-10-14. The [source review identity](source-review.json) records the exact
canonical input hashes, reviewed topic destinations and unchanged excerpt hashes
against the source baseline above.

Date evidence/Chronology and historical editing/Value Source now have distinct
section titles and landing points. Writing and Longform use focused task sections
instead of a page-level target. Explicit IDs remain stable; the former combined
`record-sources-and-ordering` anchor remains as a compatibility target.
Useful concept links are reciprocal in related-topic metadata. Backup/restore
and world transfer use explicit targets on their existing canonical instructions,
without new topic IDs or copied recovery prose.

The manual home has a nine-row **Where Inspect control works** guide, covering
the existing 20 meanings, with reachable examples and links. It explains the
forbidden cursor on exempt controls and the ordinary F1 alternative. This changes
guidance, not inspection registrations. Following user review, KRT-89's scope was
explicitly expanded to include practical interface inspection and the native
disabled-hover finding. That runtime work remains pending in KRT-89; the earlier
curate-and-guide-only boundary is superseded. The approved articles and guide
do not establish acceptance of the expanded inspection experience.

## Verification and acceptance boundaries

- Help bundle generation and strict Sphinx (`-n -W --keep-going`) passed.
- Focused bundle/search/inspection regressions: **48 passed, one skipped**,
  `artifacts/krt89/help.xml`. The skip is the existing optional packaged-executable
  probe. All six expert queries find their intended topic in the first five
  results. Distinct landing titles are asserted for evidence/chronology,
  historical editing/source and writing/links.
- Repository Ruff, mypy (**477 source files**), visual, complexity and test
  collection policies passed; no baseline was relaxed.
- [Native companion navigation](native-navigation.json) exercised all 20 task
  destinations, opening a related topic and returning Back with the reading
  position restored. The fixture author's draft text remained unchanged.
- Native Windows companion captures: **24 PNGs**, six themes at 640 × 560 and
  360 × 560 logical pixels, Qt 6.10.1, DPI 96/device ratio 1. The long recovery task
  and inspection guide represent flowing prose, steps, links and a table.
  Disabled navigation and focus remain visible. The existing capture script now
  accepts `--topic` while retaining its original default behavior.

The [recovery presentation metadata](presentation.json) and
[guide metadata](guide/presentation.json) identify the native environment and
source. The guide captures scroll to its validated anchor after layout at each
width. Examples: [dark recovery](dark_mode-360.png),
[light recovery](light_mode-360.png), [dark guide](guide/dark_mode-360.png).
The six narrow recovery palettes and representative normal/guide captures were
visually inspected; this is assisted native rendering evidence.

Automated search/anchor checks establish structural behavior, not historical
truth or human usability. No full release/package, scaling, multi-monitor or
independent workflow acceptance is claimed here; those remain KRT-91. Integrity
gate expansion remains KRT-90.

Manual scenario acceptance is still pending. The human reviewer should execute:

1. Enter two events known only to 962, order one before the other and confirm that
   reopening preserves year-only precision without an invented month/day.
2. Bind an outgoing role's end and successor's start to the same year-only event;
   inspect the shared transition without inventing independent exact dates.
3. Create a border state at a chosen date in 962; inspect before/on/after that
   transition and confirm existence dates and earlier geometry are unchanged.

Record reviewer, exact source revision, corrections and per-scenario result before
claiming manual workflow acceptance. The textual approvals above do not substitute
for these observations. A local commit was subsequently authorized; no push was
requested. KRT-89 remains In Progress for the expanded inspection scope and
outstanding manual acceptance.

## Expanded interface inspection — 2026-10-15

This implementation continues from committed curation revision
`52f66fb7ae34b93beeea9859417ce2b500483181`. The earlier sparse-coverage limits
above describe that revision, not the expanded implementation. Christian
subsequently authorized committing this batch using the passed verification and
pushing it on 2026-10-15. Delivery hashes are recorded in Linear. KRT-89 stays
In Progress for the outstanding human review and manual acceptance.

### Delivered routes and content

The finite `docs/help-inspection.json` inventory records 916 construction-site
declarations, their source symbols, canonical paragraph targets and task IDs.
These are declarations, not 916 independently accepted workflows or a count of
all runtime widget instances. They cover workspace/Explorer, Event and Entity
inspectors, writing/F11, Timeline, Map/Layers/raster tools, Connections, Longform,
Graph, AI Search, Analysis, settings, world management and transfer/recovery
dialogs. The 23 existing topic IDs remain; 26 supplemental destinations link
ordinary controls to existing canonical tasks. Original specialist meanings and
nine excerpts remain compatible.

Each new paragraph briefly states a purpose or effect. The native explanation
adds a validated task link; search indexes each paragraph at its real anchor.
The 916 generated ordinary-control paragraphs have a median of 19 words and a
maximum of 34 words, excluding the task link. The longer specialist excerpts
retain their previously approved detail.
Prose remains in `docs/user/`, with no maintained explanation strings in widgets.
Dynamic map actions use operation IDs. Default actions and overflow proxies
retain their original meaning, and form labels use field associations. Region
hit testing preserves Source-column, geometry-state and painted-time meanings.
F1 precedence remains separate from inspection registration.

The code cross-check corrected draft errors about grouping, saved layouts,
feedback buttons, read-only previews and already-saved AI settings. Timeline
group rename is explicitly described as unimplemented, matching its current
handler. No unrelated rename feature was added to make the prose true.

### Input and lifecycle

The controller resolves native pointer positions for enabled and disabled
controls, menu items and nested viewports. Targeting consumes action clicks,
including right/double clicks, wheel changes and context-menu activation during
inspection. Hovering a menu heading can reveal its submenu without triggering an
operation. Shift+F1 retains the focused target, independently of pointer location.

Qt-owned action and menu wrappers are retained until native destruction, including
exempt menu items. This fixes a full-window startup failure exposed by the broad
integration run. Semantic origins/owners remain weak and validity-checked.
Transient relation/gallery/group menus have explicit owners and deferred cleanup.
Existing modal teardown, Escape ordering and live-editor protections are retained.

Authoring Contracts 1–9 and 11 apply. This adds assistance routes without changing
creation, selection, date, writing, map Apply/Cancel or command/worker ownership.
Presentation uses existing secondary/input/selection/focus roles, neutral links
and shared supporting captions. Touched legacy literals were replaced with shared
roles or named authored-data defaults; ten obsolete visual exceptions were removed.
No visual allowance was added or enlarged. Entity temporal-save complexity falls
from 19 to 16; RelationForm construction falls from 16 to 11, with the corresponding
ceiling tightened and obsolete allowance removed.

### Bounded verification

- Native Windows Qt 6.10.1: **67 tests passed** across Help context, search,
  inspection and expanded coverage. Window-level input covers modal ownership,
  repeated open/close, disabled targets, menus, F11, incomplete dates and draft
  preservation. The test Graph child is explicitly a shared-fixture stub.
- Full-window writing-navigation integration: **25 passed** after correcting
  wrapper lifetime. These tests create the real MainWindow and exercise
  Rich/Source navigation/return with live drafts.
- Final native control/editor/gallery batch: **53 passed**, including the 14
  new coverage, factory-drift, action-owner, label and overflow regressions.
- The isolated [real Chromium probe](expansion/native-webengine.json) uses native
  Windows window-level pointer input on a real QWebEngineView child. It resolves
  `graph.exploring` without delivering the click to the local HTML document.
  It loads no world and does not establish real graph-node workflow acceptance.
- An earlier focused batch passed **171 tests / 1 skip** and exposed two unrelated
  architecture assertions: `DatabaseService.require_connection` is absent from
  the architecture API baseline; worker length is 2102 against a 2089 budget.
  Both source files and the architecture test are unchanged from HEAD. No
  architecture baseline was relaxed for this Help work.
- Repository Ruff, mypy (479 source files), inspection drift, visual and complexity
  policies and test collection were run. Strict Sphinx builds without warnings.
- Final clean `pytest -m "smoke or ci_fast"`: **2079 passed, 3 skipped**, 4459
  deselected, in 384.36 seconds. The existing Starlette/httpx deprecation warning
  remains. This is the repository's smoke/fast selection, not the full 6541-test
  release suite. The drift-check failure during an earlier in-flight menu review
  is superseded by this completed clean run; no test/review baseline was weakened.
- Final Ruff and inspection/visual/complexity checks pass. Test collection retains
  all baseline tests: 6541 collected, including 2073 ci_fast and 19 smoke tests
  (markers overlap). Strict Sphinx and repository-wide mypy pass.

The [presentation metadata](expansion/presentation.json) records 60 native
renders across all six themes at 640 and 360 pixels, 96 logical DPI / DPR 1.0:
reader/navigation, populated search, no results, an ordinary Explorer explanation
and a disabled Explorer control. All six narrow explanation palettes and
representative normal/narrow reader/search/disabled images were visually checked.
The capture CLI isolates settings in a temporary INI store. The
[source identity](expansion/source-identity.json) records canonical input and
implementation hashes, declaration/review counts and the unchanged inputs behind
the separate architecture failures.
Examples: [ordinary explanation](expansion/dark_mode-360-explanation.png),
[search/focus](expansion/cyberpunk_mode-360-search.png),
[no results](expansion/muted_light_mode-360-no-results.png),
[disabled control](expansion/light_mode-360-disabled-explorer.png),
[normal reader](expansion/light_mode-640.png).

These are assisted native renders and automated checks. They do not establish
independent human readability, all menu combinations, actual data-provider
requests, native system dialogs, scaled displays, multi-monitor behavior or the
full extracted package. Full-package/scaling/multi-monitor acceptance remains
KRT-91. The three manual scenarios above remain unexecuted.

### Content review and maintenance limits

Christian authorized drafting appropriate concise explanations based on code and
required maintenance when behavior changes. That authorizes this local draft;
the original 20 approvals do not silently approve every new paragraph. New
reference prose remains pending human review before publication. Record reviewer,
the final source identity, corrections and approval separately from automated
verification. The captured source identity describes the verified pre-commit
snapshot; subsequent commit/push authorization is recorded above and in Linear.
No release or completed human semantic/workflow acceptance is claimed here.

The drift checker validates declarations, canonical targets, topic IDs and reviewed
source fingerprints. It also flags unregistered native input factories, including
new files, unless a reasoned exemption exists. Comments/formatting do not cause
review drift. The checker never changes prose or review fingerprints. Custom
widget families, JavaScript controls and new domain dependencies still require
explicit feature review; a green structural gate is not semantic approval.

The Expert Assistance contract's deliberate scope amendment was updated in both
repository and Linear. Broader integrity consolidation remains KRT-90.
