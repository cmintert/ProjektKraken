# KRT-46 assisted baseline — 2026-10-04

This records one assisted, component-backed walkthrough of the new
[20-task catalog](../../authoring-benchmark.md), including failed and partial
tasks. It is an audit baseline, not a participant performance session. The user
will record human task videos later. No creator-performance improvement is
claimed and partial tasks are not counted as completed creator goals.

## Environment and method

* Source revision: `eb8aff5ce8501c05a3fae81aa2e1238be789f6db`, with the KRT-46
  documentation/test changes only; production Python was unchanged.
* Windows, Python 3.13.14, PySide6/Qt 6.10.1; production `main.qss` and dark
  theme; Segoe UI fonts registered explicitly for offscreen Qt.
* MainWindow 1600 × 1000. Ordinary editor crops are 871 × 569; compact crops
  331 × 569 after an approximately 360 px splitter allocation. Scrollbars,
  tabs and overflow remain part of the captured widget, not manually retouched.
* Immutable Rhine Tribunal archive, SHA-256
  `c66eb9095c7254f250021c7cb4d77d057ffef6c34236b139afa200ee9e940166`.
  Each probe extracted a fresh disposable copy and used isolated Ini QSettings
  and application data. MainWindow's worker loaded 47 entities and 20 events;
  the normal world startup/migration path was retained.
* Initial fixture playhead was 439711; later tests used the active calendar
  converter, the saved 1187 event and exact 1219 date. Initial rendering preceded
  calendar fanout; the workspace capture therefore includes fallback labels.
* Real Qt text/mouse/key events exercised local controls. Names, target choices,
  exact wiki source, object positions and some coordinator entry points were
  assisted. Save operations used the normal coordinator/command/worker path.
  Modal responses were scripted; dialog frequency and safety decisions cannot
  be inferred from those assisted responses.
* Native Windows automation was unavailable. Offscreen WebEngine and the map's
  OpenGL viewport could not paint their canvases reliably. MainWindow map
  captures establish controls/mode strips only. The separate `map-software.png`
  uses the same production MapWidget, theme and fixture image with a QWidget
  software viewport; it demonstrates spatial layout, not native GPU behavior.

## Per-task record

Every row uses assisted mode. Completion time, pauses, hesitation, creator
decisions, dialog/panel counts, backtracking, wrong turns and terminology
confusion are **not measured** in every row. The routes, mode changes and context
observations below are the observations actually available. Read these alongside
the catalog's stricter semantic success checks.

| Task | Completion / semantic evidence | Route, assistance, context and recovery |
| --- | --- | --- |
| KA-01 | Assisted: new UUID selected and Character correction saved. | New → Create Entity; scripted name. Initial Concept default observed, then explicit type change: KRT-14. |
| KA-02 | Assisted: search narrowed to one matching identity and mouse selection reopened it. | Search/Explorer selection; no duplicate created. Discovery time not measured. |
| KA-03 | Assisted: typed description survived worker save. | Writing field → Save Changes. Probe text was “A benchmark character.”, not the exact participant prompt. |
| KA-04 | Partial: saved supported WikiLink source retained. | Exact-source insertion assisted; completion discovery and follow/return were not performed end-to-end. Peek navigation has separate regression evidence. |
| KA-05 | Partial: production capture dialog inspected and data extracted; no reliable unique-connection success established. | Dialog entry/target assisted. A worker-backed extension read a stale inspector snapshot before the relation appeared; do not interpret that probe failure as a product failure. Full-dialog overload remains KRT-22. |
| KA-06 | Assisted capability check: member_of with confidence 0.7 and note persisted. | Emitted existing editor intent through worker; target/type refinement assisted. Because KA-05 was partial, this is not proof of duplicate-free refinement of its result. |
| KA-07 | Partial: Starts now emitted fixed start 433359.5; closed disposable DB contained that boundary. | Playhead input assisted. The worker extension found two member_of records after dependent steps ran with stale snapshots; combined notes/boundary preservation was not established by this extension. Focused relation round-trip tests are the semantic safeguard. |
| KA-08 | Partial: Ends at Event emitted the dynamic binding from a production event-relation dialog. | Source-event setup assisted using the 1187 session, rather than the catalog's 1201 council. Later source-event date mutation was not executed; existing temporal tests cover dynamic resolution. |
| KA-09 | Assisted: created charter through command pipeline; typed year saved. | Creation setup assisted; local date Enter and Save exercised. Year precision checked in existing date tests. |
| KA-10 | Assisted: approximate qualifier survived worker save/reopening. | Keyboard Date fields disclosure; qualification control. No invented day/month certainty. |
| KA-11 | Assisted: independent three-day duration survived save/reopening. | Event has duration and assisted value signal; duration mode entered deliberately. |
| KA-12 | Assisted: saved-event and exact-calendar coordinator navigation succeeded with selection retained. | Show world at event/Go to date entry invoked through coordinator. World Time preservation and guarded fanout separately tested. |
| KA-13 | Assisted: existing person placement arrived through worker snapshot. | Add Marker route rendered; object/normalized coordinate supplied through map coordinator. Native canvas placement discovery not measured. |
| KA-14 | Failed visible-route goal; partial drawing-mode check passed. | Draw Region entered mode; real Escape exited. Full polygon construction/revision not executed; revision entry needs right-click (KRT-48). |
| KA-15 | Partial: guided trajectory start and visible Cancel exited safely. | Selected marker and start assisted. Two dated positions, Apply and undo not executed in this walkthrough; existing session tests cover those semantics. |
| KA-16 | Failed protection goal. | Map-switch handler cancelled the active session without a decision/stash (KRT-26). Destination selection assisted; actual changed-point restoration not tested here. Source confirms the same cancellation drops the working copy. |
| KA-17 | Partial: temporal controls rendered; graph filtering tests passed. | At playhead / History to playhead / All relations visible. Native canvas/node interaction excluded because of offscreen GPU failure. |
| KA-18 | Failed visible-route goal. | Seeded Severin/1187 outline used to inspect organization. No visible labeled organize/setup route; context-menu tests establish existing signals (KRT-47). No claim of persisted Tasgillia/charter organization. |
| KA-19 | Partial depth check: event reopening retained approximate year and duration; production dialog retained supplied confidence/notes. | Advanced relation construction/reopening assisted. Full combined dynamic/fixed relation persistence relies on existing temporal tests, not the stale-snapshot extension. |
| KA-20 | Partial: supported Rich/Source round-trip and worker save retained text/link and caret. | Exact-source insertion assisted. Navigation away/return not executed as a complete task; existing dirty navigation, newer-draft and caret-refresh tests supply separate evidence. |

The walkthrough identifies ordinary-path violations and demonstrates selected
advanced capabilities without converting test success into user success. The
later videos should execute all catalog success checks, especially KA-04/08/14/
15/17/18/19/20, and retain failed attempts and facilitator intervention.

## Rendered evidence

| Capture | Conclusion supported |
| --- | --- |
| [Workspace](workspace.png) | Explorer creation/search, temporal controls and overall production layout; initial calendar fallback visible. |
| [Entity normal](entity-normal.png), [compact](entity-narrow.png) | Ordinary text/type/context controls; compact tab overflow, wrapping/truncation and writing density belong to KRT-45. |
| [Event normal](event-normal.png), [compact](event-narrow.png) | Existing date disclosure, qualification and duration opt-in; compact structured-date labels are cramped (KRT-45). Fresh collapsed defaults are verified separately by widget-event tests. |
| [Relation](relation.png) | Always-present expert options and modal configuration burden (KRT-22). |
| [Map](map.png), [draw mode](map-draw.png), [journey mode](map-journey.png) | Visible controls and local mode strips; some journey labels clip at this layout (KRT-25). Blank native canvas is an offscreen limitation. |
| [Map software viewport](map-software.png) | Production map controls with fixture background using a software viewport, 1100 × 720. |
| [Graph](graph.png) | Labeled temporal modes/filtering; not interactive canvas validation. |
| [Longform](longform.png) | Seeded outline and complete toolbar; missing labeled structural actions and icon-only Find (KRT-47). |

## Safeguards and findings

Seven new ci_fast cases use delivered widget events to protect fresh collapsed
disclosure, keyboard access, lossless advanced duration/date values, same-object
reload, clean presentation changes, local invalid Enter/Escape behavior, narrow
visible overflow action dispatch, and text-focus/inner-operation map key ownership.
Existing date-draft, overflow and trajectory tests remain intact.

Validation: initial focused suite 93 passed; temporal/wiki/raster suite 150 passed;
context/map/timeline/graph suite 200 passed;
bounded ci_fast 1,275 passed, two asset-dependent skips, 4,373 deselected. Ruff and
test policy passed; mypy passed across 425 source files. Collection baseline:
5,650 total / 1,277 ci_fast. No executable/package build was performed.

Existing owners: KRT-14 (typing), KRT-21 (capture), KRT-16 (fact semantics),
KRT-22 (relations), KRT-45 (inspectors), KRT-25 (map intent/modes), KRT-26
(unfinished map work). New grouped owners: KRT-47 (Longform actions/setup and
deliberate membership/deletion), KRT-48 (selected map feature actions). No known
violation is reclassified as an exception simply because it has an owner.
