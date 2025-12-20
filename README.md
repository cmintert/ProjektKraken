# Projekt Kraken

**Projekt Kraken** is a desktop worldbuilding environment designed for the "Architect" persona. It treats history as the primary axis of the world, offering a timeline-first approach to lore creation.

## Key Features

*   **Timeline-First Workflow**: Events are first-class citizens with precise chronological data (cosmic to seconds).
*   **Aeon-Style Visualization**: specific graphical view with "Lanes", "Rulers", and intuitive interactions (Pan/Zoom).
*   **Context-Aware UI**: "Trinity" view system (Editor, Timeline, Relations).
*   **Configurable Workspace**: Dockable panels with state persistence and "View" menu control.
*   **Hybrid Data Model**: Strict SQL schema for relationships mixed with flexible JSON attributes for world data.
*   **Modern UI**: Dark mode support via `ThemeManager`, responsive layouts, and clean typography.
*   **CLI Tools**: Full-featured command-line interface for headless operations, automation, and scripting.

## Installation

1.  Clone the repository.
2.  Create a virtual environment:
    ```bash
    python -m venv .venv
    .venv\Scripts\activate
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

### GUI Application

Run the main application:

```bash
python -m src.app.main
```

### CLI Tools

ProjektKraken includes comprehensive command-line tools for headless operations:

```bash
# Manage events
python -m src.cli.event create --database world.kraken --name "Event" --date 100.0
python -m src.cli.event list --database world.kraken

# Manage entities
python -m src.cli.entity create --database world.kraken --name "Entity" --type character
python -m src.cli.entity list --database world.kraken

# Manage relations
python -m src.cli.relation add --database world.kraken --source <id> --target <id> --type "caused"

# Export longform documents
python -m src.cli.export_longform world.kraken output.md
```

See **[CLI Documentation](src/cli/README.md)** for complete reference.

## Testing

Run the test suite with coverage:

```bash
pytest --cov=src --cov-report=term-missing
```

Current Test Coverage: **>95%** (Core, GUI, Interactions).

### Code Quality

- **Docstring Coverage**: 100% (Google Style)
- **Security**: Zero SQL injection vulnerabilities
- **PEP 8**: 99.6% compliant
- **Type Hints**: Comprehensive throughout codebase

See [CODE_REVIEW_SUMMARY.md](CODE_REVIEW_SUMMARY.md) for detailed assessment.

## Documentation

- **[CLI Tools](src/cli/README.md)**: Command-line interface reference
- **[DATABASE.md](docs/DATABASE.md)**: Database architecture and best practices
- **[SECURITY.md](docs/SECURITY.md)**: Security guidelines and best practices
- **[Design.md](Design.md)**: Architecture and design decisions
- **[SENIOR_ARCHITECT_REVIEW.md](SENIOR_ARCHITECT_REVIEW.md)**: Comprehensive architectural review and refactoring report

## Architecture

*   **Core**: `src/core` - Business logic, Event models, BaseThemeManager (headless) and ThemeManager (Qt).
*   **GUI**: `src/gui` - PySide6 widgets (Timeline, EventEditor, EventList).
*   **CLI**: `src/cli` - Command-line tools for headless operations.
*   **Services**: `src/services` - SQLite database interactions.
*   **Commands**: `src/commands` - Undo/Redo command pattern implementation (shared by GUI and CLI).

## Status

*   **Phase 1 (MVP)**: Complete.
*   **Phase 2 (Editor)**: Complete.
*   **Phase 3 (Navigation)**: Complete.
*   **Phase 4 (UI/UX)**: Complete.
*   **Phase 5 (Docs)**: In Progress.
