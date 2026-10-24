# Architecture and Threading

## Worker semantic indexing

`WorkerSemanticIndexService` owns the pending embedding queue, cached
`SearchService`, Windows native-model probe, index rebuild, and semantic
suggestion query. It is a plain Python object invoked through the existing
`DatabaseWorker` Qt slots on the database worker thread. The worker retains its
public slots and signals; the service receives the current worker-owned database
service only for each operation and emits through narrow notification callbacks.
Database reinitialization, failed initialization, and cleanup discard cached
search and pending work. The native-model probe remains once per worker lifetime.
The historical 1,990-line worker reference remains recorded in the architecture
test, with an explicit 1,864-line ceiling after this extraction.

## Simple-load failure reporting

`DatabaseWorker` retains its event/entity/map load slots, database access, guards,
success signals and thread ownership. A private reporter owns only a safe
operation/type/stack-location error log and the existing user-facing error signal.
It cannot execute or dispatch operations. Failed loads do not emit empty loaded
snapshots or completion signals; successful empty results still replace displayed
data. An additional dataset-specific failure notification is queued to the data
coordinator: a pending event/entity load failure terminates startup once with
`False`, releasing the existing splash without reporting empty success. Later
results cannot replace that terminal outcome. See
[worker failure contracts](worker-failure-contracts.md) for the bounded
inventory, consumer regression and verification evidence.

## Spell-check lifecycle and presentation

`SpellCheckController` is a GUI-thread QObject parented to a standard `QTextEdit`.
It owns the debounce timer, lazy LanguageTool thread/worker, settings generation,
request snapshots, matches, spelling actions and transient underlines. Requests
and results use explicit queued delivery; the worker receives detached text and
settings, never editor/document objects. The view retains standard context-menu
composition and wiki-link actions. Settings live in the separate
`SpellCheckSettingsDialog`, re-exported at its original import location.

Results require the current enabled request, settings generation, document
revision and rendered plain text. Edits, replacement, settings changes and
shutdown invalidate pending work. Theme refresh recolors existing underlines;
Qt highlighter-only revision changes refresh valid match revisions without
changing authored text or undo history. Suggestions still use ordinary text undo.

Closing stops scheduling and joins the current worker; showing a surviving view
resumes scheduling. Parent/editor destruction invokes cleanup while the child
controller still exists, without accessing the dying editor. No forced thread
termination or HTTP cancellation is introduced: closing can still wait for the
current request. Dependency guards prevent spelling state or thread ownership
from returning to `WikiTextEdit`. See [KRT-39 evidence](../ux/evidence/krt39/README.md).

## Temporal entity edit planning

`TemporalEntityEditPlanner` transforms detached entity, expected-owner, patch,
metadata and source-relation snapshots into a local edit plan. It owns baseline
changes, payload patching and ordered dated groups, with no persistence, Qt,
clock or ID-allocation dependencies. Its output owns nested values independently
of inputs and separates original from updated relation snapshots.

`TemporalEntityEditCommand` retains fresh comparison/conflict checks, distinct
source-record reads, undo state, payload validation, tag synchronization and all
writes inside the existing `BaseCommand` transaction. Dated relation ordering is
calculated after earlier writes, and the final checkpoint is built in that same
transaction. Planning errors retain the existing validation diagnostics. Plans
are not persisted: history retains the original intent and undo snapshots, and
redo prepares another plan. UI draft preparation remains KRT-40's separate
responsibility. See [KRT-42 evidence](../ux/evidence/krt42/README.md).

## Relation presentation and inline policy

The pure core relation-presentation helpers own existing captions, suggestions and
inline preview calculation. A separate core policy helper owns the existing inline
reversal assessment. Widgets retain rendering, groups, temporal summaries, drafts
and signals; authored persistence and exact undo boundaries are unchanged. See
[Relation handling boundaries](relation-handling.md) for the consumer inventory,
compatibility rules and deferred vocabulary integration contract.

## Offline Help capability

The Help coordinator owns contextual invocation, read-only navigation, search
intent and companion ownership. Its inspection controller handles native Qt
What's This pointer events, explicit pointer/focus explanation shortcuts and
transient popup input. Production composition registers
explicit control meanings and read-only region providers; widgets emit intent
and render snapshots. HelpSearchService ranks validated HelpSearchDocument
snapshots without Qt. HelpBundleService confines generated content and assets
to the version-matched offline bundle. None of these components query world data,
execute commands or add database-worker slots. GUI-local weak origin references
and native popup/registration metadata never cross worker boundaries.

## Timeline reconciliation and packing

`TimelineEventPreparationService` prepares full replacements and ordered mutation
batches without Qt or persistence. Its GUI-local result retains Event identities,
lists upserts/removals and accumulates geometry invalidations. `TimelineView`
continues to own graphics items, drop lines, group duplicates, scene updates,
debounce, initial fitting and navigation. No command or database boundary moves.

`TimelineLanePacker.measure_events()` resolves the current calendar and existing
item/text geometry on the GUI thread. Frozen `TimelineLayoutInput` records contain
only event ID, start/end lore days (including gap) and height. Both synchronous and
grouped packing use `pack_timeline_intervals()`; the asynchronous `LayoutWorker`
uses the same pure calculation with detached records. No live Event, calendar,
font or graphics item crosses this worker boundary.

Queued completion signals carry a unique request token. The view checks token
identity and the captured layout generation before applying results. Event
geometry, preview, scale, calendar and grouping changes invalidate older work;
empty replacement/removal also invalidates it. One active worker coalesces newer
requests. Stale completion redispatches through the current empty/grouped/sync/
async selection; stale errors cannot trigger an old fallback. Current errors use
fresh synchronous measurements. Dependency tests guard these extracted boundaries.

Accepted lane history is GUI-owned and scoped separately to standard layout,
each tag band and All events. Frozen snapshots cross the layout-worker boundary.
Packing uses saved lore-date anchors (stable ID ties) independently of visual
collision starts. Each interval takes one row below the deepest earlier
intersecting interval, or row zero without such predecessors. This longest-path
recurrence minimizes rows under chronological precedence, in O(n squared) time
and O(n) storage. A chain can require more rows than unconstrained overlap depth.
Current member heights shrink automatically; accepted history cannot override
chronology. Both worker and GUI paths use this same canonical calculation.
Histories are published after successful scene application; stale worker
callbacks cannot publish them. Grouped passes stage history until the full pass
succeeds. Empty timelines purge history; ordinary refreshes keep surviving IDs.

## Dependency direction

```text
src/app → src/gui → src/commands → src/services → src/core
```

Keep dependencies moving in this direction. `AppCoordinator` is the facade for
cross-feature orchestration.

## Strangler migration guardrails

The following transitional modules are established choke points:

- `src/app/map_handler.py`
- `src/services/worker.py`
- `src/app/connection_manager.py`
- `src/app/main_window.py`
- `src/services/db_service.py`

Do not add a new feature responsibility to them. Bug fixes and small
modifications to existing responsibilities remain appropriate. New capabilities
belong in capability-specific controllers, coordinators, services, repositories,
or domain models. In particular, prefer the relevant repository/service to a new
feature-specific `DatabaseService` method; do not make a new `DatabaseWorker`
slot or `ConnectionManager` signal connection the default home for new work; and
do not add feature logic to `MainWindow`.

For substantial work in a choke point, first consider extracting the touched
capability and retaining a delegating compatibility method. Prefer explicit,
narrow dependencies such as `SomeCoordinator(repository, navigation,
command_executor)` instead of passing `MainWindow` or another large application
object into a feature component. Do not introduce a dependency-injection
framework.

```text
UI
  -> feature-specific controller/coordinator
  -> application/domain service
  -> repository/domain model
```

Qt threading and signal plumbing are infrastructure concerns, not feature
boundaries. This is a strangler migration: choke points may temporarily remain
facades, extracted components can initially be invoked through them, and new
behavior should increasingly bypass them. Existing code does not need to be
reorganized immediately; move old behavior when that capability is next
substantially modified.

The first production extraction follows this pattern for raster management:
`MapHandler` retains its existing public raster API as a compatibility facade,
while `RasterController` owns raster rendering, editing, temporal state, and
command intent. Shared marker and layer-tree synchronization remains in
`MapHandler`; dependencies flow only from the facade to the raster controller.

## Mutation flow

```text
Widget signal
  → EditorCoordinator
  → BaseCommand
  → CommandCoordinator
  → DatabaseWorker.run_command()
  → BaseCommand.execute(db_service)
```

Widgets render snapshots and emit intent. They do not execute SQL, perform
business mutations, or own service objects.

Temporal entity saves use the stateless `TemporalEntityDraftService` to compare
copied draft snapshots and prepare patches and baseline metadata. It returns
`NoChanges`, `ChoiceRequired` or `PreparedSave`; it has no Qt, command or storage
dependencies. The widget owns dialogs, a local preparation guard and a copied
`PendingTemporalSubmission`, while `BaseEditorMixin` owns revisions and dirty
state. Context and draft comparisons are checked after modal choices and before
submission. The existing coordinator correlates results; the widget installs the
transaction-built checkpoint before releasing save guards or restarting autosave.
Neither preparation nor acknowledgement replaces newer live form values.

## Thread ownership

`DatabaseService` belongs to the database worker thread. Never access it from
the Qt main thread, including for allegedly read-only convenience queries.

Use queued delivery:

- `Qt.ConnectionType.QueuedConnection`
- `QMetaObject.invokeMethod(..., QueuedConnection)`

Pass serializable snapshots such as dictionaries across thread boundaries. Do
not pass live commands, database connections, widgets, or other thread-owned
objects.

### Persistence connection contracts

`DatabaseService.require_connection()` returns an already-open SQLite connection
only on the thread that opened it. Disconnected or foreign-thread access raises
`RuntimeError`; it never opens a database. CLI and webserver operations open their
own services before requesting a connection. `get_connection()` retains lazy
opening for existing callers and checks ownership before returning the connection.

Private `_connection` access belongs only in `DatabaseService` and repository
internals. An AST regression guard covers all production layers, including aliases
and reflective access. Raw connections remain deliberate inputs to persistence
services such as search, tag filtering and Longform; they must not cross threads.

`AuthoredRelationService` owns authored relation endpoint validation, protected
type policy, creation/update preparation and exact undo restoration. It receives
a relation repository and narrow entity/event lookup callbacks; `DatabaseService`
keeps delegating compatibility methods and its existing lazy connection behavior.
Commands bind the service's repositories to their worker-owned
`require_connection()` result. The service opens no connection and begins no
transaction: repository writes join the command/import owner's transaction, or
own a standalone transaction through the existing repository context manager.

Forward relation creation, edits, reversal and redo require canonical UUIDs for
every supplied endpoint and verify that the entity/event exists. IDs are rejected,
never normalized. Consequently, history that references existing objects with
noncanonical IDs can fail forward replay without rewriting its serialized state.
Undo restores its captured source, target, type and attributes without applying
forward canonical validation, preserving relation identity and creation time.
SQLite endpoint-existence constraints still apply to restoration. Commands retain
identity allocation, stale-edit checks, snapshots and serialization; generated
wikilink mentions keep their separate repository reconciliation path. The existing
dependency-direction tests enforce the service/facade/command responsibility seam.

Longform mutation helpers leave commit and rollback to their caller. Commands use
the `BaseCommand` transaction; CLI indexing/export and worker indexing explicitly
own service transactions. Nested operations join an existing transaction rather
than committing it. Read metadata through `longform_builder.get_longform_meta()`;
the canonical source is `attributes._longform`, not a separate structure table.

Longform commands capture their complete document metadata on the worker immediately
before their first successful execution. The serialized `metadata_before` snapshot
distinguishes absent metadata, empty dictionaries, and original container presence.
Undo restores that snapshot while preserving other documents and unrelated current
attributes; redo retains the original undo target. Older history without a snapshot
falls back to the recorded `old_meta` and cannot recover fields never recorded.

`ensure_fresh_view()` never commits, rolls back, or checkpoints an active transaction.
Its owner controls when the snapshot ends. Idle calls may perform a best-effort WAL
checkpoint; subsequent reads naturally see newly committed data.

### Analysis Suite

Deterministic validation and temporal analysis execute on the database worker.
Each request carries job and world IDs; consumers reject superseded output. A
typed failure signal restores controls on every terminal path.

AI analysis first captures a deep, serializable snapshot on the database
worker, including the world ID, timestamp, explicit scope, preset, and selected
categories. A dedicated AI `QThread` reconstructs core objects and makes model
calls without database or widget access. Cancellation uses a thread-safe token.
Late results are accepted only while both job and world IDs remain current.

Structured responses use `json.loads`, schema and enum checks, candidate-ID
validation, and supplied-evidence-ID validation. One malformed response can
receive one repair request. Reports and dismissals remain in the GUI session;
they never enter world storage or `QSettings`.

Relation visibility is centralized in `src/core/temporal_window.py`. The
relation dialog, resolver, analyzer, and validator use that evaluator so
instant, dynamic, open, and invalid interval semantics cannot drift.

## Coordinators

- `AppCoordinator` coordinates cross-feature work.
- `EditorCoordinator` turns editor intent into commands.
- `DataCoordinator` distributes loaded snapshots.
- `NavigationCoordinator` resolves links and selections.
- `TimeCoordinator` synchronizes playhead-dependent views.
- `ImportCoordinator`, `BackupCoordinator`, and `FastInjectCoordinator` own
  their respective workflows.

## Temporal assertions and projections

`src/core/temporal_expression.py` defines schema version 1. An event's
`attributes._temporal_v2` contains `schema`, `expression`, and optionally
`end_expression` for a separately asserted duration endpoint. An event can
also have a positive `lore_duration` with no asserted end date. Expressions
retain calendar identity,
supplied components, precision, qualification, original text, and explicit
outer bounds. Additional `claims` and `constraints` records survive edits and
exports; competing claims are not merged into an occurrence range. The
canonical `expression` drives state; claims remain separate evidence.

`lore_date` is a compatibility/layout projection when this metadata is present.
With `end_expression`, `EventRepository` projects `lore_duration` from the two
representative positions; otherwise a positive `lore_duration` is the authored
duration. The repository regenerates temporal coordinates on writes, while
`event_temporal_service` and `move_expression` preserve precision during moves.
The worker's calendar load calls `calendar_context_service.ensure_active_calendar`
before publishing a converter configuration. Worlds without an active calendar
get a persisted Gregorian default; UI code must never mint a temporary calendar
ID for authoring. A storage failure leaves calendar initialization unavailable
and emits an error instead of publishing an unsavable identity.
Absence of metadata alone selects legacy exact semantics. Invalid metadata
must produce a diagnostic or a rejected write, never silent exact fallback.

Relations and map layers use `attributes.temporal`, with `schema: 1`,
`behavior`, and `start`/`end` or occurrence `at` boundaries. Each boundary is
one of `{"expression": ...}`, `{"exact": ...}`, `{"status": "open"}`,
`{"status": "unknown"}`, `{"binding": "source_event"}`, or
`{"anchor": {"anchor_id": "event:<uuid>", "offset_days": 0}}`.
The compatibility reader still supports legacy `valid_*` fields and flags.

`resolve_temporal_window().status_at()` is the shared truth evaluator. Its
four statuses are definite, possible, inactive, and indeterminate. Consumers
must choose an explicit policy: the state resolver applies only definite
payloads and retains possible effects; graph snapshots carry their status;
map rendering keeps uncertain layers visible with a cue. Unknown boundaries
must not be converted to open boundaries or falsehood. Intervals are
half-open, while legacy equal-bound occurrences retain instant semantics.

`resolve_event_anchors` preserves identity across queries. `overlap_status`
recognizes shared handovers and explicit chronological order.
`TemporalConstraint` supports `before`, `after`, and `same_as`, with optional
nonnegative `min_offset_days` and stable IDs for newly written rules.
`chronology_service` gathers rules from all event metadata, projects direct
incoming and outgoing orderings, and validates the whole graph. Validation
contracts shared transitions, detects cycles, and propagates hard date bounds
with explicit open endpoints. `ApplyChronologyCommand` revalidates and updates
all touched events atomically; `UpdateEventCommand` validates changed dates.
Existing invalid rules remain visible without blocking unrelated saves.
The event editor offers separate **Chronology...** and **Date evidence...** actions.
This is a bounded validation system, not a probabilistic world solver.

Analysis checks role exclusivity only when a relation explicitly has
`attributes.exclusive: true`; it groups competing sources by target and role.
Certain overlap is critical, possible overlap is a warning, and a shared
handover is not a conflict. Partial lifespan dates are informational rather
than fabricated exact ages.

`GraphDataService` applies `GraphTemporalMode` before deriving connected nodes.
The data coordinator sends playhead/mode snapshots over a queued signal to
the worker. Widgets consume evaluated snapshots; they only control the reveal
policy. Incremental edge updates freeze layout when node identities are
unchanged, retaining pan, zoom, and selection. Timeline future/past cues use
evidence bounds. `event_temporal_display` derives the possible envelope and
any certainly occupied interior from hard bounds. The Timeline paints these
on one track and its lane packer reserves the full envelope; a representative
coordinate is used for layout and snapping, never as an asserted start.

No existing numeric date is automatically reinterpreted. The optional legacy
precision review assistant, EDTF export, and derived database indexes are not
included. Ordinary JSON export retains the complete semantic attributes.

Before deleting an event, the command checks persisted temporal dependencies
on the worker thread. A failed preflight returns a serializable dependency
snapshot; the main-thread coordinator presents it and can submit a confirmed
retry. The retry checks the dependencies again before deleting. References
outside attached relations remain unresolved rather than becoming unbounded;
undo restores the event anchor. See [temporal acceptance](temporal-acceptance.md).

## Settings configuration

`SettingsCoordinator` owns the modeless Settings Center, detached drafts,
conflicts and persistence acknowledgements. Widgets render snapshots and emit
intents. The main menu bar has one direct Settings action; immediate contextual
controls use the GUI intent bus and the same coordinator adapters.

`settings_registry` defines stable IDs, scopes, defaults, validation, search
aliases and reset eligibility. `LocalSettingsAdapter` owns the canonical
QSettings preference allowlist and OS credential migration. Workspace resets
are scheduled for startup so ordinary shutdown cannot overwrite their result.

`SettingsSnapshotWorker` is a feature endpoint on the existing database thread.
Its provider is called only there; explicitly queued signals carry detached
values and the database/request identity. `SettingsRepository` owns the
versioned `system_meta.world_preferences` record and exact metadata restoration.
Migration provenance remains present through preference resets.

One `ApplyWorldSettingsCommand` applies a world patch through normal command
execution and its transaction boundary. It checks the originating database and
expected values before mutation, and serializes exact prior values for undo.
Local preferences, credentials and world changes have separate acknowledgements;
only failed groups stay pending. Runtime AI/theme/indexing caches derive from
committed snapshots. Index rebuilding remains an explicit operation.

## UI rules

- Use `StyleHelper` and `ThemeManager`; do not hardcode widget colours.
- Use runtime-recoloured SVG icons through `icon_loader.py`.
- Declare Qt signals with `Signal`.
- Use fully qualified Qt enum names.
- Guard delayed widget access during teardown with `shiboken6.isValid`.

### Interface Help

Feature constructors attach semantic inspection metadata with the GUI-local
`declare_inspection` helper. `HelpSurfaceBindings` connects those declarations,
associated form labels, default actions and overflow equivalents to
`HelpContextRegistry`. This registration is independent of ordinary F1 context
precedence. The application-layer `HelpInspectionController` resolves native
targets and loads validated canonical excerpts through `HelpBundleService`;
widgets do not load documentation or infer meaning from displayed labels.

The build-only `docs/help-inspection.json` inventory supplies canonical targets
and source-review fingerprints. `src/core/help_inspection_inventory.py` checks
declarations and review drift without Qt, database or worker dependencies.

### Workspace shell

The production `src/app/main_window.py` owns one central `WorkspaceShell`.
Project, Entity, Event, Map, Timeline, Graph, Longform, Analysis, AI Search, and
History remain their original feature-widget instances and are registered as
semantic panels. The shell provides exactly four generic destinations: Left,
Center, Right, and Bottom.

Application code reveals panels through `workspace.show_panel(panel_id)` and
must not infer a panel's current physical zone. Workspace persistence is the
explicit versioned panel/order/visibility/size structure in
`src/gui/workspace/layout_state.py`; outer window geometry is stored
separately.
