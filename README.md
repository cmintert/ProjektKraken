---
project: ProjektKraken
document: Main Project README
last_updated: 2026-10-21
---

# Projekt Kraken

## Version

**v0.20.1 (Beta)**
**Projekt Kraken** is a desktop worldbuilding environment designed for the "Architect" persona. It treats history as the primary axis of the world, offering a timeline-first approach to lore creation.

## Screenshot

![Layout](<Screenshot 2026-10-20 094912.png>)

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

The Windows release stores user preferences (window layouts and settings)
locally using QSettings, separately from portable world folders.

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
- **Return to Current Time**: Quick navigation back to the current story time

### AI & Search
- **Semantic Search**: Local embeddings with LM Studio for natural language queries
- **AI Panel**: Dedicated search interface with keyboard navigation
- **LLM Generation**: Context-aware content generation with RAG integration
- **Portable Task Templates**: Read-only authoring presets plus custom per-world tasks

### Data & UI
- **Event-Driven Architecture**: Signal-based communication between components
- **Hybrid Data Model**: Strict SQL schema for relationships + flexible JSON attributes
- **Unified Workspace**: Movable panels across four stable zones with explicit layout persistence
- **Theme Support**: Dark mode and custom themes via `ThemeManager`
- **Fast Inject**: Rapid entity/event creation with template support and variable resolution
- **Focused Writing**: A centered writing surface for Event and Entity descriptions
- **Temporal Entity Editing**: Correct visible historical descriptions and attributes
  at their baseline or dated source
- **Reviewed Import and Export**: JSON, CSV, TSV, Markdown, publishing formats,
  backups, and portable-world transfer

## Installation

### Windows Executable (Recommended)

1. Download the Windows x64 ZIP and its `.sha256` file from
   [GitHub Releases](https://github.com/cmintert/ProjektKraken/releases).
2. Verify the download in PowerShell:

   ```powershell
   Get-FileHash .\ProjektKraken-0.20.1-beta1-windows-x64.zip -Algorithm SHA256
   ```

   The reported hash must match the value in the downloaded `.sha256` file.
3. Extract the complete ZIP into an ordinary user folder. Keep the
   `ProjektKraken` folder and its `_internal` folder together.
4. Open the extracted `ProjektKraken` folder and double-click
   `ProjektKraken.exe`.

No Python installation or command line is required. The portable `worlds/`
directory is created beside the executable on first launch.
See the [beta release notes](docs/releases/0.20.1-beta1.md) for known
limitations and safe update guidance.

### From Source

Source checkout setup and launch commands are documented in the
[developer setup guide](docs/developer/development.md).

## Usage

### GUI Application

Open the extracted `ProjektKraken` folder and double-click
`ProjektKraken.exe`. Keep `_internal` beside the executable; moving only the
`.exe` will prevent the application from starting.

**Developer / Advanced Options:**

- `--reset-settings`: Clears all persistent settings (window state, preferences) to defaults.

### CLI Tools

Source checkouts include offline command-line tools for existing world folders.
Use Python 3.13 or newer with project dependencies, and close the desktop app
before writing through the CLI.

```text
python -m src.cli.cli entity list --database "worlds/My Campaign/My Campaign.kraken" --json
python -m src.cli.cli info show --database "worlds/My Campaign/My Campaign.kraken"
```

See the **[CLI reference](docs/reference/cli.md)** for supported actions,
options, import targeting, and limitations.

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
Confirm that the complete ZIP was extracted and that `_internal` remains beside
`ProjektKraken.exe`. Normal application diagnostics are written to
`logs/kraken.<process ID>.log` beside the executable. If the application opens
but its layout is unusable, choose **Layouts → Reset Layout**. See the
[troubleshooting guide](docs/user/troubleshooting.md) for further checks.

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
- **[User Manual](docs/user/index.md)** - Current menus, workspace panels, and workflows
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

**v0.20.1 (Beta)**

## License

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**.

GPLv3 is a strong copyleft license that ensures that if you distribute the software, you must share the source code. It is fully compatible with PySide6 (LGPLv3). See the [LICENSE](LICENSE) file for the full text.


