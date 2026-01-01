---
**Project:** ProjektKraken  
**Document:** Design Specification  
**Last Updated:** 2026-01-01  
**Commit:** `373459f4`  
---

# Project Kraken: Comprehensive Design Specification

Version: 0.4.0  
Status: Alpha  
Target Audience: Software Developers, UX Designers

## 1. Product Vision & Philosophy

Project Kraken is a desktop worldbuilding environment designed specifically for the "Architect" Persona (Type A Worldbuilder). Unlike typical wiki-tools that treat lore as static text, Kraken treats history as the primary axis of the world.

### 1.1 The Core Problems Solved

**The "Mode Switching" Fatigue**: Eliminates the friction of toggling between "Edit" (Markdown) and "Read" modes found in tools like Obsidian. Kraken uses a native WYSIWYG editor.

**The Static History**: Most tools treat dates as simple text strings. Kraken treats time as a mathematical coordinate, allowing for causal ripples and precise timeline visualization.

**The Context Void**: Standard tools show one page at a time. Kraken uses a Context-Aware UI (similar to 3D software like Houdini) where selecting an object instantly updates multiple linked views (Timeline, Graph, Inspector).

### 1.2 The User Experience

The workflow is "Timeline-First":

1. The user defines an Event (e.g., "The Fall of Atlantis").
2. The user links Entities (Characters, Cities) to that event.
3. The system constructs the biography of the entities based on the events they participated in.

## 2. Technical Architecture

Kraken adheres to a strict Service-Oriented Architecture (SOA) with the Command Pattern to prevent the "God Class" anti-pattern.

### 2.1 Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| GUI Framework | PySide6 (Qt 6) - Official LGPL bindings |
| Database | SQLite 3.35+ - Local, serverless, single-file (.kraken) |
| Documentation | Sphinx (Google Style) |
| Testing | Pytest |
| Code Quality | Ruff |

### 2.2 Architectural Patterns

**The "Dumb UI" Principle:**
- Views (`src/gui`) contain zero business logic. They only display data and emit signals.
- Logic (`src/core`) knows nothing about the UI. It returns pure Python objects.
- Communication: UI → Command → Service → Signal → UI Redraw.

**The Command Pattern (Action Layer):**
- Every user action (e.g., CreateEvent, DeleteEntity) is a standalone class in `src/commands`.
- This encapsulates logic and enables Undo/Redo functionality natively.
- Commands are shared between GUI and CLI for 100% feature parity.

**Service Layer (The API):**
- `DatabaseService`: Handles raw SQL I/O with parameterized queries.
- `CalendarConverter`: Handles Float-to-String time conversion.
- `LinkResolver`: Resolves wiki links to entities/events.
- `AttachmentService`: Manages image attachments.

### 2.3 Directory Structure

```
src/
├── app/          # Application entry point, MainWindow, DataHandler
├── cli/          # Command-line tools (headless operations)
├── commands/     # Undo/Redo command pattern implementation
├── core/         # Business logic, models, theme management
├── gui/          # PySide6 widgets
│   └── widgets/
│       ├── timeline/      # Timeline visualization (lane packing, ruler)
│       ├── map/           # Map and marker system
│       └── ...            # Editors, lists, wiki text, etc.
├── resources/    # Icons, SVG assets
└── services/     # Database, repositories, parsers
```

## 3. Data Architecture (The Hybrid Model)

Kraken uses a Hybrid SQLite Schema to balance strict relational integrity with the flexibility required for worldbuilding.

### 3.1 The "Hard" Schema (SQL Columns)

Mandatory fields strictly typed in SQL to ensure performance for sorting, filtering, and tree generation.

| Table | Columns |
|-------|---------|
| **entities** | id (UUID), type, name, description (HTML) |
| **events** | id (UUID), type, name, lore_date (Float), lore_duration (Float) |
| **relations** | id (UUID), source_id, target_id, rel_type |
| **maps** | id (UUID), name, image_path |
| **markers** | id (UUID), map_id, object_id, object_type, x, y, label |
| **attachments** | id (UUID), owner_type, owner_id, file_path, mime_type |
| **longform_entries** | id, table_name, object_id, parent_id, position, level |

### 3.2 The "Soft" Schema (JSON Attributes)

Every table includes an `attributes` JSON column for flexible data:
- Inventory, Stats, Custom Tags
- Procedural generation seeds
- Map marker colors and icons
- Attachment metadata

### 3.3 Organizational Metadata

All tables track:
- `created_at`, `modified_at` (Real-world timestamps)
- Status flags for workflow management

## 4. Time System

Kraken decouples Storage from Presentation.

### 4.1 Storage: Linear Float

- Time is stored as a `REAL` (float) in the database.
- Scale Standard: **1.0 = 1 Day**.
- Precision: 64-bit floats allow for cosmic scales (millions of years) down to sub-day resolution (hours, minutes).

### 4.2 Presentation: Custom Calendar

A `CalendarConfig` (JSON) defines how to translate the float into a human-readable string.

**Features:**
- Custom months with variable days per month
- Custom week days with abbreviations
- Sub-day time conversion (hours, minutes)
- Bidirectional conversion (structured ↔ float)

**Example:** Float `405.5` → "Year 2, Month 2, Day 10, 12:00"

This allows for custom fantasy calendars (e.g., 8-day weeks, 13-month years) without changing the database structure.

## 5. UI/UX Specification

The interface mimics high-end productivity tools (IDEs, 3D Suites) with dockable panels.

### 5.1 Main Views

**Project Explorer:**
- Unified list showing all entities and events
- Drag-and-drop to Map view creates markers
- Type-based filtering

**Entity/Event Editors:**
- Tabbed inspector with Details, Tags, Relations, Attributes
- WikiTextEdit with `[[link]]` syntax and autocomplete
- Gallery widget for image attachments

**Timeline View:**
- QGraphicsView-based Aeon-style visualization
- Lane-based event packing (First Fit algorithm)
- Semantic zoom ruler with collision avoidance
- Event duration bars and point markers
- Draggable playhead and current time line

**Map View:**
- Custom map images with placed markers
- Markers link to entities/events
- Context menu for marker management
- Customizable marker icons and colors

**Longform Editor:**
- Hierarchical document structure
- Drag-and-drop outline management
- Markdown export

### 5.2 Wiki Linking

**ID-Based Links:**
- Format: `[[id:UUID|DisplayName]]`
- Links survive entity renames
- Automatic broken link detection (red styling)
- Ctrl+Click navigation

**Autocomplete:**
- Type `[[` to trigger entity/event suggestions
- Inserts ID-based links automatically

### 5.3 Theming & Styling

The UI uses a centralized `ThemeManager` (`src/core/theme_manager.py`) that loads color palettes from `themes.json`.

- **Dark Mode**: Default modern dark theme
- **Tokens**: Semantic color tokens (e.g., `primary`, `surface`, `border`) mapped to Qt stylesheets (QSS)
- **StyleHelper**: Centralized theme-aware QSS generation
- **Scalability**: High DPI scaling enabled

## 6. CLI Tools

Full-featured command-line interface for headless operations:

```bash
python -m src.cli.event    # Event CRUD
python -m src.cli.entity   # Entity CRUD
python -m src.cli.relation # Relation management
python -m src.cli.calendar # Calendar configuration
python -m src.cli.map      # Map and marker management
python -m src.cli.attachment # Attachment management
python -m src.cli.longform # Document export
python -m src.cli.wiki     # Wiki link scanning
```

See [CLI Documentation](src/cli/README.md) for complete reference.

## 7. Development Standards

### Documentation

- Google Style Docstrings are mandatory for all classes and methods.
- Type Hints are mandatory throughout.

### Logging

- Use the standard `logging` module.
- No `print()` statements.
- RotatingFileHandler keeps logs under 5MB.

### Testing

- **Framework**: Pytest with pytest-qt for GUI tests
- **Coverage**: Target >90%
- **Memory DB Pattern**: Unit tests use in-memory SQLite (`:memory:`) via pytest fixtures.
- **TDD**: Write tests before implementing code.

### Code Quality

- **Ruff** for linting and formatting
- Avoid god classes
- Command pattern for all user actions