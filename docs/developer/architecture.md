# Architecture and Threading

## Dependency direction

```text
src/app → src/gui → src/commands → src/services → src/core
```

Keep dependencies moving in this direction. `AppCoordinator` is the facade for
cross-feature orchestration.

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

