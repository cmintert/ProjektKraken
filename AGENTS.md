# AGENTS.md
## Project Snapshot
- ProjektKraken is a PySide6 desktop worldbuilding app with timeline-first UX and portable world folders.
- On Windows, launch with `start-kraken.cmd` for the environment preflight. The
  cross-platform entry point is `python -m src.app.main` (`src/app/main.py` is a
  shim; real startup is in `src/app/entry.py`).

## Architecture To Preserve
- Respect one-way dependencies: `src/app` -> `src/gui` -> `src/commands` -> `src/services` -> `src/core`.
- Keep UI dumb: widgets in `src/gui/**` render state and emit signals, but do not run business logic or SQL.
- Mutation path is coordinator-driven: widget signal -> `EditorCoordinator` -> command -> `CommandCoordinator` -> `DatabaseWorker.run_command()` -> `BaseCommand.execute(db_service)`.
- `AppCoordinator` (`src/app/coordinators/app_coordinator.py`) is the facade for cross-feature orchestration.

## Threading Rules (Critical)
- `DatabaseService` is owned by the worker thread (`src/services/worker.py`); never access it from the Qt main thread.
- Use queued cross-thread delivery only: `Qt.ConnectionType.QueuedConnection` / `QMetaObject.invokeMethod(..., QueuedConnection)`.
- Pass serializable snapshots across boundaries (see `history_changed` snapshot dicts in `src/app/command_coordinator.py`).
- Preserve undo/redo overlap guards in `src/app/command_coordinator.py` when changing command flow.

## Data And Storage
- Each world lives under `worlds/<World Name>/` with `world.json`, `<World Name>.kraken`, and `assets/`.
- IDs are `str(uuid.uuid4())`; timestamps are `float`; lore time is float days (`1.0 == 1 day`).
- Core models stay as dataclasses with `to_dict()` / `from_dict()` (example: `src/core/events.py`).
- DB pattern is strict columns plus JSON attributes (see `src/services/db_service.py`).

## UI, Commands, And Style Conventions
- Use `StyleHelper` + `ThemeManager().get_theme()` for styling; do not hardcode widget colors.
- Load/recolor SVGs with `src/gui/utils/icon_loader.py` (`currentColor` replacement pattern).
- Commands follow `BaseCommand`: no service in `__init__`, implement `execute(self, db_service)` and `undo(self, db_service)`.
- Prefer `BaseCommand._assign_tags(...)` / `_sync_tags(...)` over manual tag sync loops.
- Use `Signal` from `PySide6.QtCore`, fully qualified enums, and `logging` (never `print()`).
- Ruff/mypy conventions are enforced: annotations in non-test code, 88-char lines, double quotes, stdlib/third-party/local import order.

## Build, Test, And CI Workflow
- App: `start-kraken.cmd` on Windows or `python -m src.app.main`; environment:
  `python launcher.py --check`; tests: `pytest`; fast suites: `pytest -m smoke -q`,
  `pytest -m "not slow"`.
- On Windows GUI tests, set `$env:QT_QPA_PLATFORM = "offscreen"` before running pytest.
- Quality gates: `python -m ruff check src/ tests/`, `python -m ruff check src/ tests/ --fix`, `mypy src/`.
- Reuse `tests/conftest.py` fixtures (`qapp`, `db_service`, `init_theme_manager`); avoid ad-hoc Qt/DB fixture copies.
- Watch for test pitfalls: shared `MockQSettings._storage`, teardown validity checks (`shiboken6.isValid(...)`), and debounce/timer-driven UI behavior.

## Read First
- `README.md`, `.github/copilot-instructions.md`, `CLAUDE.md`
- `src/app/worker_manager.py`, `src/app/connection_manager.py`, `src/app/coordinators/`
- `src/commands/base_command.py`, `src/services/worker.py`, `tests/conftest.py`

