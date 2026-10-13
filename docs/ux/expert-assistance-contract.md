# Expert Assistance contract v1 — KRT-85

- **Version:** 1.0
- **Decision date:** 2026-10-13
- **Issue:** [KRT-85](https://linear.app/projektkraken/issue/KRT-85/specify-expert-assistance-contract-topic-registry-and-context)

**Status:** Approved implementation plan; design documentation only. Runtime
verification and human documentation sign-off remain downstream requirements.
**Repository contract:** `docs/ux/expert-assistance-contract.md`.

**Linear review copy:** [Expert Assistance contract v1](https://linear.app/projektkraken/document/krt-85-expert-assistance-contract-v1-d33e593af7c3).

## Purpose and boundaries

Help answers a question about the software at the current task without changing
the creator's work. The first pass is finite: 20 substantive topics, three utility
routes and 20 semantic control explanations. No fifth mandatory workspace zone.

The approved preferences are task-led walkthroughs, followed by consequences,
examples and related concepts, and F1 moving keyboard focus into Help.
**Return to work** restores the originating control when it remains valid.

Help explains software semantics. It does not query world data, infer why a
particular entity has a particular value, or provide actual event/value provenance.
That is future **State Explanation**. Explaining how the inspector's Source label
works is in scope; diagnosing a selected entity's source is not.

No State Explanation, tutorial overlays, AI chatbot or manual database is included.
This document specifies future behavior; it does not announce working Help.
Task/concept/control prose remains in `docs/user/`, subject to human review.
No AI-generated unsupervised reference prose may be published.

## Existing implementation and evidence

The source audit for the approved plan found:

| Surface | Current behavior | Integration consequence |
| --- | --- | --- |
| `UIManager.create_help_menu` | Keyboard Shortcuts and About, both modal dialogs | Add visible Help routes through delegation, retaining these actions |
| `ShortcutManager` | Creation, formatting, navigation and map metadata; no explicit Help binding | Add Help metadata without competing dispatch paths |
| `GlobalShortcutFilter` | Application-wide undo/redo, creation and trajectory Escape/Enter/Delete handling | Exclude Help-owned input; do not make this filter the Help feature owner |
| `FocusWritingController` | F11 window shortcut; application filter for Escape and outside navigation | Help focus/inspection must preserve F11 and keep Escape local |
| Workspace | Four zones; panels can change placement | Determine semantic owner independently of zone and current QObject parent |
| Nested writing/date/dialog controls | No explicit F1 binding found in the audited production Python | Check Qt's default handling, shortcut ambiguity and local keyboard ownership |
| Canonical manual | 12 Markdown pages, mostly task-oriented; generated heading anchors | Use explicit targets, without a second editable prose repository |
| Sphinx and Windows package | MyST 4.0.1/Sphinx 8.2.3; no packaged manual assets | Build a separate renderer-compatible artifact at build time |

Existing Ctrl+I metadata serves both creation and italic formatting. That is
existing shortcut debt, not an F1 conflict to repair in KRT-85. New Help wiring
must not worsen it. F1, Shift+F1 and F11 are distinct inputs; Help must not consume
ordinary text/edit shortcuts outside its ownership.

The research experiment used Qt 6.10.1, `QT_QPA_PLATFORM=offscreen`, an
application-modal QDialog, and a non-modal companion with a QLineEdit.
Window-level `QTest.keyClick(companion.windowHandle(), Qt.Key.Key_H)` left the
main-window-owned field empty and inserted `h` into the dialog-owned field.
Direct widget-level test events did not expose this blocking and are insufficient
evidence. This establishes an ownership requirement for the design, not native
Windows acceptance. KRT-91 must verify native modal and multi-monitor behavior.

## Help levels and context resolution

| Level | Content and destination |
| --- | --- |
| Control | Concise reviewed explanation, linked to its task; longer than a tooltip |
| Task | Purpose, prerequisites, short procedure, consequences and example |
| Concept | Deeper semantics linked from tasks; may share canonical sections |

Include what an action does not change where the distinction matters. Omit
irrelevant sections rather than imposing empty templates. Keep independent
representations explicit: attributes, relations and mentions do not automatically
synchronize merely because their wording resembles one another.

Resolve context in this exact order:

1. Nearest explicitly registered control or control-group topic.
2. Active operation/tool belonging to the requesting surface.
3. Containing dialog topic.
4. Owning panel topic.
5. Searchable manual home (`manual.home`).

Walk nested editors, viewports and composite controls up to the containing dialog
or panel boundary. A panel default is a separate registration, never a
control-group topic that wins before an active tool. The active operation
provider must belong to that request's surface: a background map edit cannot
override a relation or chronology dialog, Longform or another inspector.

Register the semantic owner separately from QObject ancestry. Moving the live
writing widget into F11 presentation does not change its Event/Entity ownership.
Menus capture the last valid authoring origin before menu activation. Without
a valid origin use manual home; do not guess from a background selection.

Unknown IDs continue through the resolution chain. Unavailable mapped content
shows a readable explanation and an available parent/manual route. A missing,
invalid or version-mismatched bundle produces an accessible local error with
the regeneration/reinstall route, rather than presenting stale reference text,
opening a browser, changing world state or showing a blank window.

### Ownership interfaces

These are design contracts for KRT-86–88, not new runtime APIs in KRT-85:

- **Widget registration:** associate a control/group with a semantic topic ID and
  optional control-excerpt ID. Panel/dialog defaults have distinct registrations.
  Widgets render snapshots and emit Help intent; they do not load services or
  maintain explanation strings.
- **Operation provider:** a narrow read-only callback returns the owning
  surface's current topic ID or no active operation. It must not apply/cancel
  edits or inspect the database.
- **Help coordinator:** owns invocation, origin/context capture, scoped
  resolution and viewer lifecycle. Dependencies are the registry, operation
  providers, bundle reader and viewer; do not pass MainWindow as a feature API.
- **Bundle service:** resolves IDs and loads local generated content/metadata.
  It has no database, command executor, AI, telemetry or network dependency.
- **Composition:** UIManager/MainWindow delegate menu construction and bootstrap
  to the Help component. Do not add feature responsibilities to MainWindow,
  ConnectionManager, DatabaseWorker or DatabaseService.

Origins are GUI-local weak/validity-checked references plus semantic ownership,
not live references crossing worker boundaries. No new worker slot is needed.
Registrations and operation providers are removed with their owning component.

### Required surface defaults

| Requesting surface | Default |
| --- | --- |
| Explorer, Event inspector | `authoring.create`, `authoring.details`, respectively |
| Entity inspector | `entity.historical-editing` |
| Nested writing view, including F11 | `writing.edit`; explicit Focus control uses `writing.focus` |
| Timeline and Go to date dialog | `timeline.viewing` |
| Map canvas and Layers | `map.features` |
| Active geometry / trajectory operation | `map.historical-geometry` / `map.trajectories` |
| Relations panel / relation dialog | `relations.create` |
| Relation timing controls / temporal dialog | `relations.timing` |
| Date evidence / chronology dialog | `date.evidence` / `event.chronology` |
| Longform | `longform.recovery` |
| Other panels/dialogs | Canonical manual page where available, otherwise `manual.home` |

Unregistered date controls inside a chronology dialog use the dialog default,
not an unrelated inspector/map topic. Registered date controls may intentionally
resolve to `date.precision` before the chronology fallback.

## Companion viewer and keyboard ownership

Use one reusable, resizable, read-only non-modal companion containing
QTextBrowser. It is outside the workspace zones and can move to a separate
monitor. Its visible controls are **Back**, **Forward**, **Manual**, **Search**,
**Refresh context** and **Return to work**. The Help menu exposes **Help for
current task**, **User manual** and **Inspect control**, retaining shortcuts/About.

Capture the origin before activating Help. F1 focuses the topic reader; search
activation focuses the search field. Tab order, accessible names, selectable
content and keyboard-operable links provide a complete reading path.

Context changes only on explicit F1 invocation from an authoring surface or
**Refresh context**. Do not chase focus changes. Refresh uses the last valid
authoring origin, excluding the Help window itself. F1 inside Help keeps the
current topic and window; it does not reset navigation or create another viewer.

Back/Forward affect Help history only. Repeated requests for the same topic do
not add redundant history entries. Return to work hides the companion and
restores the current valid origin. Closing Help has the same focus-return
behavior. If the origin has disappeared, focus its surviving visible dialog/panel;
otherwise leave the current safe application focus. Never reopen an object,
navigate to an old selection or replay a stale cursor snapshot over newer work.

While a modal dialog owns the request, make the companion a non-modal top-level
child of that dialog so it can receive input. Safely transfer ownership before
the dialog destroys its children; retain Help navigation and geometry across
transfer. A later destruction callback alone is too late. Do not change dialog
modality, call accept/reject, or weaken its draft protection to make Help usable.

Bind QKeySequence.HelpContents with Windows F1 coverage and one dispatcher for
application-owned authoring windows/dialogs. Prevent overlapping actions or
shortcut ambiguity. Do not intercept F1 in another application or native OS dialog.

Keep native focused-control Shift+F1 behavior. **Inspect control** enters Qt
What's This mode for pointer targeting. Do not add a competing Shift+F1 shortcut.
Control snippets are generated from canonical excerpt targets; tooltips stay short.
Expose the corresponding explanation through keyboard-accessible Help topics
even for a non-focusable label.

The targeting click is inspection only, not selection/tool activation. Inspecting
an exempt control does not activate it or invent an explanation. Escape leaves
inspection before reaching the containing draft/mode. A control explanation link
opens its task in the companion through the same coordinator.

Help-owned input and inspection must bypass global creation, world undo/redo,
trajectory keys and Focus writing Escape handling. In Help, Ctrl+F opens Help
search; editing search text affects only that field. Enter operates its local
control/link/result; Escape closes inspection/local search first, then returns
from Help. It never applies a trajectory, cancels a date draft, exits F11 or
changes world undo history.

### State invariant

Opening, navigating, searching, inspecting, refreshing and closing Help must not
alter selection, playhead or world time, edit mode, saved/dirty state, authored
content, world navigation history or undo/redo history. Help must neither commit
nor cancel pending operations.

Preserve text caret/selection/scroll, live writing document, map working copy,
dialog fields and workspace placement. Preserve current work directly rather
than serializing and rehydrating editors. Asynchronous saves initiated before
Help can still complete normally; distinguish their independent acknowledgements
from Help-caused mutations when comparing state.

## Topic registry and offline rendering

Use stable dotted IDs, independent of widget names, UI labels and heading text.
IDs are never reused for a different meaning. Renaming a heading keeps its explicit
MyST target; moving a topic changes the manifest source, not its ID. Renaming an
ID requires a reviewed compatibility alias, not silent replacement.

The version-1 manifest has `schema_version` and a topic list. Each topic records
`id`, `source` (relative to `docs/user/`), `target` (explicit MyST target),
`level` (`control`, `task` or `concept`), `related_ids`, and optional
`control_excerpt_target`. Control registrations may share a task and excerpt.
Supporting canonical links, including recovery links, remain in source prose;
they do not create an additional maintained content field.

Example specification; this target is planned, not an existing user-doc anchor:

```json
{
  "schema_version": 1,
  "topics": [
    {
      "id": "map.historical-geometry",
      "source": "maps.md",
      "target": "help-map-historical-geometry",
      "level": "task",
      "related_ids": ["map.visibility", "timeline.viewing"]
    }
  ]
}
```

Place `(help-map-historical-geometry)=` before the canonical section. Use the
same `help-` plus ID-with-dots-replaced-by-hyphens rule for all inventory targets.
The generated manifest records actual resolved HTML fragments; never guess them
from display titles or assume that MyST versions emit identical fragment markup.
Displayed titles and all prose derive from the canonical documents.

KRT-86 creates the machine-readable manifest, builder and bundle; KRT-89 curates
sections, explicit targets and control excerpts. Coordinate these follow-ups so
a release never packages unresolved planned targets.

Build from resolved MyST/Sphinx documents into HTML supported by QTextBrowser.
Do not feed raw MyST Markdown or the Furo website shell to the viewer. Preserve
headings, lists, tables, code, Unicode/custom calendars, anchors, cross-links and
bundled images. Unsupported constructs fail generation with source/location
diagnostics rather than silently losing meaning.

Generate browseable manual pages and offline search text/index from the same
resolved content. Search covers the packaged manual, with title/task/concept
matches, snippets, empty/no-result states and keyboard-accessible results.
No runtime Sphinx, Qt WebEngine, external browser, separate editable Help prose,
network fetch or manual database is required.

Bundle metadata includes manifest schema, exact app version, source revision
(including whether the build source is dirty) and deterministic content hashes.
Include assets explicitly in ProjektKraken.spec. Resolve release resources from
the installed bundle and development resources from a repository-relative
generated location, never the process working directory. Missing development
content explains the documented build command; opening Help does not build it.

Internal navigation/resources stay inside the bundle, including path resolution
and fragments. Disable automatic external-link opening and remote resources.
External references remain identifiable without an automatic browser launch.
The existing Sphinx website remains functional and independently publishable.

## Finite first-pass inventory

The table freezes 20 substantive task topics. The source column links to current
canonical material; explicit `help-...` targets are planned for KRT-86/89 and are
not claimed to exist yet. Concept explanations share these reviewed sections.

| Stable ID | Task | Current canonical material |
| --- | --- | --- |
| `authoring.create` | Create an Event or Entity | [Create an event or entity](../user/events-entities-relations.md#create-an-event-or-entity) |
| `authoring.details` | Edit and save details | [Add details](../user/events-entities-relations.md#add-details) |
| `writing.edit` | Write, format and use Rich/Source views | [Wiki editor Markdown and links](../user/wiki-editor-markdown.md) |
| `writing.links` | Link, peek and return to writing | [Wiki editor Markdown and links](../user/wiki-editor-markdown.md) |
| `writing.focus` | Enter and leave Focus writing | [Focus on writing](../user/events-entities-relations.md#focus-on-writing) |
| `event.timing` | Set a date and duration | [Set an event date or duration](../user/events-entities-relations.md#set-an-event-date-or-duration) |
| `date.precision` | Enter incomplete or qualified dates | [Dates with incomplete information](../user/timeline-and-calendars.md#dates-with-incomplete-information) |
| `date.evidence` | Record conflicting date sources | [Record sources and ordering](../user/timeline-and-calendars.md#record-sources-and-ordering) |
| `event.chronology` | Record ordering and shared transitions | [Record sources and ordering](../user/timeline-and-calendars.md#record-sources-and-ordering) |
| `timeline.viewing` | Explore time without changing world time | [Use the timeline](../user/timeline-and-calendars.md#use-the-timeline) |
| `entity.historical-editing` | Edit baseline or dated state | [View and correct an entity at another time](../user/events-entities-relations.md#view-and-correct-an-entity-at-another-time) |
| `entity.value-source` | Identify which source a correction changes | [View and correct an entity at another time](../user/events-entities-relations.md#view-and-correct-an-entity-at-another-time) |
| `relations.create` | Create a directed connection | [Create relations](../user/events-entities-relations.md#create-relations) |
| `relations.timing` | Set relation meaning and historical boundaries | [Historical validity and uncertainty](../user/events-entities-relations.md#historical-validity-and-uncertainty) |
| `authoring.representations` | Choose an attribute, relation or mention | [Attributes, relations, and mentions](../user/events-entities-relations.md#attributes-relations-and-mentions) |
| `map.features` | Place markers and create features | [Add markers and features](../user/maps.md#add-markers-and-features) |
| `map.historical-geometry` | Change a border/path at a date | [Dated path and region geometry](../user/maps.md#dated-path-and-region-geometry) |
| `map.visibility` | Set existence dates independently of geometry | [Temporal visibility](../user/maps.md#temporal-visibility) |
| `map.trajectories` | Create and edit a journey | [Create or edit a trajectory](../user/maps.md#create-or-edit-a-trajectory) |
| `longform.recovery` | Organize/export Longform and find backup recovery | [Longform](../user/longform.md), with a canonical link to [Back Up and Restore](../user/import-export-and-backups.md#back-up-and-restore) |

`longform.recovery` has `longform.md` as its primary manifest source. Its task
includes a related canonical recovery link; do not copy backup prose into
Longform or split this approved topic silently.

Utility IDs are `manual.home` → `index.md`, `manual.shortcuts` →
`keyboard-shortcuts.md`, and `manual.troubleshooting` → `troubleshooting.md`.
Each receives its own explicit target by the same naming rule. These do not
increase the substantive-topic count.

### Control inspection inventory

Freeze these 20 semantic registrations. An explanation can serve equivalent
instances across dialogs/editors; the count is semantic, not widget-instance count.

| Control meaning | Task topic |
| --- | --- |
| Date qualification | `date.precision` |
| Month precision | `date.precision` |
| Day precision | `date.precision` |
| Possible occurrence limits | `date.precision` |
| Duration | `event.timing` |
| Keep duration / keep end date | `event.timing` |
| Entity baseline destination | `entity.historical-editing` |
| At this time destination | `entity.historical-editing` |
| Value Source | `entity.value-source` |
| Relation direction | `relations.create` |
| Relation Meaning | `relations.timing` |
| Relation start boundary | `relations.timing` |
| Relation end boundary | `relations.timing` |
| Shared-event binding | `relations.timing` |
| Dated geometry state | `map.historical-geometry` |
| Base Geometry | `map.historical-geometry` |
| Exists from | `map.visibility` |
| Exists until | `map.visibility` |
| Viewing time | `timeline.viewing` |
| World time | `timeline.viewing` |

Ordinary text fields, standard buttons, decorative widgets and every formatting
action do not require individual topics. They inherit a reviewed task/panel
fallback. Other panels/dialogs can route to existing manual pages or manual home;
they are exempt from new substantive topics/control snippets, not from safe Help
invocation and fallback. Expansion requires a deliberate inventory revision or
a separate backlog issue, not automatic per-widget coverage.

## Scenario review and verification boundaries

These five scenarios are reviewed at the design level against the resolution
order, ownership and preservation rules. They define executable acceptance for
KRT-87–91; they are not claims of implemented or human-tested Help.

| Scenario | Expected topic and behavior | State to compare |
| --- | --- | --- |
| Nested Rich/Source writing with selection and an unsaved draft | Explicit Link control → `writing.links`; otherwise `writing.edit`; viewport traversal stays within its editor | Live document identity, text, dirty flag, caret, selection, scroll, inspector selection and undo |
| Active map working copy | Unregistered canvas → geometry or trajectory operation topic before `map.features`; inspecting a mapped control wins first | Working-copy vertices/keyframes, active tool, selection, playhead, dirty state and undo |
| Unsaved relation dialog with a background map operation | Direction control → `relations.create`; timing control → `relations.timing`; unmapped control → dialog default; companion owned by dialog | All unsaved fields, dialog result, background map draft and undo; no accept/reject or draft prompt |
| F11 writing, Help Escape and Return to work | Writing stays owned by Event/Entity; Help Escape remains local and Return restores origin without toggling F11 | F11 active state, live document, cursor/scroll, panel layout, draft and undo |
| Date/chronology dialog with incomplete input | Registered precision control → `date.precision`; unmapped chronology row → `event.chronology`; no background-tool override | Exact unfinished input, component precision, rows, validation state, dialog result, playhead and undo |

Also test unknown IDs, missing topic/bundle, destroyed origins, dialog-owner
transfer, repeated F1, Help search Ctrl+F, Ctrl+Z in the search field, Enter/Delete
in Help, Shift+F1 targeting and Escape through inspection/search/Help. Use
window-level input when testing modality, in addition to widget-level assertions.

Apply authoring Contracts **1–9 and 11**, with the existing
[authoring contract](authoring-contract.md),
[visual vocabulary](visual-interaction-vocabulary.md),
[interaction audit](authoring-interaction-audit.md) and
[20-task benchmark](authoring-benchmark.md). This adds a feature contract without
changing those authoritative interaction rules.

Help navigation uses shared secondary controls, neutral link roles, supporting
captions and visible focus roles. Record enabled/disabled, focus, theme-switch
and narrow-layout evidence. Follow the existing UI-GATE-01 minimum client area,
display/text scaling and label-integrity gates; no clipped labels, local colors
or larger minimum dimensions used to conceal failures.

### Delivery responsibilities

| Issue | Required evidence |
| --- | --- |
| KRT-85 | This design, inventory, scenario review and UX index link; published link in the issue |
| KRT-86 | Resolved/generated anchors, links, assets, Unicode, exact version and package resources; documented regeneration command |
| KRT-87–88 | Routing, modal ownership/lifecycle, keyboard isolation, control inspection and read-only state comparisons |
| KRT-89 | Human review of canonical task instructions, examples and semantic accuracy; reviewed anchors/control excerpts |
| KRT-90 | Bounded deterministic integrity checks and deliberately broken fixtures for IDs, targets, links, assets/version and fallback |
| KRT-91 | Extracted offline Windows ZIP from another working directory; native modal/multi-monitor where available, themes, narrow/scaled layouts and five human Help-seeking scenarios |

Static integrity verifies structure, not semantic accuracy or usability.
Record human review separately: reviewer, source revision, topics/scenarios,
corrections and acceptance. Internal/assisted testing is identified as such;
passing tests or this design-level review cannot establish independent human
acceptance. Require human approval before publishing authored reference prose.

KRT-85 remains open while its repository documentation is uncommitted. Record the
coherent commit, verification and design review outcome in Linear before closing
it. Later Help code, prose curation and native acceptance remain in their assigned
issues; they do not silently expand this documentation delivery.

## Technical references

Documentation verification on 2026-10-13: Sphinx 8.2.3 with MyST 4.0.1 passed
`python -m sphinx -b html -W --keep-going docs docs/_build/html`. Inspection of
the generated HTML verified 20 substantive-topic rows, 20 control registrations,
five scenario rows, 131 local links/fragments and the UX index entry. Planned
user-doc targets were not mistaken for existing targets. This verifies the design
document's structure, not future runtime Help or human documentation acceptance.

- [Qt QTextBrowser](https://doc.qt.io/qt-6.10/qtextbrowser.html): local document
  navigation, history and links.
- [Qt supported HTML subset](https://doc.qt.io/qt-6/richtext-html-subset.html):
  the renderer's content contract, rather than a web-browser layout engine.
- [Qt QWhatsThis](https://doc.qt.io/qt-6.10/qwhatsthis.html): native focused
  Shift+F1, pointer inspection, Escape and explanation-link handling; competing
  Shift+F1 shortcuts disable the native mechanism.
- [MyST 4.0.1 cross-references](https://myst-parser.readthedocs.io/en/v4.0.1/syntax/cross-referencing.html):
  explicit targets survive label changes; implicit heading targets are fragile.
