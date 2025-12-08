# Projekt Kraken

**Projekt Kraken** is a desktop worldbuilding environment designed for the "Architect" persona. It treats history as the primary axis of the world, offering a timeline-first approach to lore creation.

## Key Features

*   **Timeline-First Workflow**: Events are first-class citizens with precise chronological data (cosmic to seconds).
*   **Aeon-Style Visualization**: specific graphical view with "Lanes", "Rulers", and intuitive interactions (Pan/Zoom).
*   **Context-Aware UI**: "Trinity" view system (Editor, Timeline, Relations).
*   **Configurable Workspace**: Dockable panels with state persistence and "View" menu control.
*   **Hybrid Data Model**: Strict SQL schema for relationships mixed with flexible JSON attributes for world data.
*   **Modern UI**: Dark mode support via `ThemeManager`, responsive layouts, and clean typography.

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

Run the main application:

```bash
python -m src.app.main
```

## Testing

Run the test suite with coverage:

```bash
pytest --cov=src --cov-report=term-missing
```

Current Test Coverage: **>95%** (Core, GUI, Interactions).

## Architecture

*   **Core**: `src/core` - Business logic, Event models, ThemeManager.
*   **GUI**: `src/gui` - PySide6 widgets (Timeline, EventEditor, EventList).
*   **Services**: `src/services` - SQLite database interactions.
*   **Commands**: `src/commands` - Undo/Redo command pattern implementation.

## Status

*   **Phase 1 (MVP)**: Complete.
*   **Phase 2 (Editor)**: Complete.
*   **Phase 3 (Navigation)**: Complete.
*   **Phase 4 (UI/UX)**: Complete.
*   **Phase 5 (Docs)**: In Progress.
