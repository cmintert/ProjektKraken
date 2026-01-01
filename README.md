---
**Project:** ProjektKraken  
**Document:** Main Project README  
**Last Updated:** 2026-01-01  
**Commit:** `d9e3f83`  
---

# Projekt Kraken

**Projekt Kraken** is a desktop worldbuilding environment designed for the "Architect" persona. It treats history as the primary axis of the world, offering a timeline-first approach to lore creation.

## Key Features

### Core Workflow
- **Timeline-First Design**: Events are first-class citizens with precise chronological data (cosmic to sub-day resolution)
- **Custom Calendar System**: Define worlds with custom months, weeks, and time tracking
- **Wiki-Style Linking**: `[[Entity Name]]` syntax with auto-completion and navigation
- **Relation Mapping**: Track relationships between events and entities with typed connections

### Visualization
- **Aeon-Style Timeline**: Lane-based event visualization with semantic zoom ruler
- **Interactive Maps**: Place markers on custom map images, link to entities/events
- **Longform Documents**: Hierarchical document structure for narrative prose

### Data & UI
- **Hybrid Data Model**: Strict SQL schema for relationships + flexible JSON attributes
- **Semantic Search**: Local embeddings with LM Studio for natural language queries
- **Dockable Workspace**: Configurable panels with state persistence
- **Theme Support**: Dark mode and custom themes via `ThemeManager`
- **Image Gallery**: Attach images to events and entities

## Installation

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # Linux/Mac
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### GUI Application

```bash
python -m src.app.main
```

### CLI Tools

ProjektKraken includes comprehensive command-line tools for headless operations:

```bash
# Events
python -m src.cli.event create --database world.kraken --name "Event" --date 100.0
python -m src.cli.event list --database world.kraken

# Entities  
python -m src.cli.entity create --database world.kraken --name "Character" --type character
python -m src.cli.entity list --database world.kraken

# Relations
python -m src.cli.relation add --database world.kraken --source <id> --target <id> --type "caused"

# Calendar Configuration
python -m src.cli.calendar show --database world.kraken
python -m src.cli.calendar set --database world.kraken --config calendar.json

# Maps
python -m src.cli.map list --database world.kraken
python -m src.cli.map create --database world.kraken --name "World Map" --image map.png

# Attachments
python -m src.cli.attachment list --database world.kraken --owner-type event --owner-id <id>

# Longform Export
python -m src.cli.longform export --database world.kraken --output document.md

# Wiki Link Scanning
python -m src.cli.wiki scan --database world.kraken --text "The [[Hero]] met [[Villain]]"

# Semantic Search
python -m src.cli.index rebuild --database world.kraken
python -m src.cli.index query --database world.kraken --text "find the wizard"
```

See **[CLI Documentation](src/cli/README.md)** for complete reference.

### Semantic Search

ProjektKraken includes local semantic search powered by LM Studio:

```bash
# Configure (one time)
export EMBED_PROVIDER=lmstudio
export LMSTUDIO_EMBED_URL=http://localhost:8080/v1/embeddings
export LMSTUDIO_MODEL=bge-small-en-v1.5

# Build search index
python -m src.cli.index rebuild --database world.kraken

# Query your world
python -m src.cli.index query --database world.kraken --text "ancient wizard"
```

See **[Semantic Search Documentation](docs/SEMANTIC_SEARCH.md)** for details.

See **[Semantic Search Documentation](docs/SEMANTIC_SEARCH.md)** for details.

## Troubleshooting

### Startup Crashes
If the application crashes immediately upon launch (even after updating versions), your local configuration settings might be corrupted. You can reset the window layout and preferences by running:

```bash
python launcher.py --reset-settings
```

This will clear the saved window state and reset the active database, allowing the application to launch with default settings. Use this with caution as it resets your workspace layout customization.

## Testing

Run the test suite:

```bash
pytest
```

With coverage:

```bash
pytest --cov=src --cov-report=term-missing
```

## Documentation

- **[CLI Tools](src/cli/README.md)** - Command-line interface reference
- **[Database Architecture](docs/DATABASE.md)** - Schema and data model
- **[Security Guidelines](docs/SECURITY.md)** - Security best practices
- **[Wiki Linking](docs/WIKI_LINKING.md)** - Wiki syntax and navigation
- **[Design Notes](Design.md)** - Architecture and design decisions

## Architecture

```
src/
├── app/          # Application entry point and main window
├── cli/          # Command-line tools (event, entity, relation, map, etc.)
├── commands/     # Undo/Redo command pattern implementation
├── core/         # Business logic, models, theme management
├── gui/          # PySide6 widgets
│   └── widgets/
│       ├── timeline/      # Timeline visualization
│       ├── map/           # Map and marker system  
│       ├── longform_editor.py
│       ├── wiki_text_edit.py
│       └── ...
├── resources/    # Icons, assets
└── services/     # Database and repository layer
```

## Technology

- **Python 3.11+**
- **PySide6** (Qt 6) for GUI
- **SQLite** for data persistence
- **pytest** for testing

## Version

**v0.4.0 (Alpha)**

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPLv3)**. 

AGPLv3 is a strong copyleft license that ensures that if you modify the software and run it on a server for others to interact with, you must share the source code of your modified version. See the [LICENSE](LICENSE) file for the full text.


