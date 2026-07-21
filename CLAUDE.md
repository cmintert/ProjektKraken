# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Run the application
```powershell
.\start-kraken.cmd
```

Use `python -m src.app.main` as the cross-platform module entry point.

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
Entry point is `src/app/entry.py`; `main.py` is a backward-compatibility shim. `MainWindow` lives in `main_window.py` and coordinates panels via specialized objects:
- `coordinators/` — `AppCoordinator` (top-level), plus `BackupCoordinator`, `DataCoordinator`, `EditorCoordinator`, `FastInjectCoordinator`, `ImportCoordinator`, `NavigationCoordinator`, `TimeCoordinator`
- `CommandCoordinator` — routes commands to the worker queue
- `ConnectionManager` — wires Qt signals between components
- `DataHandler` / `MapHandler` / `LongformManager` / `AISearchManager` / `TimelineGroupingManager` — domain-specific app-layer managers
- `UIManager` / `WidgetRegistry` — dock/panel lifecycle and widget lookup
- `WorkerManager` — background database thread lifecycle

**Commands Layer** (`src/commands/`)
All user mutations are `BaseCommand` subclasses with `execute()` / `undo()`. Commands are serialized to `command_history` for persistent undo/redo. A `registry.py` maps command type strings to classes for deserialization. `CompositeCommand` bundles multiple commands atomically. Key modules: `event_commands`, `entity_commands`, `relation_commands`, `wiki_commands`, `map_commands`, `map_crud_commands`, `marker_commands`, `layer_commands`, `raster_commands`, `image_commands`, `longform_commands`, `calendar_commands`, `timeline_grouping_commands`, `inject_commands`.

**Services Layer** (`src/services/`)
- `DatabaseService` (`db_service.py`): Raw SQLite interface, owns WAL-mode connection
- `repositories/`: One repository per domain object — `EventRepository`, `EntityRepository`, `RelationRepository`, `MapRepository`, `CalendarRepository`, `AttachmentRepository`, `TagRepository`, `TrajectoryRepository`, `MetaRepository` — all injected with `DatabaseService`
- `HistoryService`: Persists command history
- `BackupService`: Automated + manual backup with retention policy
- `AssetStore`: Image/icon import (WebP conversion), trash/restore for undo support
- `RAGService` (`rag_service.py`): Hybrid lexical + semantic search
- `EmbeddingService`: Vector embeddings via configurable backend
- `LLMProvider` (`llm_provider.py`) + `providers/`: Multi-backend AI (Anthropic, Google, OpenAI, LMStudio); `PromptBuilder`, `PromptLoader`, `ReasoningFilter`, `SummaryService`
- `SearchService`: Unified text search across domain objects
- `ImportService` / `ImportNormalization`: Data import pipeline
- `ObsidianExporter`: Export worlds to Obsidian vaults
- `GraphDataService`: Builds relation graph data for the graph view
- `WebServiceManager`: Manages the embedded FastAPI/uvicorn preview server (for longform)
- `AttachmentService`: File attachment management

**Core Layer** (`src/core/`)
Dataclass domain models: `Event`, `Entity`, `Relation`, `Calendar`, `Map`, `Marker`, `World`, `Trajectory`, `ImageAttachment`. Each has `to_dict()` / `from_dict()`. Key utilities:
- `ThemeManager` (singleton, loads `themes.json`), `StyleConstants`
- `CalendarConverter`, `TemporalManager`, `TemporalResolver`, `DateParser`, `ParsedDate`
- `LinkResolver` (moved to `src/services/link_resolver.py`)
- `RasterPresets`: Built-in color palette presets for raster layers
- `FastInject`: AI-assisted quick-fill data model
- `WikiAST`: Parsed representation of `[[wiki link]]` syntax
- `Protocols`: Shared structural typing interfaces
- `Paths`: Centralized path resolution for worlds/assets

**GUI Layer** (`src/gui/`)
- `widgets/` — all interactive panels and editors
  - `map/` — `MapGraphicsView`, GIS feature editing (paths, regions, markers), raster layer pipeline (`raster_layer_item`, `raster_edit_tool`, `raster_legend_widget`, `raster_mapping`, `raster_palette_editor`, `raster_probe_popup`, `raster_stats_panel`)
  - `timeline/` — `TimelineScene`, `TimelineView`, group band visualization
  - `longform/` — hierarchical document `editor.py` with outline/content split
  - `graph_view/` — force-directed relation graph (`GraphWidget`, `GraphBuilder`, `GraphWebView`)
- `dialogs/` — standalone modal dialogs (AI settings, import preview, raster queries, etc.)
- `mixins/` — reusable widget behaviors (`AutosaveMixin`, `EditorMixin`, `LayoutGuard`, map mixins)
- `models/` — Qt item models (`ExplorerModel`, `ExplorerFilterProxy`)
- `utils/` — helpers (`color_utils`, `geometry_utils`, `svg_utils`, `icon_loader`, `style_helper`, `shortcut_manager`)

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
- Use fully qualified PySide6 enum paths (e.g. `Qt.AlignmentFlag.AlignLeft`, not `Qt.AlignLeft`) — see `docs/PYSIDE6_ENUM_SOLUTION.md`
- Commit messages use conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `style:`, `test:`
- Tests use `pytest-qt` with offscreen Qt platform (`QT_QPA_PLATFORM=offscreen` set in `conftest.py`)
- `ThemeManager` is a singleton initialized in `conftest.py`; tests requiring it should use the `init_theme_manager` session fixture
