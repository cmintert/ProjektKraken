# GitHub Copilot Instructions for ProjektKraken

## Project Overview

ProjektKraken is a desktop worldbuilding environment with a timeline-first workflow. It uses a "Trinity" view system (Editor, Timeline, Relations), a hybrid SQL+JSON data model, and a dark-mode dockable-panel UI.

**Stack:** Python 3.13+, PySide6, SQLite 3.35+, pytest/pytest-qt, ruff, mypy

---

## Build, Test, and Lint

```bash
# Run the application
python -m src.app.main

# Run all unit tests (GUI tests require offscreen platform)
QT_QPA_PLATFORM=offscreen python -m pytest tests/unit/

# Run a single test
QT_QPA_PLATFORM=offscreen python -m pytest tests/unit/test_foo.py::test_bar

# Run integration tests
python -m pytest tests/integration/

# With coverage
pytest --cov=src --cov-report=term-missing

# Lint and auto-fix
python -m ruff check src/ tests/ --fix

# Type checking
mypy src/
```

> **Note:** On Windows, set `$env:QT_QPA_PLATFORM = "offscreen"` in PowerShell before running GUI tests.

---

## Architecture

Five layers with strict one-way dependency:

```
App (src/app/)          ← orchestration, MainWindow, Coordinators
GUI (src/gui/)          ← "dumb UI": display + emit signals only
Commands (src/commands/)← undo/redo: all user actions as command objects
Services (src/services/)← data access (DatabaseService, Repositories, Workers)
Core (src/core/)        ← domain models, ThemeManager — zero UI deps
```

### MainWindow is split into Coordinators

`MainWindow` delegates responsibility to coordinators in `src/app/coordinators/`:

- **`EditorCoordinator`** — `create_entity`, `delete_entity`, `update_entity`, `add_relation`, `remove_relation`, `update_relation`, `delete_event`, `update_event`
- **`DataCoordinator`** — `load_event_details`, `load_entity_details`
- **`CommandCoordinator`** — undo/redo stack, `history_changed` signal, `execute(cmd)`
- **`NavigationCoordinator`**, **`BackupCoordinator`**, **`TimeCoordinator`**, etc.

Access via `main_window.editor_coordinator`, `main_window.data_coordinator`, etc.

### Communication flow

```
Widget emits signal → MainWindow/Coordinator slot
→ constructs Command → CommandCoordinator.execute(cmd)
→ DatabaseWorker thread runs cmd.execute(db_service)
→ Worker emits signal → main thread updates UI
```

---

## Command Pattern

The **actual** `BaseCommand` signature (different from older docs):

```python
class BaseCommand(ABC):
    def __init__(self) -> None:                          # NO service in __init__
        self._is_executed = False
        self.timestamp: float = time.time()

    @abstractmethod
    def execute(self, db_service: DatabaseService) -> CommandResult: ...

    @abstractmethod
    def undo(self, db_service: DatabaseService) -> None: ...

    @abstractmethod
    def to_dict(self) -> Dict: ...

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict) -> "BaseCommand": ...

    @property
    def has_history(self) -> bool:
        return True  # Override to False for silent background commands
```

Tag helpers on `BaseCommand` — use these instead of inline loops:
- `BaseCommand._assign_tags(db_service, object_id, tags, object_type)` — initial assignment
- `BaseCommand._sync_tags(db_service, object_id, new_tags, object_type)` — diff-based sync on update

---

## Coding Standards

- **Linter:** `ruff` (not flake8). Run `python -m ruff check src/ tests/ --fix`.
- **Line length:** 88 characters.
- **Type hints:** required everywhere — parameters, return types, class attributes.
- **Docstrings:** Google Style, required for all public classes and methods.
- **Logging:** `logging` module only — never `print()`.
- **Imports:** stdlib → third-party → local; no wildcards.
- **Signals:** PySide6 uses `Signal` from `PySide6.QtCore`, **not** `pyqtSignal`.
- **Constants:** All magic numbers go in `src/app/constants.py`. Layout spacing/margins use `src/app/ui_constants.py` (`Spacing`, `Margins` classes — 8-point grid).

---

## Styling Rules

**Never hardcode colors in widget code.** All QSS must use theme tokens via `StyleHelper`:

```python
from src.gui.utils.style_helper import StyleHelper
# Add a new static method to StyleHelper (e.g. get_my_widget_style())
# that reads ThemeManager().get_theme() for color tokens.
```

- `StyleHelper.get_tool_button_style()` — standard action buttons
- `StyleHelper.get_flat_tool_button_style()` — buttons inside toolbars/header rows
- Icons: Phosphor SVGs, recolored at runtime — use `src/gui/utils/icon_loader.py`
- Themes defined in `themes.json`; access tokens via `ThemeManager().get_theme()`

---

## Qt/PySide6 Patterns

### Object destruction safety

PySide6 C++ objects can be deleted while Python wrappers still exist. Before accessing any `QObject`/`QWidget`/`QTextDocument` in a timer or deferred callback:

```python
import shiboken6
if not shiboken6.isValid(self.my_qt_object):
    return
```

Also wrap in `try/except RuntimeError` when even `isValid` may not catch partial teardown.

### Thread safety

- `DatabaseService` is owned by the worker thread — **never** access from the main thread.
- Cross-thread: pass **immutable snapshots (dicts)**, not live command objects.
- `HistoryPanel` receives `(list[dict], list[dict])` snapshots, not raw `BaseCommand` lists.
- `history_changed.emit()` fires **before** `undo_requested.emit()` to prevent concurrent mutation.

### QTextEdit focus

`QApplication.focusWidget()` returns `text_edit.viewport()` when a `QTextEdit` has focus. Check both when saving focus state:

```python
focus = QApplication.focusWidget()
if widget.value_edit is focus or widget.value_edit.viewport() is focus:
    ...
```

---

## Testing Conventions

- **GUI tests** require `QT_QPA_PLATFORM=offscreen` (set in `tests/conftest.py` but must also be set in the shell for subprocess runs).
- **In-memory DB:** use the `db_service` fixture from `tests/conftest.py` — it provides a fresh `DatabaseService(":memory:")` per test.
- **`MockQSettings._storage`** is a **class-level dict** (shared across all tests in the session). Tests that write to it contaminate later tests. Clear specific keys in teardown or use `monkeypatch.setattr` to override `PySide6.QtCore.QSettings` per-test.
- **Minimum coverage:** 85% overall; core logic/commands 100%.
- **Test naming:** `test_<method>_<scenario>` or `test_<method>_<scenario>_<expected>`.

---

## Data Model Conventions

- `@dataclass` with `to_dict()` / `from_dict()` for all domain models.
- IDs: `str(uuid.uuid4())`.
- Timestamps: `float` (Unix epoch).
- **Time storage:** `lore_date: float` where `1.0 = 1 day`. Calendar display is separate from storage.
- **Hybrid schema:** SQL columns for searchable fields; JSON `attributes` column for flexible key-value pairs.
- **File format:** `.kraken` (SQLite). WAL mode, foreign keys on.

---

## Wiki Links

- Format: `[[Entity Name]]`
- Rendered/parsed by `WikiTextEditView` (`src/gui/widgets/wiki_text_edit.py`)
- `SectionManager` inside it uses a 300ms debounce timer — always guard `_analyze_document` with `shiboken6.isValid(self.document)`.
- Auto-relation creation on wiki link insertion is toggled by `SETTINGS_AUTO_RELATION_KEY`.
