# ProjektKraken Documentation

Welcome to the ProjektKraken documentation! This guide will help you get started with worldbuilding using ProjektKraken, a desktop application designed for timeline-first narrative creation.

## What is ProjektKraken?

**ProjektKraken** (v0.10.3 Beta) is a desktop worldbuilding environment designed for the "Architect" persona - creators who treat history as the primary axis of their world. Unlike traditional wiki-tools that treat lore as static text, ProjektKraken treats time as a mathematical coordinate, allowing for precise timeline visualization and causal relationships.

### Key Philosophy

- **Timeline-First Design**: Events are first-class citizens with precise chronological data
- **Local-First**: Your world lives in a folder on your disk, not in a cloud database
- **Portable**: All worlds are self-contained and stored next to the executable
- **Context-Aware UI**: Selecting an object updates multiple linked views (Timeline, Graph, Inspector)

## Quick Links

### User Documentation

- **[Installation Guide](INSTALLATION.md)** - How to install and set up ProjektKraken
- **[User Guide](USER_GUIDE.md)** - Complete user manual for all features
- **[Workflows](WORKFLOWS.md)** - Common use cases and step-by-step tutorials
- **[FAQ](FAQ.md)** - Frequently asked questions and troubleshooting

### Technical Documentation

- **[Architecture](ARCHITECTURE.md)** - System design and architectural patterns
- **[Development Guide](DEVELOPMENT.md)** - Developer setup and coding standards
- **[API Reference](API.md)** - Code reference and API documentation
- **[Database Schema](DATABASE.md)** - Database structure and data model
- **[Testing Guide](TESTING.md)** - Testing practices and guidelines
- **[Contributing](CONTRIBUTING.md)** - How to contribute to the project

## Core Features at a Glance

### Timeline & Events
- **Precise Chronology**: Cosmic to sub-day resolution
- **Custom Calendars**: Define your own months, weeks, and time tracking
- **Natural Language Dates**: Enter dates like "1st of Summer" or "2 weeks later"
- **Dual Timeline Views**: Lane-based graphic timeline + card-style text timeline

### Entities & Relations
- **Entity Types**: Characters, locations, factions, artifacts, concepts
- **Typed Relations**: Track relationships with categories (caused, located_in, involved, etc.)
- **Interactive Graph**: Physics-based node graph with filtering

### Advanced Features
- **Temporal Maps**: 4D mapping where entities move across maps over time
- **Wiki Linking**: `[[Entity Name]]` syntax with auto-completion
- **Semantic Search**: Local AI-powered search with LM Studio
- **Undo/Redo**: Full command history with visual interface
- **Fast Inject**: Rapid creation using templates
- **Longform Documents**: Hierarchical document structure for narrative prose

### Data Management
- **Hybrid Data Model**: Strict SQL schema + flexible JSON attributes
- **Automated Backups**: Continuous auto-save with manual backup/restore
- **Import/Export**: JSON import with deduplication and cycle resolution
- **Portable Architecture**: Self-contained world folders

## Getting Started

### Quick Start (3 Steps)

1. **Install ProjektKraken**
   - Download the latest release or run from source
   - See [Installation Guide](INSTALLATION.md)

2. **Create Your First World**
   - Launch the application
   - Click **File → New World**
   - Choose a template or start blank

3. **Learn the Basics**
   - Follow the [User Guide](USER_GUIDE.md)
   - Try the [Workflows](WORKFLOWS.md) tutorials
   - Explore the interface

### For Developers

If you want to contribute or extend ProjektKraken:

1. Read the [Development Guide](DEVELOPMENT.md)
2. Review the [Architecture](ARCHITECTURE.md)
3. Check the [Contributing Guidelines](CONTRIBUTING.md)

## Technology Stack

- **Python 3.11+** - Core language
- **PySide6** (Qt 6) - GUI framework
- **SQLite** - Data persistence
- **NumPy** - Vector operations
- **pytest** - Testing framework

## License

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**. GPLv3 is a strong copyleft license that ensures that if you distribute the software, you must share the source code. It is fully compatible with PySide6 (LGPLv3).

## Support

- **Issues**: [GitHub Issues](https://github.com/cmintert/ProjektKraken/issues)
- **Documentation**: This guide and linked documents
- **Source Code**: [GitHub Repository](https://github.com/cmintert/ProjektKraken)

## Version

Current Version: **v0.10.3 (Beta)**

---

**Next Steps:**
- New users: Start with the [Installation Guide](INSTALLATION.md)
- Existing users: Check the [User Guide](USER_GUIDE.md) for feature details
- Developers: Read the [Architecture](ARCHITECTURE.md) and [Development Guide](DEVELOPMENT.md)
