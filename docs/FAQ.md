# Frequently Asked Questions (FAQ)

**Version:** 0.11.0 (Beta)  
**Last Updated:** February 2026

Common questions, troubleshooting, and tips for using ProjektKraken.

---

## Table of Contents

1. [General Questions](#general-questions)
2. [Installation and Setup](#installation-and-setup)
3. [Features and Usage](#features-and-usage)
4. [Data Management](#data-management)
5. [Performance](#performance)
6. [Troubleshooting](#troubleshooting)
7. [Advanced Topics](#advanced-topics)

---

## General Questions

### What is ProjektKraken?

ProjektKraken is a **timeline-first desktop worldbuilding application** designed for writers, game masters, and worldbuilders. It helps you create and manage complex fictional worlds with precise chronological tracking and relationship mapping.

### Why "timeline-first"?

Unlike traditional wiki tools that treat dates as text, ProjektKraken treats time as a mathematical coordinate. This allows for:
- Precise chronological ordering
- Causal relationship tracking
- Timeline visualization
- Temporal queries and analysis

### Is ProjektKraken free?

Yes! ProjektKraken is **open-source** under the MIT License. You can use it freely for any purpose, including commercial projects.

### What platforms are supported?

- **Windows**: 10 or later
- **macOS**: 10.15 (Catalina) or later
- **Linux**: Ubuntu 20.04+ or equivalent

### Is an internet connection required?

No. ProjektKraken is **completely offline**. All data is stored locally on your computer. Internet is only needed for optional AI features (LLM generation) if using cloud providers.

### Where is my data stored?

- **Worlds**: In `worlds/` folder next to the application
- **User Settings**: System application data directory
  - Windows: `%APPDATA%\ProjektKraken\`
  - macOS: `~/Library/Application Support/ProjektKraken/`
  - Linux: `~/.local/share/ProjektKraken/`

### Can I collaborate with others?

Currently, ProjektKraken is designed for single-user workflows. However, you can:
- Share world folders manually
- Use Git for version control
- Export to formats others can import

---

## Installation and Setup

### What are the system requirements?

**Minimum:**
- 4 GB RAM
- 500 MB storage
- 1280x720 display

**Recommended:**
- 8+ GB RAM
- SSD storage
- 1920x1080+ display

### Do I need Python installed?

- **Windows Executable**: No, Python is bundled
- **Source Installation**: Yes, Python 3.13+ required

### The Windows executable won't run. What do I do?

**"Windows protected your PC" warning:**
1. Click "More info"
2. Click "Run anyway"

This is normal for unsigned executables.

**Still won't run:**
- Check Windows Event Viewer for error details
- Ensure Visual C++ Redistributable is installed
- Try running as administrator (right-click → Run as administrator)

### How do I update to a new version?

1. **Backup your worlds folder** (just in case)
2. Download new version
3. Replace old executable/files with new ones
4. Your world data remains compatible

### Can I install on a USB drive?

Yes! ProjektKraken is fully portable:
1. Extract to USB drive
2. Run from USB
3. All worlds store relative to executable

---

## Features and Usage

### How do I create wiki links?

Use double brackets: `[[Entity Name]]`

- Start typing `[[` to see autocomplete suggestions
- Links are case-sensitive
- Click links to navigate

### Can I use custom calendars?

Yes! **Edit → Calendar Settings** lets you configure:
- Month names and lengths
- Week structure (custom day names)
- Leap year rules
- Multiple year variants

### How precise can dates be?

Extremely precise:
- **Cosmic scale**: Millions of years
- **Human scale**: Years, months, days
- **Sub-day**: Hours, minutes, seconds

Internally stored as floats (1.0 = 1 day).

### What types of relations are supported?

Common types include:
- **caused** - Causal relationships
- **involved** - Participation
- **influenced** - Indirect effects
- **located_at** - Spatial relationships
- **member_of** - Membership
- **owns** - Ownership

You can also define custom relation types.

### Can I add images to entities?

Yes:
1. In Entity Editor, click **Add Image**
2. Select image file (PNG, JPG)
3. Image stored in `assets/images/` folder
4. Thumbnails auto-generated

### How does undo/redo work?

Every user action is a reversible command:
- **Undo**: Ctrl+Z
- **Redo**: Ctrl+Shift+Z
- History persists across app restarts
- View command history in History Panel

### What is semantic search?

Semantic search uses AI embeddings to find content by meaning, not just keywords:
- Query: "magical artifacts" finds items about magic, even without exact words
- Requires AI setup (LM Studio recommended for privacy)
- One-time indexing process

---

## Data Management

### How are worlds stored?

Each world is a self-contained folder:
```
worlds/
└── My World/
    ├── world.json           # Metadata
    ├── My World.kraken      # SQLite database
    └── assets/              # Images, files
```

### Can I rename a world?

Yes:
1. Close the world in ProjektKraken
2. Rename the world folder
3. Open `world.json` and update `"name"` field
4. Rename the `.kraken` file to match
5. Reopen in ProjektKraken

### Can I merge two worlds?

Not directly, but you can:
1. Export both worlds to JSON
2. Manually merge JSON files (resolve ID conflicts)
3. Import into new world

Alternatively, use Import feature to add entities from one world to another.

### What database does ProjektKraken use?

SQLite 3.35+ with:
- WAL mode for concurrency
- Hybrid schema (SQL + JSON attributes)
- Single-file portability

### Are automatic backups enabled?

Yes, by default:
- **Frequency**: Every 15 minutes
- **Location**: User data directory
- **Retention**: Configurable (default: 10 backups)

Manage via **Edit → Backup Settings**.

### How do I restore from backup?

1. **File → Restore World**
2. Select backup `.kraken` file
3. Confirm restoration
4. Current state is backed up automatically before restore

### Can I export my world?

Yes, multiple formats:
- **JSON**: Full data export
- **Obsidian**: Markdown wiki
- **Longform**: Narrative documents

---

## Performance

### The app feels slow with many entities. Help?

Optimization tips:

1. **Use Filtering**
   - Don't display all 10,000 entities at once
   - Filter by tags, type, or date range

2. **Limit Graph Depth**
   - In Graph View, reduce connection depth to 2-3

3. **Optimize Database**
   - **Tools → Database → Optimize**

4. **Close Unnecessary Panels**
   - Reduce open editors
   - Hide timeline when not needed

### Timeline rendering is laggy. What can I do?

- **Reduce visible date range**: Zoom in on specific period
- **Simplify group bands**: Reduce number of bands
- **Limit events on screen**: Use filtering
- **Lower display resolution**: If on 4K+ monitor

### Search is slow. How to speed it up?

- **Initial indexing takes time**: One-time process
- **Incremental updates**: Fast after initial index
- **Use local embeddings**: LM Studio faster than cloud APIs

### Graph view won't load. Why?

- **Too many nodes**: Filter to reduce count (< 1000 nodes)
- **Large relation count**: Simplify connections
- **Browser limitations**: Graph view uses web rendering

---

## Troubleshooting

### "Database is locked" error

**Causes:**
- Multiple ProjektKraken instances open
- Orphaned process from crash

**Solutions:**
1. Close all ProjektKraken instances
2. Check Task Manager (Windows) or Activity Monitor (macOS) for processes
3. Delete temporary files: `.kraken-shm` and `.kraken-wal` in world folder
4. Reopen application

### Changes aren't saving

**Check:**
- Auto-save is enabled (should be default)
- Disk has free space
- World folder has write permissions

**Force manual save:**
- Close and reopen world (triggers save)
- Use **File → Backup World** to confirm save works

### Wiki links aren't working

**Common issues:**
- **Case mismatch**: `[[Frodo]]` ≠ `[[frodo]]`
- **Entity doesn't exist**: Create entity first
- **Typo in name**: Use autocomplete (type `[[` to see options)

### Images aren't displaying

**Solutions:**
- Verify image file exists in `assets/images/` folder
- Check file format (PNG, JPG supported)
- Try re-adding image in editor
- Check file permissions

### Timeline playhead disappeared

- **View → Timeline → Reset View**
- Check playhead date isn't outside visible range
- Try zooming out to see full timeline

### Undo isn't working for a specific action

Some actions aren't undoable:
- UI layout changes
- Search queries
- Opening/closing worlds
- View/zoom changes

Most data changes (create/edit/delete) are undoable.

### Graph view shows wrong connections

**Refresh graph:**
1. Close Graph View
2. **Tools → Rebuild Graph Cache**
3. Reopen Graph View

**Check filters:**
- Ensure filters aren't hiding expected connections

---

## Advanced Topics

### Can I use custom fonts?

Not currently through UI, but you can:
1. Edit theme JSON files
2. Specify font families in stylesheets
3. Requires application restart

### Can I write custom scripts/plugins?

ProjektKraken has CLI tools (`src/cli/`) for scripting:

```bash
python -m src.cli.event list --world "My World"
python -m src.cli.entity create --name "New Character" --type character
```

Plugin system is planned for future releases.

### How does the AI integration work?

**Architecture:**
1. **Embeddings**: Text → vector representation
2. **Vector Storage**: Saved in database
3. **Similarity Search**: Find related content
4. **RAG**: Augment LLM with world context

**Privacy:**
- Local embeddings (LM Studio): Data never leaves your computer
- Cloud providers: Data sent to API (check provider's privacy policy)

### Can I use ProjektKraken for game data?

Yes! Common uses:
- **RPG Campaigns**: Track sessions, NPCs, quests
- **Game Development**: World lore, character backstories
- **Interactive Fiction**: Branching narratives, choices

### What about performance with 100,000+ entities?

Should work, but:
- Use aggressive filtering
- Consider splitting into multiple worlds (e.g., by era)
- Optimize database regularly
- Expect slower initial loads

### Can I self-host an AI API?

Yes! Use LM Studio:
1. Install LM Studio locally
2. Load a model (e.g., llama-2, mistral)
3. Start server in LM Studio
4. Configure ProjektKraken AI settings to use `http://localhost:1234`

### How do I report bugs or request features?

- **GitHub Issues**: [github.com/cmintert/ProjektKraken/issues](https://github.com/cmintert/ProjektKraken/issues)
- Provide:
  - Steps to reproduce
  - Expected vs actual behavior
  - System info (OS, version)
  - Error messages/logs if any

### Where can I get help?

- **Documentation**: [docs/INDEX.md](INDEX.md)
- **GitHub Discussions**: Ask questions, share tips
- **Discord**: Community server (link in README)

### How can I contribute?

See [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Code contributions
- Documentation improvements
- Bug reports
- Feature suggestions

---

## Tips and Tricks

### Speed Tips

- **Keyboard shortcuts**: Learn common shortcuts (Ctrl+Shift+E for events, etc.)
- **Quick create**: Use Fast Inject for rapid entity creation
- **Tag everything**: Makes filtering and finding easier later
- **Use templates**: Create template entities with common attributes

### Organization Tips

- **Consistent naming**: Use clear, consistent naming conventions
- **Tag hierarchies**: Use dot notation for nested tags (e.g., `faction.royal`, `faction.criminal`)
- **Document conventions**: Keep a "World Bible" entity with rules and conventions
- **Regular reviews**: Periodically review and clean up relations

### Workflow Tips

- **Start with events**: Create major events first, add entities later
- **Work chronologically**: Build timeline in order
- **Use graph view**: Discover missing connections
- **Export regularly**: Backup and export periodically

### AI Tips

- **Good prompts**: Be specific in AI queries
- **Context matters**: Select relevant entity before generating
- **Review output**: Always edit AI-generated content
- **Iterate**: Regenerate with different prompts if needed

---

## Still Have Questions?

- **Read the [User Guide](USER_GUIDE.md)** for detailed feature explanations
- **Check [Workflows](WORKFLOWS.md)** for step-by-step guides
- **Visit [GitHub Issues](https://github.com/cmintert/ProjektKraken/issues)** for technical questions

---

**Navigation:**  
[← Workflows](WORKFLOWS.md) • [Back to Index](INDEX.md) • [Architecture →](ARCHITECTURE.md)
