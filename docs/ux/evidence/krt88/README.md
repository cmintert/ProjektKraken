# KRT-88 offline search and control inspection evidence

Verification date: 2026-10-13. Local commit delivery: 2026-10-14, reusing the
passed checks below. The delivery hash is recorded in KRT-88, which remains
In Progress pending human prose approval.
This extends KRT-87 under the [Expert Assistance contract](../../expert-assistance-contract.md),
authoring Contracts 1–9 and 11, and the shared visual vocabulary. Full package,
display/text scaling, multi-monitor and independent human acceptance remain KRT-91.

## Delivered behavior

Help Search and local Ctrl+F search validated canonical sections as the user types
with a 200 ms debounce. Unicode-normalized, case-folded prefix matching ranks
meaningful coverage, title phrase, title matches and body matches; numeric dates
are optional boosts. Destinations are deduplicated, ties are deterministic, results
are capped at 50 and plain-text snippets at 180 characters. Enter flushes pending
typing before activation. Query/results and selected destination survive revealing
search again; search itself creates no Help navigation entries. Empty/no-result
states and invalid-bundle recovery are explicit. No query is logged or persisted.

The 20 approved control meanings use nine shared canonical excerpt targets.
Qt's native Shift+F1 receives fresh validated text without a competing shortcut;
Help → Inspect control enters native pointer inspection. Labels, composite
editors, geometry items, Source cells and painted time marks have explicit semantic
registrations; bindings do not infer meaning from displayed wording or select an
item to inspect it. Exempt and disabled controls do not activate.

Explanation links use the existing confined Help coordinator. Native popups are
tracked through Qt's public active-popup API with weak snapshots and ownership
tokens, because PySide can collect a wrapper while the C++ object is still alive.
Native QObject properties retain registrations for C++-owned labels/viewports;
shutdown clears only this registry's metadata. No world/worker dependency is added.

Popup keys consume the complete modifier chord before dismissal. A plain-Qt
Windows probe demonstrated that a synthetic Ctrl+Z chord can otherwise outlive
QWhatsThis's self-deleting popup. The guard now passes native window-level
Ctrl+Z, creation, Enter, Delete and Escape checks without world or map actions.
Inspection owns Escape before draft or F11 handling and preserves unfinished dates.
Modal completion and outer-owner deletion dismiss local inspection before teardown.

The Entity destination dialog was extracted into a GUI-only helper to attach
explicit semantic metadata to its transient buttons. Baseline, dated, cancel and
hidden-baseline confirmation outcomes are retained. Reviewed allowance
`c901-b90fc28385bc` strictly improved from 23 to 19 and its ceiling decreased to 19.
No new complexity allowance or visual exception was introduced.

## Verification

- Focused Help/search/inspection/bundle/date/dependency suite: **113 passed,
  one skipped**, `artifacts/krt88/focused.xml`. The skip is the existing optional
  packaged executable probe.
- Native Windows search/inspection plus existing Help scenarios: **50 passed**,
  `artifacts/krt88/native-help.xml`. This is automated native verification, not
  human acceptance.
- Tests cover all 20 production meanings and nine nonempty generated excerpts,
  the three expert queries in the first five results, Unicode/prefix matches,
  debounce, Enter, result retention, local undo/Escape, disabled/exempt controls,
  pointer regions without selection, wrapper collection, unavailable excerpts,
  unfinished dates, background-map keys and F11 writing.
- Existing Help regressions compare live Rich/Source documents, caret/selection,
  drafts, map working copies, playhead, modal ownership and navigation/history.
- Ruff, repository-wide mypy, dependency direction, visual, complexity and
  test-collection policy checks and Sphinx are used for the delivery batch.
  No full ci_fast/release gate or extracted executable acceptance is claimed.

## Native presentation

The [presentation metadata](presentation.json) records version/source identity,
Qt, native platform, DPI and natural control widths. All six themes have captures
at 640 × 560 and 360 × 560 logical client pixels for the reader, populated search,
no results and a real native explanation. Back/Forward disabled states, result
selection, query focus and complete wrapping action labels are represented.
Native popups size against the available screen independently of companion width.

Search uses shared input/selection/focus roles; explanatory content and links use
ordinary neutral foreground and link roles. Native explanation palettes use the
same surface/text roles. The search region uses its natural wrapped height.

Examples: [dark search](dark_mode-360-search.png),
[dark explanation](dark_mode-360-explanation.png),
[muted-light no results](muted_light_mode-360-no-results.png).

```powershell
python -m scripts.build_help
$env:QT_QPA_PLATFORM = "windows"
python -m scripts.capture_help_evidence --output docs/ux/evidence/krt88 --search-inspection
python -m pytest tests/unit/test_help_search_inspection.py tests/unit/test_help_coordinator.py -q
```

## Canonical excerpt review — pending human approval

No new reference prose has been published remotely. Reviewer, review date and
accepted source revision remain **pending**. Review the nine blocks below against
their code behavior before publishing; record corrections and approval in KRT-88.
KRT-89 retains broader manual semantic curation.

| Topic / explicit excerpt target | Canonical source | Code behavior to review |
| --- | --- | --- |
| `date.precision` / `help-control-date-precision` | {ref}`Dates <help-control-date-precision>` | CompactDateWidget components/qualification/limits; parser precision vs occurrence bounds |
| `event.timing` / `help-control-event-timing` | {ref}`Event timing <help-control-event-timing>` | TemporalRangeWidget lock modes and duration presence; validation vs save acknowledgement |
| `entity.historical-editing` / `help-control-entity-historical-editing` | {ref}`Historical editing <help-control-entity-historical-editing>` | Entity baseline/dated destination helper and existing dated-event choice |
| `entity.value-source` / `help-control-entity-value-source` | {ref}`Source <help-control-entity-value-source>` | Description Source and attribute source labels; sourced correction vs new dated change |
| `relations.create` / `help-control-relations-create` | {ref}`Direction <help-control-relations-create>` | RelationForm direction/reverse choice; RelationAuthoring drop subject/target |
| `relations.timing` / `help-control-relations-timing` | {ref}`Relation timing <help-control-relations-timing>` | Meaning, open/unknown/manual/event boundaries, exclusive end and shared event identity |
| `map.historical-geometry` / `help-control-map-historical-geometry` | {ref}`Geometry <help-control-map-historical-geometry>` | Base/dates in FeatureGeometryStatesDialog and geometry coordinator; no visibility-date mutation |
| `map.visibility` / `help-control-map-visibility` | {ref}`Existence <help-control-map-visibility>` | TemporalValidityDialog and temporal-window presence; independent geometry |
| `timeline.viewing` / `help-control-timeline-viewing` | {ref}`Time identities <help-control-timeline-viewing>` | Viewed playhead vs World current time; deliberate Set/Return Current Time actions |

## Existing unrelated failures

A broader Entity editor run returned 54 passed and two failures:
`test_add_relation_flow` and `test_edit_relation_flow`. Both relation-dialog
signal timeouts reproduce with the untouched HEAD Entity editor loaded in memory.
Their mock relation payloads remain outside this Help batch; no baseline was
relaxed or unrelated relation behavior changed. The destination helper's focused
choice/confirmation tests pass. Earlier KRT-87 reports retain their separate
pre-existing Focus-writing and architectural-boundary limitations.

The local commit was authorized without rerunning passed tests. No push was
authorized. Human prose approval and KRT-91 acceptance are distinct from
automated structural/presentation evidence.
