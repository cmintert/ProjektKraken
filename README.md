---
project: ProjektKraken
document: Main Project README
last_updated: 2026-01-13
commit: 0.6.0
---

# Projekt Kraken

**Projekt Kraken** is a desktop worldbuilding environment designed for the "Architect" persona. It treats history as the primary axis of the world, offering a timeline-first approach to lore creation.

## Portable-Only Architecture (v0.6.0+)

Starting with version 0.6.0, ProjektKraken uses a **portable-only architecture** where all worlds are stored next to the executable in a `worlds/` directory. Each world is completely self-contained.

### World Structure

```
ProjektKraken.exe              # Application executable (or project root in dev)
worlds/                        # Worlds directory (created automatically)
  My Fantasy World/            # World directory
    world.json                 # World manifest (metadata)
    My Fantasy World.kraken    # SQLite database
    assets/                    # World assets
      images/                  # Full-size images
        events/                # Event images by ID
        entities/              # Entity images by ID
      thumbnails/              # Image thumbnails
      .trash/                  # Deleted files (for undo)
  Another Campaign/            # Another world
    world.json
    Another Campaign.kraken
    assets/
      ...
```

### World Manifest (world.json)

Each world contains a `world.json` manifest file with metadata:

```json
{
  "id": "unique-uuid",
  "name": "My Fantasy World",
  "description": "An epic fantasy setting",
  "created_at": 1234567890.0,
  "modified_at": 1234567890.0,
  "version": "0.6.0",
  "db_filename": "My Fantasy World.kraken"
}
```

### User Preferences

User preferences (window layouts, settings) remain stored in the system's standard application data directory using QSettings:
- **Windows**: `%APPDATA%\ProjektKraken\`
- **macOS**: `~/Library/Application Support/ProjektKraken/`
- **Linux**: `~/.local/share/ProjektKraken/`

Backups and AI search indexes are also stored in the user data directory.

## Key Features

### Core Workflow
- **Timeline-First Design**: Events are first-class citizens with precise chronological data (cosmic to sub-day resolution)
- **Temporal Relations**: Advanced timeline logic with staging system and dynamic date overrides
- **Custom Calendar System**: Define worlds with custom months, weeks, and time tracking
- **Wiki-Style Linking**: `[[Entity Name]]` syntax with auto-completion and navigation
- **Relation Mapping**: Track relationships between events and entities with typed connections
- **Automated Backups**: Continuous auto-save with manual backup/restore functionality

### Visualization
- **Interactive Graph View**: Physics-based node graph with filtering, auto-updates, and force-directed layout
- **Temporal Maps 2.0**: Trajectory visualization (MF-JSON), reliable playhead persistence, and "Clock Mode" for precise temporal editing
- **Dual Timeline Views**: Lane-based graphic timeline + card-style text timeline
- **Longform Documents**: Hierarchical document structure for narrative prose
- **Return to Present**: Quick navigation to current timeline position

### AI & Search
- **Semantic Search**: Local embeddings with LM Studio for natural language queries
- **AI Panel**: Dedicated search interface with keyboard navigation
- **LLM Generation**: Context-aware content generation with RAG integration
- **Custom Prompts**: Configurable LLM prompts and personas

### Data & UI
- **Event-Driven Architecture**: Signal-based communication between components
- **Hybrid Data Model**: Strict SQL schema for relationships + flexible JSON attributes
- **Dockable Workspace**: Configurable panels with state persistence and layout management
- **Theme Support**: Dark mode and custom themes via `ThemeManager`

## Installation

### Windows Executable (Recommended)

Download the latest release from GitHub Releases. The application is portable - simply extract and run `ProjektKraken.exe`. The `worlds/` directory will be created automatically next to the executable on first run.

### From Source

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

**Developer / Advanced Options:**

- `--set-default-layout`: Launches the application in "Capture Mode". When you close the application, the current window layout is saved as the new factory default (to `src/assets/default_layout.json`).
- `--reset-settings`: Clears all persistent settings (window state, preferences) to defaults.

### CLI Tools

ProjektKraken includes comprehensive command-line tools for headless operations.

**Note:** In portable mode (v0.6.0+), database paths should point to the `.kraken` file within a world directory:

```bash
# Example world structure:
# worlds/My Campaign/My Campaign.kraken

# Events
python -m src.cli.event create --database "worlds/My Campaign/My Campaign.kraken" --name "Event" --date 100.0
python -m src.cli.event list --database "worlds/My Campaign/My Campaign.kraken"

# Or use shorter paths if you're in the project directory:
python -m src.cli.event list --database "worlds/My Campaign/My Campaign.kraken"

# Entities  
python -m src.cli.entity create --database "worlds/My Campaign/My Campaign.kraken" --name "Character" --type character
python -m src.cli.entity list --database "worlds/My Campaign/My Campaign.kraken"

# Relations
python -m src.cli.relation add --database "worlds/My Campaign/My Campaign.kraken" --source <id> --target <id> --type "caused"

# Calendar Configuration
python -m src.cli.calendar show --database "worlds/My Campaign/My Campaign.kraken"
python -m src.cli.calendar set --database "worlds/My Campaign/My Campaign.kraken" --config calendar.json

# Maps
python -m src.cli.map list --database "worlds/My Campaign/My Campaign.kraken"
python -m src.cli.map create --database "worlds/My Campaign/My Campaign.kraken" --name "World Map" --image map.png

# Attachments
python -m src.cli.attachment list --database "worlds/My Campaign/My Campaign.kraken" --owner-type event --owner-id <id>

# Longform Export
python -m src.cli.longform export --database "worlds/My Campaign/My Campaign.kraken" --output document.md

# Wiki Link Scanning
python -m src.cli.wiki scan --database "worlds/My Campaign/My Campaign.kraken" --text "The [[Hero]] met [[Villain]]"

# Semantic Search
python -m src.cli.index rebuild --database "worlds/My Campaign/My Campaign.kraken"
python -m src.cli.index query --database "worlds/My Campaign/My Campaign.kraken" --text "find the wizard"
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
- **[Backup Strategy](docs/BACKUP_STRATEGY.md)** - Backup and restore guide
- **[Temporal Relations](docs/TEMPORAL_RELATIONS.md)** - Timeline logic and staging system
- **[Semantic Search](docs/SEMANTIC_SEARCH.md)** - AI search and embeddings setup
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

**v0.6.0 (Beta)**

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPLv3)**. 

AGPLv3 is a strong copyleft license that ensures that if you modify the software and run it on a server for others to interact with, you must share the source code of your modified version. See the [LICENSE](LICENSE) file for the full text.


