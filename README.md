---
project: ProjektKraken
document: Main Project README
last_updated: 2026-07-27
---

# Projekt Kraken

## Version

**v0.19.0 (Beta)**
**Projekt Kraken** is a desktop worldbuilding environment designed for the "Architect" persona. It treats history as the primary axis of the world, offering a timeline-first approach to lore creation.

## Screenshot

![Layout](<Screenshot 2026-02-08 174625.png>)

## Portable World Architecture

ProjektKraken creates worlds in the `worlds/` directory next to the executable by
default. You can also register a complete world folder on a local or removable
drive, mapped drive, UNC share, or synchronized folder. Keeping the manifest,
database, and assets together is the recommended and fully portable model.

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

### Advanced External Databases

World Manager can deliberately link a manifest to an existing `.kraken` database
outside its world folder. This advanced configuration requires confirmation of the
fully resolved path. Approval is stored in local application settings and can be
revoked; it is not trusted merely because it appears in a transferable manifest.

External databases reduce portability and can separate assets from backups. A
missing external database is never recreated automatically. File synchronization
can cause conflicts, and SQLite databases on network storage must not be edited by
multiple users simultaneously.

## Key Features

### Core Workflow
- **Timeline-First Design**: Events are first-class citizens with precise chronological data (cosmic to sub-day resolution)
- **Temporal Relations**: Advanced timeline logic with staging system and dynamic date overrides
- **Custom Calendar System**: Define worlds with custom months, weeks, and time tracking
- **Natural Language Dates**: Intuitive date entry (e.g., "1st of Summer", "2 weeks later") with parser integration
- **Wiki-Style Linking**: `[[Entity Name]]` syntax with auto-completion and navigation
- **Relation Mapping**: Track relationships between events and entities with typed connections
- **Automated Backups**: Continuous auto-save with manual backup/restore functionality

### Visualization
- **Interactive Graph View**: Physics-based node graph with filtering, auto-updates, and force-directed layout
- **Temporal Maps 2.0**: Direct spatial and date editing, atomic undo, speed equalization, and reliable playhead persistence
- **Timeline Context**: Lane-based world timeline plus related-event summaries
  inside entity inspectors
- **Longform Documents**: Hierarchical document structure for narrative prose
- **Return to Present**: Quick navigation to current timeline position

### AI & Search
- **Semantic Search**: Local embeddings with LM Studio for natural language queries
- **AI Panel**: Dedicated search interface with keyboard navigation
- **LLM Generation**: Context-aware content generation with RAG integration
- **Portable Task Templates**: Read-only authoring presets plus custom per-world tasks

### Data & UI
- **Event-Driven Architecture**: Signal-based communication between components
- **Hybrid Data Model**: Strict SQL schema for relationships + flexible JSON attributes
- **Dockable Workspace**: Configurable panels with state persistence and layout management
- **Theme Support**: Dark mode and custom themes via `ThemeManager`
- **Fast Inject**: Rapid entity/event creation with template support and variable resolution
- **Advanced Import**: Two-pass JSON import strategy with deduplication and cycle resolution

## Installation

### Windows Executable (Recommended)

Download the latest release from GitHub Releases. The application is portable - simply extract and run `ProjektKraken.exe`. The `worlds/` directory will be created automatically next to the executable on first run.

### From Source

1. Clone the repository
2. Install Python **3.13 or newer**.
3. Create a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # Linux/Mac
   ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### GUI Application

On Windows, double-click `start-kraken.cmd`, or run it from a terminal:

```powershell
.\start-kraken.cmd
```

The launcher prefers `.venv`, verifies Python 3.13 and the runtime dependencies,
then starts the application. The underlying cross-platform entry point remains:

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

# Data Import
python -m src.app.main import --file "data/backup.json" --mode update
```

See **[CLI Documentation](src/cli/README.md)** for complete reference.

### Semantic Search

ProjektKraken includes local semantic search powered by LM Studio:

```bash
# Configure (one time)
export EMBED_PROVIDER=lmstudio
export LMSTUDIO_EMBED_URL=http://localhost:1234/v1/embeddings
export LMSTUDIO_MODEL=bge-small-en-v1.5

# Build search index
python -m src.cli.index rebuild --database world.kraken

# Query your world
python -m src.cli.index query --database world.kraken --text "ancient wizard"
```

See the **[Search, AI, and Analysis guide](docs/user/search-ai-and-analysis.md)**
for desktop and command-line setup guidance.

For desktop AI features, open **Tools → AI Settings**, enter the LM Studio
server address (for example `http://localhost:1234`), and select **Refresh
Models**. Choose one loaded text-generation model and, if semantic search uses
LM Studio, one embedding-capable model. ProjektKraken derives the individual
`/v1` endpoints; do not paste a completion or embedding endpoint into the
server field. Cloud generation providers remain visible but disabled until
their adapters meet the same reply and cancellation contract.

## Troubleshooting

### Startup Crashes
The Windows launcher shows an actionable error and writes full startup details to
`logs/startup_error.log`. Normal application diagnostics are in `logs/kraken.log`.
During source development, `logs/` is in the repository root; packaged builds keep
it beside `ProjektKraken.exe`.

If the application crashes after a layout or settings change, reset the window
layout and preferences by running:

```powershell
.\start-kraken.cmd --reset-settings
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

**📚 [Complete Documentation](docs/index.md)**

### Quick Start
- **[Getting Started](docs/user/getting-started.md)** - Launch, worlds, and the
  first editing workflow
- **[User Manual](docs/user/index.md)** - Current menus, docks, and workflows
- **[Maps, Layers, and Rasters](docs/user/maps.md)** - Drawing, nesting,
  temporal states, queries, and calibration
- **[Troubleshooting](docs/user/troubleshooting.md)** - Startup, layout, AI,
  and raster guidance

### For Developers
- **[Architecture](docs/developer/architecture.md)** - Dependency, coordinator,
  command, and threading contracts
- **[Development Guide](docs/developer/development.md)** - Environment and
  quality commands
- **[Database and Storage](docs/developer/database-and-storage.md)** - Portable
  worlds and persistence rules
- **[Testing Guide](docs/developer/testing.md)** - Tests, fixtures, and Qt
  hazards
- **[Contributing Guide](docs/developer/contributing.md)** - Contribution
  workflow

### Historical Documentation

Superseded manuals and implementation notes are retained under
`archive/documentation/` and are not published by Sphinx.

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

- **Python 3.13+**
- **PySide6** (Qt 6) for GUI
- **SQLite** for data persistence
- **pytest** for testing

## Map Editing

The current drawing, vertex-editing, snapping, raster, calibration, and
master/detail-map workflows are documented in the
**[Maps, Layers, and Rasters guide](docs/user/maps.md)**.

## Version

**v0.19.0 (Beta)**

## License

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**.

GPLv3 is a strong copyleft license that ensures that if you distribute the software, you must share the source code. It is fully compatible with PySide6 (LGPLv3). See the [LICENSE](LICENSE) file for the full text.


