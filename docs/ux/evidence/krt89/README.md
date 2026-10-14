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
