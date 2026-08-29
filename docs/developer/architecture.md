# Architecture and Threading

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

## Thread ownership

`DatabaseService` belongs to the database worker thread. Never access it from
the Qt main thread, including for allegedly read-only convenience queries.

Use queued delivery:

- `Qt.ConnectionType.QueuedConnection`
- `QMetaObject.invokeMethod(..., QueuedConnection)`

Pass serializable snapshots such as dictionaries across thread boundaries. Do
not pass live commands, database connections, widgets, or other thread-owned
objects.

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

## UI rules

- Use `StyleHelper` and `ThemeManager`; do not hardcode widget colours.
- Use runtime-recoloured SVG icons through `icon_loader.py`.
- Declare Qt signals with `Signal`.
- Use fully qualified Qt enum names.
- Guard delayed widget access during teardown with `shiboken6.isValid`.

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
