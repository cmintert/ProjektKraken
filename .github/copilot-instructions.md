# ProjektKraken Workspace Instructions

## Project Overview

ProjektKraken is a desktop worldbuilding application with a timeline-first workflow.
Primary stack: Python 3.13+, PySide6, SQLite, pytest, ruff, and mypy.

## Build And Test

- On Windows, run the app with `start-kraken.cmd` so the environment is checked;
  `python -m src.app.main` remains the cross-platform module entry point.
- Run the test suite with `pytest`.
- Run GUI tests on Windows with `$env:QT_QPA_PLATFORM = "offscreen"` before invoking pytest.
- Run a focused test with `pytest tests/unit/test_events.py::test_event_creation`.
- Run coverage with `pytest --cov=src --cov-report=term-missing`.
- Run lint checks with `python -m ruff check src/ tests/`.
- Auto-fix lint issues with `python -m ruff check src/ tests/ --fix`.
- Run type checking with `mypy src/`.
- Build the executable with `pyinstaller ProjektKraken.spec`.

## Architecture

Respect the one-way dependency stack:

- `src/app/`: orchestration, `MainWindow`, coordinators, worker lifecycle.
- `src/gui/`: dumb UI only; widgets display state and emit signals.
- `src/commands/`: undoable user actions as `BaseCommand` subclasses.
- `src/services/`: data access, repositories, workers, indexing, import/export, AI integrations.
- `src/core/`: domain models, temporal logic, theme management, shared utilities.

Key rules:

- Do not put business logic or direct database access in GUI widgets.
- Route user mutations through coordinator -> command -> worker thread execution.
- `DatabaseService` is worker-thread owned. Never access it from the main Qt thread.
- Pass immutable snapshots such as dicts across thread boundaries, not live Qt objects or command instances.

Use these files as canonical examples:

- `src/app/coordinators/` for app-layer orchestration.
- `src/commands/base_command.py` for command shape and tag helper usage.
- `src/gui/utils/style_helper.py` for theme-aware styling.
- `tests/conftest.py` for Qt and database test fixtures.

## Conventions

- Follow ruff rules from `pyproject.toml`: 88-character lines, double quotes, type annotations on non-test code.
- Write Google-style docstrings for public classes and methods.
- Use `logging`, never `print()`.
- Import order is stdlib, third-party, then local `src.*` modules.
- Use `Signal` from `PySide6.QtCore`, never `pyqtSignal`.
- Use fully qualified PySide6 enums such as `Qt.AlignmentFlag.AlignLeft`.
- Put reusable magic numbers in `src/app/constants.py` or `src/app/ui_constants.py`.
- Domain models should remain dataclasses with `to_dict()` and `from_dict()` methods.
- IDs are `str(uuid.uuid4())`; timestamps are `float`; lore time uses `lore_date: float` where `1.0 == 1 day`.

For commands:

- `BaseCommand.__init__()` takes no service argument.
- Implement `execute(self, db_service)` and `undo(self, db_service)`.
- Use `BaseCommand._assign_tags(...)` and `BaseCommand._sync_tags(...)` instead of manual tag loops.

For styling:

- Never hardcode widget colors in code.
- Add or reuse theme-aware QSS via `StyleHelper` methods backed by `ThemeManager().get_theme()`.
- Use runtime-recolored Phosphor SVG icons via `src/gui/utils/icon_loader.py`.

## Qt And Testing Pitfalls

- Guard deferred access to `QObject`, `QWidget`, and `QTextDocument` instances with `shiboken6.isValid(...)`, and handle `RuntimeError` where teardown is possible.
- `QApplication.focusWidget()` can return a `QTextEdit` viewport instead of the editor widget; check both.
- `tests/conftest.py` provides the in-memory `db_service` fixture and initializes `ThemeManager`; prefer those fixtures over custom setup.
- `MockQSettings._storage` is shared across tests. Clear touched keys or patch `QSettings` per test to avoid contamination.
- Wiki-link document analysis uses a debounce timer; guard document access during teardown.

## References

- `README.md` for developer commands and product context.
- `docs/ARCHITECTURE.md` for deeper architecture details.
- `docs/TESTING.md` for test strategy and expectations.
- `AGENTS.md` for repository-wide agent instructions and critical invariants.
