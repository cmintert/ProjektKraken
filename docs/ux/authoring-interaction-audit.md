# Authoring interaction audit v1 — KRT-46

Audited 2026-10-04 against source revision `eb8aff5c` and
[Contract v1](authoring-contract.md). This inventories the major authoring
capabilities, including their advanced entry points; it is not a claim that all
current surfaces already comply. Known violations remain violations when assigned
to follow-up issues. Human video measurements will be added later, starting
from new empty worlds under benchmark v1.1; the assisted fixture evidence below
remains a separate seeded audit run.

## Evidence and disposition rules

KRT-22 implementation (2026-10-06, base `7826d960`): ordinary connection capture
and refinement are inline in both inspectors; grouped boundary controls,
recognizable Notes, advanced disclosures and visible full-editor routes preserve
expert semantics. Contracts 1–10 are covered by focused acceptance and rendered
checks, including stable serialized capture/refinement replay and independent
prose/connection drafts. [Evidence and direction-reversal constraint](evidence/krt22/README.md).
The historical inventory below remains the audited baseline. Implementation is
included in the KRT-22 implementation commit; a fresh empty-world human
comparison remains pending.

KRT-45 partial human review (2026-10-05, review checkout `b2fa333b`):
[KA-01–10 video/SRT evidence](evidence/krt45/human-run-1.md) records eight
optimization groups and source-video timestamps. The 26 full-frame screenshots
were subsequently removed at the user's request because they included VS Code;
capture metadata remains available. Independent widget checks
reproduce unfocused dropdown wheel mutation (new KRT-52) and missing Linked events
playhead markers for one-event/outside-range cases (KRT-45). Relation boundary
grouping, overload and participant terminology stay in KRT-22; visible link
creation is KRT-53; deliberate normal creation remains KRT-14. Event action/commit
feedback and writing-toggle state stay in KRT-45. This run does not establish a
numeric regression of KRT-49, a parser defect, fewer measured destination changes
or complete semantic acceptance. KA-11–20 and matched comparison remain pending.
Contract v1 and the v1.2 prompts are unchanged.

KRT-52 F1 implementation (2026-10-05): shared `ScrollSafeComboBox` protects
relation boundaries/meaning/type/event choices, structured dates/qualification,
Entity/Event type and metadata choices. Unfocused closed fields pass wheel
navigation without changing values, emitting mutation signals or taking focus;
click/Tab-focused wheel editing and open-popup scrolling remain available.
[Inventory and window-delivery verification](evidence/krt45/human-run-1.md#f1-fix--krt-52-2026-10-05)
cover contracts 2/5/8/9, narrow/normal geometry and save/undo. The original review
above remains historical evidence; full KRT-45 human acceptance is still pending.

KRT-45 supporting-feature refinement (2026-10-05, based on `7f723d08`): Summary…
and Draft with AI… are quiet actions directly below the description. One
History & context heading reveals non-button Linked events (Entity only), Map
layer links and World context sections. Its caption explains the read-only
purpose. The existing writing panels open independently without generating or
committing, and preserve working inputs when hidden. The World context stable
route still reveals its embedded home or activates its independent pane.
[Refinement evidence](evidence/krt45/supporting-refinement.md) records purpose
copy, narrow/short rendering, keyboard and retention tests. Count writing-panel
openings and the shared information disclosure separately; human comparison is
still pending and Contract v1 is unchanged.

KRT-45 implementation update (2026-10-05, based on `5e7942f7`): Entity/Event
destinations are now Overview, Connections, Details and Media. Tags sit above
Fields/Sheet; World context is a read-only Overview disclosure; both supporting
views can independently split and return through the labeled inspector More
menu. The earlier inventory below remains a historical audit of `eb8aff5c`.
Current routes, every nested disclosure, contract 1–10 tracing, regressions and
rendered evidence are in [the KRT-45 mapping](evidence/krt45/README.md).
Date fields… is now Date details & uncertainty…; advanced semantics and existing
dialog exceptions remain. The user authorized implementation with a preserved
baseline. The [full human v1.2 comparison](evidence/krt45/benchmark-comparison.md)
is pending; destination fragmentation is implemented but its human acceptance
disposition remains open. No contract rule was revised.

**C** = verified compliance for the explicitly described behavior.
**V** = known violation linked to actionable work.
**E** = justified exception with the domain reason and alternative route below.
There are no unresolved unverified dispositions in this inventory. Evidence levels
are explicit: source tracing establishes wiring/ownership and absence of routes;
Qt tests establish the tested behavior; assisted offscreen rendering establishes
the displayed layout. None establishes first-time-user learnability.

Evidence: [assisted baseline](evidence/krt46/baseline.md), production MainWindow
renders with the repository stylesheet and registered Segoe UI fonts, isolated
QSettings, migrated disposable Rhine Tribunal world, and real Qt keyboard/mouse
events. Native Windows automation was unavailable. WebEngine reported GPU context
errors; graph control routes and temporal semantics have source/test evidence,
but these captures do not validate interactive graph-canvas rendering. This is a
verification-environment limitation, not a diagnosed product defect. The map's
offscreen OpenGL canvas also remained blank; a separate software-viewport render
verifies its background layout. Map control/mode claims use the MainWindow
captures and widget tests. Compact inspector labels/overflow density remain
KRT-45; clipped journey instructions/actions in this layout belong to KRT-25.

## Core action inventory

In the tables, Enter/Escape refer to the owning field or mode, not a global
command. Destructive operations must follow the guarded production mutation path.
`—` means no special gesture is required for that action.

| Surface / creator intent | Visible route and accelerators | Interaction, disclosure and state | Context / disposition / traceability |
| --- | --- | --- | --- |
| Explorer: create an entity/event/map | New… menu; empty-state Create Entity/Create Event; Ctrl+I/E/M | Name/file setup is modal; selection opens the resulting inspector. | **C** visible creation route and coherent selection; **V** entity silently starts as Concept, [KRT-14](https://linear.app/projektkraken/issue/KRT-14). `UnifiedListWidget`, `EditorCoordinator.create_entity`, KA-01. |
| Explorer: find/select/reopen | Search, item kind and sort controls; filter Set…/overflow | Single click selects and populates ordinary inspector; drag has visible spatial destinations. | **C** same identity selected, no duplicate creation; normal/narrow New route retained. `unified_list.py`, `NavigationCoordinator`, KA-02; `test_explorer_checkboxes.py`. |
| Explorer: filter/delete | Set…, Clear Filters, Delete via toolbar/visible overflow | Secondary filters disclosed; deletion goes to EditorCoordinator confirmation, with worker commands/undo. | **C** visible toolbar/overflow; `EditorCoordinator.on_item_delete_requested`, `test_overflow_toolbar.py`. |
| Capture without abandoning current writing | Unresolved WikiLink/Peek materialization exists; general capture route absent | Normal creation deliberately selects; provisional capture should preserve origin. | **V** missing general Quick Capture, [KRT-21](https://linear.app/projektkraken/issue/KRT-21). This does not invalidate deliberate normal-creation selection. `navigation_coordinator.py`, KA-04. |
| Entity: ordinary text/type/tag/media/attribute editing | Details and labeled inspector tabs; Save Changes/Discard; Add/Edit/Remove rows | Inspector handles common edits; Summary/Generate description/Timeline are disclosed; resize reflows the same fields. | **C** common editing route and collapsed extras; **V** destination/terminology fragmentation owned by [KRT-45](https://linear.app/projektkraken/issue/KRT-45). `entity_editor.py`, `EditorPresentation`, KA-03/19; `test_editor_presentation.py`. |
| Entity: correct displayed history or begin a dated description | Source banner and Start a new description at this time | Historical source is visible; explicit dated-edit choice is genuinely multi-step; fields emit snapshots/intent. | **C** source feedback and lossless source-aware editing; **E** explicit ownership choice rather than silently changing history. `EntityEditorWidget.display_temporal_state/_save_temporal`, `test_temporal_entity_edit_command.py`. |
| Relation vs scalar attribute ownership | Relations and Attributes both available | Equivalent-looking membership facts can be expressed differently without clear canonical guidance. | **V** semantic ambiguity, [KRT-16](https://linear.app/projektkraken/issue/KRT-16). `entity_editor.py`, Benchmark Log Task 1; preserve both capabilities pending research. |
| Event: date / uncertainty / duration | Text-first date; Date fields…; Time…; Event has duration; End date / duration… | Fresh date qualification/end controls collapsed; Enter validates date; invalid draft retained; Escape restores only local date. | **C** progressive disclosure and local keyboard ownership; source uncertainty and duration remain distinct. `CompactDateWidget`, `TemporalRangeWidget`, KA-09–11; new and existing `test_editor_presentation.py`, `test_temporal_authoring.py`. |
| Event: source evidence / chronology | Date evidence… and Chronology… | Advanced, multi-record/evidence configuration uses dialogs; count/feedback exposes existing data. | **E** dialogs justified by independent sources/order constraints; no need to open them for a basic date. `event_editor.py`, `test_temporal_authoring.py`, `test_temporal_precision_roundtrip.py`. |
| Event: participants, locations, connections | Relations tab Add/Edit/Remove plus double-click Edit; corresponding drop targets | Single click selects relation; double-click edits; drag/drop relates objects; Shift accelerates type choice. | **C** visible typed relation routes; **V** editing is overloaded modal configuration, [KRT-22](https://linear.app/projektkraken/issue/KRT-22). `event_editor.py`, `relation_dialog.py`, KA-05–08. |
| Relation: capture/refine a connection | Add Relation / Edit; expert full dialog | Target/type plus weight/confidence/notes/timing visible together; no primary loose-capture/refinement sequence. | **V** disclosure, creator language and ordinary-edit modality, [KRT-22](https://linear.app/projektkraken/issue/KRT-22). [Rendered dialog](evidence/krt46/relation.png); `RelationEditDialog`; preserve serialized dynamic/fixed/unknown semantics. |
| Relation: begin/end at viewed date or event | Starts now / Ends now, formatted Now preview; source-event radio choices and boundary controls | Fixed playhead snapshots and dynamic event binding are distinct; valid target required; modal OK/Cancel. | **C** existing expert timing capability, **V** ordinary-path complexity stays KRT-22. KA-07/08/19; `test_relation_dialog.py`, `test_temporal_authoring.py`. |
| Timeline: browse dates/select events | Ruler/playhead, labeled Go to date…, Return to Current Time, playback controls | Scrub changes viewed date; event selection selects inspector context; drag changes spatial temporal position. | **C** visible exact-date navigation and selection; semantic precision retained. `timeline_view.py`, `event_item.py`, `TimeCoordinator`; `test_timeline_interaction.py`, `test_timeline_calendar_boundaries.py`. |
| Event → view the world at its saved date | Show world at this event | Selection retained; World Time unchanged; uses guarded playhead navigation and standard fanout. | **C**, KA-12; `TimeCoordinator.show_world_at_event`, `test_time_coordinator.py`. Uses saved semantic anchor, not a pending draft date. |
| Timeline: grouped structure/navigation | Grouping/configuration routes and visible band headings | Group headers can collapse/expand structures; this gesture manages presentation rather than editing a world object. | **E** group interaction is a structural presentation convention; configuration still visibly reachable. `group_band_item.py`, `test_timeline_grouping_workflow.py`; no new default gesture imposed. |
| Map: browse/place/draw | Map selector, Add Marker, Draw Path, Draw Region, layer tree, Fit to View | Selected mode indicator and Confirm/Cancel; Enter confirms eligible local operation; Escape exits innermost suboperation/browse. | **C** visible creation and local cancellation, KA-13/14; **V** terminology/control density remains research [KRT-25](https://linear.app/projektkraken/issue/KRT-25). `MapWidget.active_map_session_mode`, `MapGraphicsView`, `test_map_widget.py`, `test_map_graphics_view.py`. |
| Map: revise vector geometry/style/states/validity | Context menu Edit Vertices / Edit Style / Manage Geometry States / Temporal Validity; geometry strip visible only after entry | Drag handles are meaningful once in edit mode; visible cancellation exists, but entry lacks a labeled route for the full capability set. | **V**, [KRT-48](https://linear.app/projektkraken/issue/KRT-48). `map/interaction_handler.py`, `MapLayerPanel`, `FeatureGeometryCoordinator`; KA-14. |
| Map: marker appearance/size/validity | Context-menu appearance/size/validity actions; layer selection/deletion controls | Selection alone does not reveal a labeled actions menu. | **V**, KRT-48; `InteractionHandler.show_marker_context_menu`; preserve icon library lifecycle and expert accelerators. |
| Map: journey authoring | Edit Trajectory, Add Location, date modes, Apply/Cancel, speed preview controls | Working copy, explicit apply; Escape cancels date/speed suboperation before trajectory; Enter leaves active text input alone. | **C** supported local workflow and keyboard ownership, KA-15; `TrajectoryEditCoordinator`, new delivered-event tests in `test_trajectory_edit_shortcuts.py`; `test_trajectory_edit_session.py`. |
| Map: switch context while editing | Map selector / parent navigation | `TrajectoryEditCoordinator.on_map_selected` cancels a session when the map differs; no decision/stash. | **V** meaningful working copy lost, [KRT-26](https://linear.app/projektkraken/issue/KRT-26), KA-16. Do not bless this path with a passing contract test. |
| Map: raster editing / time-specific state / sampling | Layer paint panel, Edit base/Edit this state/Create Editable State, tools/palette/stats; advanced paint disclosure | Contextual controls; visible edit target; B/F/G/I and held Space accelerate tools/panning. | **C** source-verified labeled tool routes, **E** held Space panning is an accelerator alongside normal navigation; mode-language assessment remains KRT-25. `MapLayerPanel`, `MapGraphicsView`; `test_map_graphics_view.py`, `test_raster_editing.py`. |
| Graph: inspect/filter temporal connections | Search, tag/type filters, Refresh, visible overflow; At playhead/History to playhead/All relations; Show possible relations | Temporal mode visible, uncertain-edge counts explicit; advanced filters in dialog. | **C** routes and temporal semantics, KA-17; `GraphWidget`, `GraphFilterBar`, `test_temporal_authoring.py`, `test_graph_widgets.py`. Canvas/native GPU rendering excluded from this evidence claim. |
| Graph: select a node / pan / drag | Visible graph node; search is the alternative locating route | Click selects and synchronizes inspector; dragging rearranges visual layout; no automatic world mutation. | **E** click-to-inspector follows ordinary selection, not a modal edit command; do not invent a redundant double-click operation. `GraphBuilder._inject_interaction_js`, `GraphWidget._on_graph_node_clicked`, navigation guard. |
| Longform: assemble/nest/reorder | Outline drag; context menu Move Up/Down, Promote/Demote; Ctrl+[ / Ctrl+] | Structural drag is meaningful; labeled document editing entry point missing, empty fixture has no self-teaching add route. | **V**, [KRT-47](https://linear.app/projektkraken/issue/KRT-47), KA-18. Full `longform/editor.py` toolbar and outline traced; `test_longform_outline_context_menu.py`; rendered seeded outline. |
| Longform: remove membership vs delete world content | Delete Item in context menu | Signal is routed directly to DeleteEntityCommand/DeleteEventCommand without confirmation; user guide claims non-destructive removal. | **V** wording and destructive guard, KRT-47. `LongformOutlineWidget._delete_selected` → `LongformManager.delete_longform_item`; full connection trace in `ConnectionManager.connect_longform_editor`. No destructive probe was needed. |
| Longform: select content / find / export | Outline/card/title links; toolbar Find icon, Export to Markdown/Vault; filtering | Content selection navigates to underlying ordinary inspector; publication has separate local/LAN actions. | **C** existing content/navigation/export routes; **E** linked titles navigate as hyperlinks; **V** discoverability of icon-only Find and document setup included in KRT-47. `test_longform_card_selection.py`, `test_longform_search.py`. |
| Embedded wiki: write, link, save, Rich/Source, focus writing | Writing field, formatting toolbar, MD/HTML toggle, Focus writing; completion/Peek | Enter inserts text when appropriate; mode switches preserve supported source; save must retain caret and newer drafts. Unsupported rich syntax deliberately uses Source. | **C** supported round-trip/save protections; **E** Source fallback avoids lossy representation; **V** creator-facing mode labels/destination clarity in KRT-45. `WikiTextEdit`, `ResizableWikiTextEditField`; KA-04/20, `test_wiki_text_edit.py`, `test_wiki_link_refresh.py`, `test_wikilinking_navigation.py`. |

## Justified exceptions register

* **E-01 — Selection populates an inspector.** Explorer, graph nodes and Longform
  content are object selectors. Single click may display the ordinary inspector
  while preserving selection and applying navigation guards. It must not execute
  an unrelated mutation or open modal configuration. Double-click remains edit
  for relation rows, layer naming and suitable object surfaces.
* **E-02 — Structured date fallback.** Without an active calendar, text-first date
  parsing cannot be offered honestly. Structured fields and explanatory feedback
  remain visible; `test_no_calendar_uses_structured_entry` protects the fallback.
* **E-03 — Text and nested operations own keys.** Multiline Enter inserts a line;
  local date Enter validates; Escape cancels the inner draft/speed/date operation
  before its containing map session. Global map apply must not intercept text
  input. Delivered-event tests cover this boundary.
* **E-04 — Advanced multi-record dialogs.** Chronology, independent source-date
  evidence, palette/configuration, and deliberate historical ownership choices
  may be modal. Their ordinary entry routes remain visible and their data must
  round-trip. This exception does **not** justify the overloaded relation dialog.
* **E-05 — Structural presentation/navigation.** Group headers may collapse a
  presentation structure; hyperlink titles navigate; held-Space map panning
  accelerates an otherwise reachable operation. These conventions have source/
  test evidence above and do not unlock hidden domain capability.

## Follow-up ownership and completion

KRT-22, KRT-45, KRT-26, KRT-25, KRT-14, KRT-21 and KRT-16 retain their existing
responsibilities. KRT-47 groups Longform action/membership/deletion clarity;
KRT-48 groups selected map object actions. Findings are evidence, not a second
backlog. No new global gesture router, worker slot, database API or redesign is
introduced by KRT-46.

Regression coverage protects fresh disclosure, lossless advanced values, clean
presentation-only state, narrow overflow access, date commit/cancel, and focused
text/map operation ownership. Known violations have reproduction evidence and
owners, not tests that normalize the violation.

This audit closes the design-authority/baseline milestone after its documentation
and tests are verified and committed. The linked issues remain open. Later
participant videos must measure wrong turns, terminology confusion and advanced
task success before reporting user improvement or full surface compliance.
