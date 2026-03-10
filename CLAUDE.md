# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Run the application
```bash
python -m src.app.main
```

### Run all tests
```bash
pytest
```

### Run a single test file or function
```bash
pytest tests/unit/test_events.py
pytest tests/unit/test_events.py::test_event_creation
```

### Run tests with coverage
```bash
pytest --cov=src --cov-report=term-missing
```

### Run only fast unit tests (skip slow)
```bash
pytest -m "not slow"
```

### Linting and formatting
```bash
ruff check src/          # Check for issues
ruff check src/ --fix    # Auto-fix issues
ruff format src/         # Format code
mypy src/                # Type checking
```

### Build executable
```bash
pyinstaller ProjektKraken.spec
```

## Architecture

ProjektKraken is a PySide6 desktop worldbuilding app organized into strict layers. The "Dumb UI" principle is enforced: widgets only display and emit signals, never contain business logic or direct database access.

### Layer Stack (top to bottom)

**Application Layer** (`src/app/`)
`main.py` → `MainWindow` coordinates all panels. Specialized coordinators handle focused concerns: `BackupCoordinator`, `NavigationCoordinator`, `TimeCoordinator`, `CommandCoordinator`. `WorkerManager` manages the background database thread lifecycle.

**Commands Layer** (`src/commands/`)
All user mutations are encapsulated as `BaseCommand` subclasses with `execute()` and `undo()` methods. Commands are serialized to the `command_history` DB table for persistent undo/redo across sessions. Existing command modules: `event_commands.py`, `entity_commands.py`, `relation_commands.py`, `wiki_commands.py`, `map_commands.py`, `calendar_commands.py`.

**Services Layer** (`src/services/`)
- `DatabaseService` (`db_service.py`): Raw SQLite interface, owns WAL-mode connection
- `repositories/`: One repository per domain object (EventRepository, EntityRepository, RelationRepository, MapRepository, CalendarRepository, etc.) — all take `DatabaseService` via constructor injection
- `HistoryService`: Persists command history
- `BackupService`: Automated + manual backup with retention policy
- `AssetStore`: Image/icon import (WebP conversion), trash/restore for undo support
- `RAGService`: Hybrid lexical + semantic search via LM Studio embeddings

**Core Layer** (`src/core/`)
Dataclass domain models: `Event`, `Entity`, `Relation`, `Calendar`, `Map`, `World`. Each has `to_dict()` / `from_dict()`. Utilities: `ThemeManager` (singleton, loads `themes.json`), `CalendarConverter`, `LinkResolver`.

**GUI Layer** (`src/gui/`)
Widgets in `src/gui/widgets/`. Key subdirectories:
- `timeline/` — lane-based and ruler timeline visualization
- `map/` — `MapGraphicsView`, GIS feature editing (paths, regions, markers), raster layer support with legend overlay
- `longform/` — hierarchical document editor with live FastAPI/uvicorn preview server
- Top-level widgets: `entity_editor.py`, `event_editor.py`, `unified_list.py`, `wiki_text_edit.py` (supports `[[wiki links]]`), `gallery_widget.py`, `sheet_builder.py`

### Threading Model

Two threads: main Qt thread (UI only) and a `DatabaseWorker` (QThread) that owns the `DatabaseService`. Commands are submitted to the worker via a queue. Results return to the main thread via Qt signals using `QueuedConnection`. **Never access `DatabaseService` from the main thread.**

### Data Model

SQLite database (`.kraken` extension) per world. Hybrid schema: strict columns for searchable/sortable fields, plus a paired `*_attributes` table storing flexible JSON per record. Key tables: `events`, `entities`, `relations`, `maps`, `map_markers`, `map_layers`, `calendars`, `command_history`, `edit_sessions`, `backups`.

### World / Portable Storage

All worlds live in a `worlds/` directory next to the executable (or project root in dev). Each world is a subdirectory containing `world.json` (manifest) and a `.kraken` SQLite file. User preferences (window layout, settings) use QSettings at the OS app-data path.

## Key Conventions

- **Type hints required** on all function signatures; `ANN` rules enforced by ruff (except in tests)
- **Google-style docstrings** for all public classes and methods
- **Double quotes** for strings; line length 88 (Black-compatible)
- **Imports order**: stdlib → third-party → local (`src.*`)
- No wildcard imports from Qt or anywhere else
- Commit messages use conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `style:`, `test:`
- Tests use `pytest-qt` with offscreen Qt platform (`QT_QPA_PLATFORM=offscreen` set in `conftest.py`)
- `ThemeManager` is a singleton initialized in `conftest.py`; tests requiring it should use the `init_theme_manager` session fixture
