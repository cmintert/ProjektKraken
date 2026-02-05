# Frequently Asked Questions (FAQ)

Common questions and solutions for ProjektKraken users.

## Table of Contents

1. [General Questions](#general-questions)
2. [Installation & Setup](#installation--setup)
3. [Using the Application](#using-the-application)
4. [Data & Files](#data--files)
5. [Features & Functionality](#features--functionality)
6. [Performance & Troubleshooting](#performance--troubleshooting)
7. [Advanced Topics](#advanced-topics)

---

## General Questions

### What is ProjektKraken?

ProjektKraken is a desktop worldbuilding application designed for creators who treat history as the primary axis of their world. It offers timeline-first worldbuilding with precise chronology, custom calendars, wiki-style linking, and interactive visualizations.

### Who is ProjektKraken for?

ProjektKraken is designed for the "Architect" persona - worldbuilders who value:
- Precise timeline management
- Complex relationship tracking
- Spatial and temporal visualization
- Local-first, offline operation
- Data ownership and portability

Ideal for:
- Fantasy/sci-fi writers
- Tabletop RPG game masters
- Worldbuilding hobbyists
- Campaign planners
- Lore documentarians

### How is ProjektKraken different from Obsidian, World Anvil, or other tools?

**vs. Obsidian:**
- Native WYSIWYG editor (no Edit/Read mode switching)
- Built-in timeline visualization
- Temporal mapping (4D maps)
- Custom calendar system
- Native date/time handling

**vs. World Anvil:**
- Fully offline and local
- No subscription required
- Portable data (own your files)
- More flexible data model
- Desktop-first design

**vs. General Note-Taking Apps:**
- Timeline-first approach
- Event-driven worldbuilding
- Temporal relations
- Graph visualization
- Map integration

### Is ProjektKraken free?

Yes, ProjektKraken is free and open source under the GPLv3 license. You can use, modify, and distribute it freely under the terms of the license.

### What platforms does ProjektKraken support?

- **Windows** 10+ (executable available)
- **macOS** 10.15+
- **Linux** (Ubuntu 20.04+ or equivalent)

Runs from source on all platforms with Python 3.11+.

### Can I use ProjektKraken for commercial projects?

Yes! Under the GPLv3 license, you can use ProjektKraken for commercial worldbuilding projects. The license applies to the application itself, not to the worlds you create with it. Your world data is yours.

---

## Installation & Setup

### The application won't start. What should I do?

1. **Try resetting settings:**
   ```bash
   python launcher.py --reset-settings
   ```

2. **Check for error messages:**
   - Run from terminal/command prompt to see error output
   - Look for missing dependencies

3. **Verify Python version** (if running from source):
   ```bash
   python --version  # Should be 3.11 or higher
   ```

4. **Reinstall dependencies** (if running from source):
   ```bash
   pip install -r requirements.txt --force-reinstall
   ```

### I get "ModuleNotFoundError: No module named 'PySide6'"

This means Python dependencies aren't installed.

**Solution:**
```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### How do I update ProjektKraken?

**Executable Version:**
1. Download new version from GitHub Releases
2. Extract to new folder or replace old files
3. Your `worlds/` folder is safe (copy it if needed)

**Source Version:**
```bash
cd ProjektKraken
git pull origin main
pip install -r requirements.txt --upgrade
```

### Where is my data stored?

**World Data:**
- Stored in `worlds/` folder next to executable (or project root in dev)
- Each world is a self-contained folder with `.kraken` database and assets

**User Settings:**
- Windows: `%APPDATA%\ProjektKraken\`
- macOS: `~/Library/Application Support/ProjektKraken/`
- Linux: `~/.local/share/ProjektKraken/`

### Can I move my worlds to another computer?

Yes! Worlds are fully portable:

1. Copy the entire world folder (e.g., `worlds/My Fantasy World/`)
2. Paste into the `worlds/` folder on the new computer
3. Open the world in ProjektKraken

All data, images, and settings are preserved.

---

## Using the Application

### How do I create my first world?

1. Launch ProjektKraken
2. Click **File → New World** (or `Ctrl+N`)
3. Enter world name and optional description
4. Click **Create**
5. Start adding events and entities!

See [User Guide - Getting Started](USER_GUIDE.md#getting-started) for details.

### What's the difference between Events and Entities?

**Events:**
- Represent moments or periods in time
- Have a date and optional duration
- Examples: battles, discoveries, celebrations

**Entities:**
- Represent people, places, things, or concepts
- Exist across time (not tied to a specific moment)
- Examples: characters, locations, factions, artifacts

### How do I add images to entities or events?

1. Select the entity or event in the editor
2. Click the **Gallery** tab
3. Click **Add Image**
4. Select one or more images from your files
5. Optionally add captions

Images are stored in `worlds/[World Name]/assets/images/`.

### How do I create relationships between entities?

1. Select the source entity in the editor
2. Scroll to the **Relations** section
3. Click **Add Relation**
4. Select the target entity
5. Choose relation type (e.g., "member_of", "rules", "located_in")
6. Optionally add start/end dates
7. Click **Add**

### What are wiki links and how do I use them?

Wiki links use the syntax `[[Entity Name]]` to link to entities from any description field.

**To create a link:**
1. Type `[[` in any description field
2. Autocomplete appears with entity list
3. Select entity or type name
4. Type `]]` to close

**To follow a link:**
- Ctrl+Click (or Cmd+Click on Mac)

### How do I undo a mistake?

- Press `Ctrl+Z` to undo
- Press `Ctrl+Y` or `Ctrl+Shift+Z` to redo
- View full history: **View → History Panel**

Undo history is saved with your world.

### Can I customize the calendar?

Yes! Custom calendars are a core feature.

1. Click **Tools → Calendar Settings**
2. Click **New Calendar**
3. Define months (names and day counts)
4. Define weeks (day names)
5. Add leap year rules (optional)
6. Click **Save** and **Set Active**

All dates now use your custom calendar.

### How do I zoom in/out on the timeline?

- **Mouse wheel** while hovering over timeline
- **Zoom buttons** in timeline toolbar
- **Keyboard**: `Ctrl++` (zoom in) / `Ctrl+-` (zoom out)

---

## Data & Files

### What file format does ProjektKraken use?

- **Database**: SQLite (`.kraken` files)
- **World Manifest**: JSON (`world.json`)
- **Images**: Standard formats (JPG, PNG, GIF, BMP)
- **Backups**: ZIP or JSON

### Can I edit the database directly?

Technically yes (it's SQLite), but **not recommended**. Direct database editing can corrupt your world. Use the application or CLI tools instead.

### How do I backup my world?

**Manual Backup:**
1. **File → Backup World**
2. Choose location and format
3. Click **Backup**

**Automated Backups:**
- Automatic backups run periodically
- Stored in user data directory
- Configurable retention policy

**Manual Copy:**
- Simply copy the entire world folder

### How do I restore from a backup?

1. **File → Restore World**
2. Select backup file
3. Choose restoration method:
   - **Full Restore**: Replace entire world
   - **Import**: Merge with existing world
4. Confirm

### Can I export my world to other formats?

Yes!

**JSON Export:**
- **File → Export → To JSON**
- Portable, text-based format

**Obsidian Export:**
- **File → Export → To Obsidian**
- Markdown files with wiki links

**Longform Export:**
- **File → Export → Longform as Markdown/HTML**
- For narrative documents

### How do I import data from external sources?

1. Prepare JSON file with entities, events, and relations
2. **File → Import → From JSON**
3. Choose import mode (merge, replace, update)
4. Click **Import**

See [User Guide - Import and Export](USER_GUIDE.md#import-and-export) for format details.

---

## Features & Functionality

### How do I create a temporal map?

1. **Create a map:**
   - Tools → Create Map
   - Name and select image file

2. **Add markers:**
   - Right-click map → Add Marker
   - Select entity

3. **Create trajectory:**
   - Select entity on map
   - Click **Add Trajectory Keyframe**
   - Set position and time
   - Repeat for multiple positions

4. **Enable Clock Mode:**
   - Click **Clock Mode** in map toolbar
   - Drag timeline playhead to see marker move

### What is Semantic Search and how do I use it?

Semantic Search uses AI embeddings to find entities and events by meaning, not just keywords.

**Setup:**
1. Install LM Studio
2. Download embedding model (e.g., bge-small-en-v1.5)
3. Start local server
4. Build index: `python -m src.cli.index rebuild --database world.kraken`

**Usage:**
1. Open **View → AI Search** (`Ctrl+Shift+F`)
2. Enter natural language query: "ancient wizard with staff"
3. View ranked results

See [User Guide - Semantic Search](USER_GUIDE.md#semantic-search-and-ai) for details.

### What is Fast Inject?

Fast Inject allows rapid entity/event creation using templates with variable substitution.

**Example:**
1. Create template: `fastinject/npc_template.json`
2. **Tools → Fast Inject**
3. Select template
4. Fill variables (name, role, location, etc.)
5. Click **Create**

Useful for populating worlds with many similar entities (NPCs, locations, etc.).

### How do I use the Graph View?

1. **View → Graph View** (or click Graph tab)
2. Nodes represent entities and events
3. Edges show relations
4. **Interact:**
   - Click node to select
   - Drag to pan
   - Mouse wheel to zoom
   - Drag node to reposition
5. **Filter:**
   - Click Filter button
   - Show/hide types, relations, tags

### Can I write longform narrative documents?

Yes! ProjektKraken includes a longform editor.

1. **File → New Longform Document**
2. Create hierarchical outline (chapters, sections)
3. Write rich text content
4. Use wiki links to reference world data
5. **File → Export → Longform as Markdown/HTML**

### How do I set up undo/redo?

Undo/redo is enabled by default. Just use `Ctrl+Z` / `Ctrl+Y`.

**View History:**
- **View → History Panel**
- Shows all commands with visual timeline
- Click any command to jump to that state

---

## Performance & Troubleshooting

### The application is running slowly. What can I do?

1. **Filter data:**
   - Use filters to focus on relevant data
   - Hide unused panels

2. **Reduce graph complexity:**
   - Filter graph by depth
   - Hide relation types
   - Limit visible nodes

3. **Optimize database:**
   - Close and reopen world (runs VACUUM)
   - Remove unused attachments

4. **Check system resources:**
   - Close other applications
   - Ensure adequate RAM

### The graph view is laggy.

1. **Reduce visible nodes:**
   - Filter by type or tag
   - Limit depth from selected node

2. **Pause physics simulation:**
   - Click Pause button in graph toolbar

3. **Use static layout:**
   - Arrange nodes manually
   - Pause simulation to freeze

### I deleted something by accident. How do I recover it?

1. **Use Undo:** Press `Ctrl+Z` immediately
2. **Check History Panel:**
   - **View → History Panel**
   - Find delete command
   - Click earlier command to restore
3. **Restore from Backup:**
   - If undo history is cleared, use backup

### Import failed with "Cycle Resolution Error"

This occurs when imported data has circular dependencies.

**Solution:**
The import system should handle this automatically with two-pass resolution. If it fails:
1. Check JSON structure for invalid relations
2. Try importing in smaller batches
3. Manually resolve circular references

### Timeline shows wrong dates.

1. **Check active calendar:**
   - **Tools → Calendar Settings**
   - Verify correct calendar is active

2. **Check date format:**
   - Dates stored as floats (1.0 = 1 day)
   - Verify float values are correct

3. **Reset calendar converter:**
   - Close and reopen world

---

## Advanced Topics

### Can I use ProjektKraken with version control (Git)?

Yes! Worlds can be tracked with Git.

**Recommended `.gitignore`:**
```
*.pyc
__pycache__/
.venv/
worlds/*/assets/images/*/  # Optional: exclude large images
worlds/*/assets/thumbnails/
```

**Track:**
- `.kraken` database files
- `world.json` manifests
- Documentation

**Note:** Binary database files don't diff well. Consider exporting to JSON for better diffs.

### Can I write custom scripts or plugins?

Currently, ProjektKraken doesn't have a plugin API, but you can:

1. **Use CLI tools:** Automate tasks via command line
2. **Direct database access:** Use SQLite tools (carefully!)
3. **Fork and modify:** It's open source (GPLv3)

Future versions may include plugin support.

### How do I contribute to ProjektKraken?

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

**Quick Start:**
1. Fork the repository
2. Clone your fork
3. Create a feature branch
4. Make changes
5. Run tests: `pytest`
6. Submit pull request

### Can I use the CLI tools without the GUI?

Yes! ProjektKraken includes comprehensive CLI tools for headless operations.

**Examples:**
```bash
# List events
python -m src.cli.event list --database world.kraken

# Create entity
python -m src.cli.entity create --database world.kraken --name "Character" --type character

# Query semantic search
python -m src.cli.index query --database world.kraken --text "ancient wizard"
```

See [User Guide - CLI Tools](USER_GUIDE.md#cli-tools) for full reference.

### How do I report bugs or request features?

1. **Check existing issues:** [GitHub Issues](https://github.com/cmintert/ProjektKraken/issues)
2. **Create new issue:**
   - Bug: Include steps to reproduce, error messages, system info
   - Feature: Describe use case and desired behavior
3. **Discussion:** Use GitHub Discussions for questions

### Where can I find the source code?

GitHub: [https://github.com/cmintert/ProjektKraken](https://github.com/cmintert/ProjektKraken)

### Is there a user community?

Check the GitHub repository for:
- GitHub Discussions
- Issue tracker
- Wiki (if available)

### Can I hire someone to add custom features?

ProjektKraken is open source. You can:
1. Fork and modify yourself
2. Hire a developer to create custom fork
3. Submit feature request and wait for community implementation
4. Contribute code yourself

---

## Still Need Help?

- **Documentation:** [User Guide](USER_GUIDE.md)
- **Tutorials:** [Workflows](WORKFLOWS.md)
- **Setup:** [Installation Guide](INSTALLATION.md)
- **Technical:** [Development Guide](DEVELOPMENT.md)
- **GitHub Issues:** [Report Bugs](https://github.com/cmintert/ProjektKraken/issues)

---

**Can't find your question?** Open an issue on GitHub with your question.
