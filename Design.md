Project Kraken: Comprehensive Design Specification

Version: 0.2.0
Status: Phase 4 (UI/UX Overhaul Complete)
Target Audience: Software Developers, UX Designers

1. Product Vision & Philosophy

Project Kraken is a desktop worldbuilding environment designed specifically for the "Architect" Persona (Type A Worldbuilder). Unlike typical wiki-tools that treat lore as static text, Kraken treats history as the primary axis of the world.

1.1 The Core Problems Solved

The "Mode Switching" Fatigue: Eliminates the friction of toggling between "Edit" (Markdown) and "Read" modes found in tools like Obsidian. Kraken uses a native WYSIWYG editor.

The Static History: Most tools treat dates as simple text strings. Kraken treats time as a mathematical coordinate, allowing for causal ripples and precise timeline visualization.

The Context Void: Standard tools show one page at a time. Kraken uses a Context-Aware UI (similar to 3D software like Houdini) where selecting an object instantly updates multiple linked views (Timeline, Graph, Inspector).

1.2 The User Experience

The workflow is "Timeline-First":

The user defines an Event (e.g., "The Fall of Atlantis").

The user links Entities (Characters, Cities) to that event.

The system constructs the biography of the entities based on the events they participated in.

2. Technical Architecture

Kraken adheres to a strict Service-Oriented Architecture (SOA) with the Command Pattern to prevent the "God Class" anti-pattern.

2.1 Technology Stack

Language: Python 3.10+

GUI Framework: PySide6 (Qt for Python) - Official LGPL bindings.

Database: SQLite 3.35+ - Local, serverless, single-file (.kraken).

Documentation: Sphinx (Google Style).

Testing: Pytest.

2.2 Architectural Patterns

The "Dumb UI" Principle:

Views (src/gui) contains zero business logic. They only display data and emit signals.

Logic (src/core) knows nothing about the UI. It returns pure Python objects.

Communication: UI -> Command -> Service -> Signal -> UI Redraw.

The Command Pattern (Action Layer):

Every user action (e.g., CreateEvent, DeleteNode) is a standalone class in src/commands.

This encapsulates logic and enables Undo/Redo functionality natively.

Service Layer (The API):

DatabaseService: Handles raw SQL I/O.

TimeService: Handles Float-to-String math.

SelectionManager: Manages the state of the "Context" (what is selected).

3. Data Architecture (The Hybrid Model)

Kraken uses a Hybrid SQLite Schema to balance strict relational integrity with the flexibility required for worldbuilding.

3.1 The "Hard" Schema (SQL Columns)

Mandatory fields strictly typed in SQL to ensure performance for sorting, filtering, and tree generation.

Entities (Timeless): id (UUID), type (String), name (String), description (HTML).

Events (Time-Bound): id (UUID), type (String), name (String), lore_date (Float), lore_duration (Float).

Relations (The Glue): id (UUID), source_id, target_id, rel_type.

3.2 The "Soft" Schema (JSON Attributes)

Every table includes an attributes JSON column.

Usage: Inventory, Stats, Custom Tags, procedural generation seeds.

Blueprints: Users can manually apply "Blueprints" (JSON Templates) to a node to enforce consistency (e.g., applying a "City Economy" template adds specific keys to the JSON). No auto-injection.

3.3 Organizational Metadata

All tables track:

created_at, modified_at (Real-world timestamps).

author (For future collaboration).

status (Draft, Idea, Canon).

gm_only (Boolean for spoiler protection).

4. The Time Engine

Kraken decouples Storage from Presentation.

4.1 Storage: Linear Float

Time is stored as a REAL (float) in the database.

Scale Standard: 1.0 = 1 Day.

Precision: 64-bit floats allow for cosmic scales (millions of years) down to combat rounds (seconds) without significant loss of precision.

4.2 Presentation: Calendar Config

A CalendarConfig (JSON) defines how to translate the float into a string.

Example: Float 405.5 -> "Year 2, Month 2, Day 10, Noon".

This allows for custom fantasy calendars (e.g., 8-day weeks, named months) without changing the database structure.

5. UI/UX Specification

The interface mimics high-end productivity tools (IDEs, 3D Suites).

5.1 The "Trinity" of Context Views

Entity View (The Editor):

QTextEdit-based WYSIWYG editor.

Supports [[WikiLinks]] which are parsed and clickable.

Timeline View:

QGraphicsView-based linear rendering.

Renders Events as bars/points on the Float axis.

Context Behavior: Selecting an Entity filters this view to show only relevant events.

Binder (Dynamic Hierarchy):

A QTreeView that constructs folders dynamically based on queries (e.g., "Group by Faction", "Group by Location").

It is not a static file system.

5.2 Theming & Styling

The UI uses a centralized `ThemeManager` (`src/core/theme_manager.py`) that loads color palettes from `themes.json`.

*   **Dark Mode**: Default modern dark theme.
*   **Tokens**: Semantic color tokens (e.g., `primary`, `surface`, `border`) are mapped to Qt stylesheets (QSS).
*   **Scalability**: High DPI scaling is enabled via `Qt.HighDpiScaleFactorRoundingPolicy.PassThrough`.

6. Development Standards

To maintain dependability, strict coding standards are enforced.

Documentation:

Google Style Docstrings are mandatory for all methods.

Type Hints (typing.List, typing.Optional) are mandatory.

Logging:

Use the standard logging module.

No print() statements.

RotatingFileHandler keeps logs under 5MB.

Testing:

Pytest is the framework.

Memory DB Pattern: Unit tests must use an in-memory SQLite instance (:memory:) via a pytest fixture to ensure speed and safety.