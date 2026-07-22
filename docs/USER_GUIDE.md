# User Guide

**Version:** 0.11.0 (Beta)  
**Last Updated:** February 2026

Complete guide to using ProjektKraken for worldbuilding and timeline management.

---

## Table of Contents

1. [Introduction](#introduction)
2. [Core Concepts](#core-concepts)
3. [User Interface Overview](#user-interface-overview)
4. [Working with Worlds](#working-with-worlds)
5. [Events and Timeline](#events-and-timeline)
6. [Entities](#entities)
7. [Relations](#relations)
8. [Maps and Geography](#maps-and-geography)
9. [Calendar System](#calendar-system)
10. [Search and AI Features](#search-and-ai-features)
11. [Graph Visualization](#graph-visualization)
12. [Import and Export](#import-and-export)
13. [Undo and Redo](#undo-and-redo)
14. [Keyboard Shortcuts](#keyboard-shortcuts)

---

## Introduction

### What is ProjektKraken?

ProjektKraken is a **timeline-first desktop worldbuilding application** designed for writers, game masters, and worldbuilders who need to manage complex lore with chronological precision. Unlike traditional wiki tools, ProjektKraken treats **history as the primary axis** of your world.

### Key Philosophy

- **Timeline-First**: Events are first-class citizens with precise timestamps
- **Relationship-Driven**: Everything connects through typed relationships
- **Local-First**: Your data lives on your computer, not in the cloud
- **Portable**: Entire worlds are self-contained folders you can backup or share

### Who is This For?

- **Fantasy Writers**: Track character arcs, political changes, and world events
- **Game Masters**: Manage campaign timelines, NPCs, and locations
- **Worldbuilders**: Create detailed histories with causal relationships
- **Sci-Fi Authors**: Handle cosmic timescales and complex chronologies

---

## Core Concepts

### The Data Model

ProjektKraken organizes your world around four core concepts:

#### 1. **Events**

Events are **timestamped moments** in your world's history.

- Have a precise date (cosmic to second resolution)
- Can represent anything: battles, births, treaties, natural disasters
- Are the primary building blocks of your timeline
- Can be linked to entities and other events

**Example Events:**
- "The Fall of Atlantis" (March 15, Year 1234)
- "King Arthur's Birth" (Year 470, Day 1)
- "Treaty of Westphalia" (October 24, 1648)

#### 2. **Entities**

Entities are **persistent things** in your world.

- Characters, locations, factions, items, concepts
- Don't require dates (though they participate in dated events)
- Have flexible attributes via JSON storage
- Can relate to any other entity or event

**Example Entities:**
- "Gandalf" (character)
- "The Shire" (location)
- "The Fellowship" (faction)
- "The One Ring" (item)

#### 3. **Relations**

Relations are **typed connections** between items.

- Directed: A → B (e.g., "Arthur" → "killed" → "Mordred")
- Can be bidirectional (automatically create reverse relation)
- Have types: "caused", "influenced", "depicted", "involved", etc.
- Can carry attributes (metadata on the relationship)

**Example Relations:**
- Event "The Battle" → "involved" → Entity "King Arthur"
- Event "World War I" → "caused" → Event "World War II"
- Entity "Frodo" → "owns" → Entity "The One Ring"

#### 4. **Worlds**

A World is a **self-contained project**.

- Stored as a folder with a `.kraken` SQLite database
- Contains all events, entities, relations, and assets
- Completely portable (copy folder = copy world)
- Supports custom calendars and themes

---

## User Interface Overview

### Main Window Layout

ProjektKraken uses a **dockable panel system** with flexible layouts:

```
┌─────────────────────────────────────────────────────┐
│ Menu Bar (File, Edit, View, Tools, Help)           │
├──────────────┬──────────────────┬───────────────────┤
│              │                  │                   │
│  Project     │   Timeline       │   Entity/Event    │
│  Explorer    │   Graphic        │   Editor          │
│              │   View           │                   │
│  (Tree of    │                  │   (Details and    │
│   Events &   │   [Timeline]     │    Properties)    │
│   Entities)  │                  │                   │
│              │                  │                   │
├──────────────┼──────────────────┴───────────────────┤
│              │                                      │
│  Relations   │   History Panel                     │
│  Panel       │   (Undo/Redo Stack)                 │
│              │                                      │
└──────────────┴──────────────────────────────────────┘
```

### Core Panels

#### Project Explorer (Left)
- **Unified List**: Shows all events and entities in one tree
- **Filtering**: Filter by type, tags, or search query
- **Drag-Drop**: Drag items to create relations
- **Context Menu**: Right-click for quick actions

#### Timeline (Center)
- **Visual Timeline**: Events displayed chronologically
- **Playhead**: Current time indicator
- **Zoom Controls**: Zoom in/out on timeline
- **Group Bands**: Organize events by category

#### Editor (Right)
- **Event Editor**: Edit event details, date, description
- **Entity Editor**: Edit entity properties, attributes, tags
- **Tabbed Interface**: Multiple editors can be open

#### Relations Panel (Bottom Left)
- **Relation List**: All relations for selected item
- **Quick Actions**: Add, edit, delete relations
- **Type Filtering**: Filter by relation type

#### History Panel (Bottom Right)
- **Command History**: Visual undo/redo stack
- **Session Tracking**: Persists across app restarts
- **Quick Navigation**: Click to jump to any point in history

---

## Working with Worlds

### Creating a New World

1. **Open Create World Dialog**
   - **File → New World** (Ctrl+N)
   - Or click "+" in Project Explorer

2. **Enter World Details**
   - **Name**: Your world's name (e.g., "Middle Earth")
   - **Description**: Optional brief description

3. **World Structure**
   ```
   worlds/
   └── Middle Earth/
       ├── world.json                  # Metadata
       ├── Middle Earth.kraken         # Database
       └── assets/
           ├── images/                 # Full-size images
           ├── thumbnails/             # Auto-generated thumbnails
           └── .trash/                 # Deleted files (for undo)
   ```

### Opening an Existing World

1. **File → Open World** (Ctrl+O)
2. **Select World Folder**
3. World opens and loads all data

### World Settings

Access via **Edit → World Settings**:

- **Name and Description**: Edit world metadata
- **Calendar**: Configure custom calendar system
- **Theme**: Select UI theme
- **Backup Settings**: Configure auto-backup frequency

### Backup and Restore

#### Automatic Backups

ProjektKraken automatically backs up your world:

- **Frequency**: Configurable (default: every 15 minutes)
- **Location**: User data directory
- **Retention**: Keeps last N backups (configurable)

#### Manual Backup

1. **File → Backup World**
2. Choose destination folder
3. Backup creates timestamped `.kraken` file

#### Restore from Backup

1. **File → Restore World**
2. Select backup `.kraken` file
3. Confirm restoration (creates backup of current state first)

---

## Events and Timeline

### Creating Events

#### Quick Create

1. **Events → New Event** (Ctrl+Shift+E)
2. Enter basic details:
   - **Name**: Event title
   - **Date**: Natural language or calendar date
   - **Type**: Event category (optional)

#### Natural Language Dates

ProjektKraken understands natural date expressions:

- `"1st of Summer"` → Converts to calendar date
- `"2 weeks later"` → Relative to current playhead
- `"Year 1234, Day 45"` → Direct date specification

### Editing Events

1. **Select Event** in Project Explorer or Timeline
2. **Event Editor Opens** in right panel
3. **Editable Fields:**
   - **Name**: Event title
   - **Date**: Lore date (float or calendar)
   - **Type**: Event category
   - **Tags**: Classification tags
   - **Description**: Rich text with wiki links
   - **Attributes**: Custom JSON fields

### Timeline Visualization

#### Timeline Controls

- **Zoom In/Out**: Mouse wheel or zoom slider
- **Pan**: Click and drag timeline
- **Return to Present**: Jump to playhead position

#### Timeline Views

1. **Graphic Timeline** (Lane-based)
   - Events as blocks on horizontal lanes
   - Automatic lane packing prevents overlap
   - Group bands for categorization

2. **Card Timeline** (Text-based)
   - Events as cards in vertical list
   - Shows more detail per event

#### Playhead

The **playhead** represents "current time" in your world:

- **Visual Indicator**: Red line on timeline
- **Clock Mode**: Edit precise time
- **Temporal Context**: Events before/after playhead

---

## Entities

### Creating Entities

1. **Entities → New Entity** (Ctrl+Shift+N)
2. Enter details:
   - **Name**: Entity name
   - **Type**: Character, Location, Faction, Item, Concept
   - **Tags**: Classification tags
   - **Description**: Rich text description

### Entity Types

ProjektKraken supports multiple entity types:

| Type | Description | Examples |
|------|-------------|----------|
| **Character** | People, sentient beings | "Frodo", "Gandalf", "Aragorn" |
| **Location** | Places, regions | "The Shire", "Mordor", "Rivendell" |
| **Faction** | Groups, organizations | "The Fellowship", "Gondor", "Mordor Army" |
| **Item** | Objects, artifacts | "The One Ring", "Anduril", "Palantir" |
| **Concept** | Abstract ideas | "The Prophecy", "Ring Lore", "Elvish Magic" |

### Editing Entities

#### Entity Editor Panel

- **Basic Info**: Name, type, tags
- **Description**: Wiki-style text editor with `[[links]]`
- **Attributes**: Custom fields (key-value pairs)
- **Relations**: List of all connections
- **Events**: Events this entity is involved in

#### Wiki Links

Link to other entities using double brackets:

```
Frodo is a [[Hobbit]] from [[The Shire]].
He carries the [[One Ring]].
```

- **Auto-complete**: Start typing `[[` to see suggestions
- **Click to Navigate**: Click links to jump to linked entities

### Tags and Filtering

#### Adding Tags

- In Entity Editor, click "Add Tag"
- Enter tag name (e.g., "protagonist", "magic", "ancient")

#### Filtering by Tags

- In Project Explorer, use tag filter
- Select one or more tags
- View updates to show only matching items

---

## Relations

### Understanding Relations

Relations connect items in your world:

- **Directed**: A → B (source to target)
- **Typed**: Specific relationship type
- **Attributed**: Can have metadata

### Relation Types

Common relation types:

| Type | Description | Example |
|------|-------------|---------|
| **caused** | Causal relationship | Event A caused Event B |
| **involved** | Participation | Event involved Entity |
| **influenced** | Indirect effect | Entity influenced Event |
| **depicted** | Representation | Map depicted Location |
| **located_at** | Spatial | Entity located at Location |
| **member_of** | Membership | Character member of Faction |
| **owns** | Ownership | Character owns Item |

### Creating Relations

#### Method 1: Drag and Drop

1. **Drag** an entity/event from Project Explorer
2. **Drop** onto another entity/event in editor
3. **Select Relation Type** from popup (hold Shift)
4. Relation created with undo support

#### Method 2: Relations Panel

1. **Select** source item
2. **Click "Add Relation"** in Relations Panel
3. **Choose** target item and relation type
4. **Confirm**

#### Method 3: Context Menu

1. **Right-click** item in Project Explorer
2. **Select "Add Relation"**
3. **Choose** target and type

### Editing Relations

1. **Select Relation** in Relations Panel
2. **Edit Dialog Opens**
   - Change target
   - Change type
   - Add/edit attributes
3. **Save Changes**

### Bidirectional Relations

Create reverse relation automatically:

- **Enable "Bidirectional"** when creating
- Example: A "owns" B also creates B "owned_by" A
- Both relations are independent (can delete separately)

### Relation Attributes

Add metadata to relations:

```json
{
  "since": "Year 1234",
  "strength": "strong",
  "public": true
}
```

Use cases:
- Temporal information (when relation started/ended)
- Intensity or importance
- Conditional properties

---

## Maps and Geography

### Adding a Map

1. **Maps → New Map**
2. **Upload Image** (PNG, JPG, or custom format)
3. **Name Map** and set properties

### Map Features

#### Map Markers

Place markers on maps to represent locations:

1. **Add Marker**: Right-click on map → "Add Marker"
2. **Link to Entity**: Associate marker with location entity
3. **Customize**:
   - Icon (from icon picker)
   - Color
   - Label

#### Map Calibration

Set real-world scale:

1. **Tools → Calibrate Map**
2. **Click Two Points** of known distance
3. **Enter Distance** (e.g., "100 miles")
4. Scale calculated automatically

#### Coordinate System

Maps support coordinates:

- **Pixel Coordinates**: X, Y on image
- **World Coordinates**: Lat/Long if calibrated
- **Grid Overlay**: Optional grid display

---

## Calendar System

### Understanding Lore Dates

ProjektKraken stores dates as **floats** (1.0 = 1 day):

- **Internal Storage**: 12345.678 (day 12345, hour 16:16:48)
- **Display**: Converted to calendar format
- **Precision**: Cosmic scale to sub-second

### Default Calendar

Built-in Gregorian-like calendar:

- 12 months, 28-31 days each
- 7-day weeks
- Leap years every 4 years

### Custom Calendars

Create fantasy calendars:

1. **Edit → Calendar Settings**
2. **Configure**:
   - Month names and lengths
   - Week structure (day names, week length)
   - Leap year rules
   - Year variants (special years)

#### Example: Fantasy Calendar

```
Months:
  - Coldmoon (30 days)
  - Springrise (28 days)
  - Highsun (35 days)
  - Harvest (30 days)

Weeks: 8 days
  - Moonday, Starday, Fireday, Waterday, Earthday, Windday, Voidday, Restday

Leap Years: Every 5 years (extra day in Highsun)
```

### Date Entry

Enter dates in multiple formats:

- **Natural Language**: "1st of Coldmoon, Year 1234"
- **Numeric**: "1234.45" (day 45 of year 1234)
- **Relative**: "2 weeks after current" (from playhead)

---

## Search and AI Features

### Semantic Search

#### Enabling Search

1. **Tools → AI Settings**
2. **Choose Provider**:
   - **Sentence Transformers** (built-in local default)
   - **LM Studio** (local, private, optional)
3. For LM Studio, enter only the server address, such as
   `http://localhost:1234`, then select **Refresh Models**.
4. Choose an embedding-capable model. This can be different from the model
   used for text generation.
5. **Index World**: Tools → Build Search Index

#### Using Semantic Search

1. **Open AI Panel** (Ctrl+K)
2. **Enter Natural Language Query**:
   - "Who are the wizards in my world?"
   - "Events related to the war"
   - "Find all items with magical properties"
3. **View Results** ranked by relevance

### LLM Generation

#### Generating Content

1. **Select Context** (entity or event)
2. In **Tools → AI Settings**, configure LM Studio and choose a loaded
   text-generation model. Cloud generation providers are currently disabled.
3. Expand **LLM Generation** in the editor.
4. **Choose Prompt**:
   - "Expand backstory"
   - "Generate relationships"
   - "Write description"
5. **Review and Edit** generated text, then explicitly choose **Replace** or
   **Append**. **Discard** leaves the description unchanged.

ProjektKraken preserves the visible reply exactly, including Markdown, wiki
links, Unicode, leading/trailing spaces, and blank lines. Model reasoning and
tool-call fields are kept separate and are never inserted into descriptions.
If the selected item changes during generation, the stale result is rejected.

#### Custom Prompts

Create custom LLM prompts:

1. **AI → Manage Prompts**
2. **New Prompt**
3. **Template with Variables**:
   ```
   Write a detailed description of {entity_name}.
   Type: {entity_type}
   Context: {related_events}
   ```

### RAG Integration

Retrieval-Augmented Generation uses your world data:

- **Indexes** all entities and events
- **Retrieves** relevant context for queries
- **Augments** LLM with your specific lore
- **Generates** consistent, world-accurate content

---

## Graph Visualization

### Opening Graph View

**View → Graph View** (Ctrl+G)

### Graph Features

- **Interactive Nodes**: Drag to rearrange
- **Force-Directed Layout**: Automatic spacing
- **Relation Edges**: Connections between nodes
- **Color Coding**: By type or tag

### Filtering Graph

1. **Filter Panel** (left side)
2. **Filter Options**:
   - **By Type**: Events, Entities, specific types
   - **By Tags**: Include/exclude tags
   - **By Relation Type**: Show specific relations
3. **Apply Filters** - graph updates in real-time

### Graph Export

**Graph → Export**:

- **PNG Image**: Static snapshot
- **JSON**: Graph data for external tools
- **HTML**: Interactive web version

---

## Import and Export

### Importing Data

#### JSON Import

1. **File → Import → JSON**
2. **Select File** with event/entity data
3. **Two-Pass Import**:
   - **Pass 1**: Deduplication (match by name)
   - **Pass 2**: Resolve references and cycles
4. **Review Import Log**

#### Supported Import Formats

- **ProjektKraken JSON**: Native format
- **Custom JSON**: Configurable mapping

### Exporting Data

#### Obsidian Export

Export to Obsidian-compatible markdown:

1. **File → Export → Obsidian**
2. **Choose Folder**
3. **Generated Structure**:
   ```
   export/
   ├── Events/
   │   ├── Event1.md
   │   └── Event2.md
   ├── Entities/
   │   ├── Entity1.md
   │   └── Entity2.md
   └── _index.md
   ```

**Markdown Format**:
```markdown
---
type: entity
tags: [character, protagonist]
---

# Frodo Baggins

A hobbit from [[The Shire]].

## Events
- [[The Quest]] (Year 3018)
- [[Destruction of the Ring]] (Year 3019)
```

#### JSON Export

Full world export:

1. **File → Export → JSON**
2. **Include Options**:
   - Events, Entities, Relations
   - Calendar, Settings
   - Assets (images)
3. **Save to File**

#### Longform Builder

Generate narrative documents:

1. **Tools → Longform Builder**
2. **Select Events** for timeline narrative
3. **Generate** formatted document
4. **Export** to Markdown, HTML, or PDF

---

## Undo and Redo

### How Undo Works

ProjektKraken uses the **Command Pattern**:

- Every user action is a reversible command
- Commands are stored in history
- History persists across app restarts

### Using Undo/Redo

**Keyboard Shortcuts**:
- **Undo**: Ctrl+Z (Cmd+Z on Mac)
- **Redo**: Ctrl+Shift+Z (Cmd+Shift+Z on Mac)

**Menu**:
- **Edit → Undo** 
- **Edit → Redo**

### History Panel

View and navigate command history:

1. **View → History Panel**
2. **Visual Stack**:
   - **▲ Done Commands**: Can undo (top of stack)
   - **▼ Undone Commands**: Can redo (bottom of stack)
3. **Click Any Command**: Jump to that state

### Persistent History

- **Saves to Database**: History stored in `.kraken` file
- **Session Tracking**: Remembers across restarts
- **Edit Sessions**: Logical grouping of related changes

### What Can Be Undone?

✅ **All User Actions**:
- Create, edit, delete events/entities
- Add, modify, remove relations
- Move markers on maps
- Change calendar settings
- Batch operations

❌ **Not Undoable**:
- Opening/closing worlds
- UI layout changes
- Search queries
- Backup/restore operations

---

## Keyboard Shortcuts

### General

| Shortcut | Action |
|----------|--------|
| **Ctrl+N** | New World |
| **Ctrl+O** | Open World |
| **Ctrl+S** | Save (auto-saves enabled) |
| **Ctrl+Z** | Undo |
| **Ctrl+Shift+Z** | Redo |
| **Ctrl+Q** | Quit |

### Navigation

| Shortcut | Action |
|----------|--------|
| **Ctrl+K** | Open AI Search Panel |
| **Ctrl+G** | Open Graph View |
| **Ctrl+T** | Jump to Timeline |
| **Ctrl+E** | Focus Project Explorer |

### Creation

| Shortcut | Action |
|----------|--------|
| **Ctrl+Shift+E** | New Event |
| **Ctrl+Shift+N** | New Entity |
| **Ctrl+Shift+R** | New Relation |

### Editing

| Shortcut | Action |
|----------|--------|
| **Ctrl+D** | Duplicate Selected |
| **Delete** | Delete Selected |
| **F2** | Rename Selected |
| **Ctrl+F** | Find/Filter |

### Timeline

| Shortcut | Action |
|----------|--------|
| **Space** | Play/Pause Playhead |
| **+** | Zoom In |
| **-** | Zoom Out |
| **Home** | Jump to Start |
| **End** | Jump to End |

---

## Next Steps

### Learn More

- **[Workflows Guide](WORKFLOWS.md)** - Step-by-step guides for common tasks
- **[FAQ](FAQ.md)** - Common questions and troubleshooting
- **[Architecture](ARCHITECTURE.md)** - Technical architecture (for developers)

### Get Help

- **GitHub Issues**: Report bugs or request features
- **Discussions**: Ask questions and share tips
- **Documentation**: Full docs at [docs/INDEX.md](INDEX.md)

---

**Navigation:**  
[← Installation Guide](INSTALLATION.md) • [Back to Index](INDEX.md) • [Workflows Guide →](WORKFLOWS.md)
