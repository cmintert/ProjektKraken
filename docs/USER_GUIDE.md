# User Guide

Welcome to the ProjektKraken User Guide! This comprehensive manual covers all features and functionality of ProjektKraken.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Interface Overview](#interface-overview)
3. [Core Concepts](#core-concepts)
4. [Working with Events](#working-with-events)
5. [Working with Entities](#working-with-entities)
6. [Relations and Connections](#relations-and-connections)
7. [Timeline Features](#timeline-features)
8. [Calendar System](#calendar-system)
9. [Maps and Trajectories](#maps-and-trajectories)
10. [Wiki Linking](#wiki-linking)
11. [Graph Visualization](#graph-visualization)
12. [Longform Documents](#longform-documents)
13. [Semantic Search and AI](#semantic-search-and-ai)
14. [Fast Inject System](#fast-inject-system)
15. [Undo and Redo](#undo-and-redo)
16. [Backup and Recovery](#backup-and-recovery)
17. [Import and Export](#import-and-export)
18. [Customization](#customization)

---

## Getting Started

### Creating a New World

1. **Launch ProjektKraken**
   - Run the executable or `python launcher.py`

2. **Create a World**
   - Click **File → New World** (or press `Ctrl+N`)
   - Enter world name: e.g., "My Fantasy Campaign"
   - Optionally add a description
   - Click **Create**

3. **World Created**
   - A new folder is created: `worlds/My Fantasy Campaign/`
   - Contains `world.json` (metadata) and `My Fantasy Campaign.kraken` (database)
   - Assets folder for images and attachments

### Opening an Existing World

- **File → Open World** (or `Ctrl+O`)
- Navigate to your world folder
- Select the `.kraken` file or the world folder itself
- Click **Open**

### Recent Worlds

- **File → Recent Worlds** - Quick access to recently opened worlds

---

## Interface Overview

### Main Window Layout

ProjektKraken uses a dockable panel layout with multiple customizable views.

```
┌─────────────────────────────────────────────────────────┐
│  Menu Bar                                                │
├──────────────┬──────────────────────┬───────────────────┤
│              │                      │                   │
│  Left Panel  │   Center Panel       │  Right Panel      │
│  (Lists)     │   (Editor)           │  (Graph/Related)  │
│              │                      │                   │
├──────────────┴──────────────────────┴───────────────────┤
│  Bottom Panel (Timeline Ruler)                          │
└─────────────────────────────────────────────────────────┘
```

### Panel Types

#### Left Panel - Data Lists
- **Event List**: Chronological list of all events
- **Entity List**: List of all characters, locations, factions, etc.
- **Unified List**: Combined view with filtering
- **History Panel**: Undo/redo command history

#### Center Panel - Editor
- **Event Editor**: Create and edit events
- **Entity Editor**: Create and edit entities
- **Longform Editor**: Write narrative documents
- **Summary Widget**: Statistics and overview

#### Right Panel - Relations
- **Graph View**: Interactive network visualization
- **Relations List**: Direct connections to selected object
- **Filter Widget**: Tag-based filtering

#### Bottom Panel - Timeline
- **Timeline Ruler**: Visual chronological display
- **Timeline Widget**: Lane-based graphic timeline
- **Timeline Display**: Card-style text timeline

### Docking and Layout

- **Drag Panels**: Click and drag panel tabs to reposition
- **Resize**: Drag panel dividers to adjust size
- **Float**: Drag panel tab outside window to float
- **Dock**: Drag floating panel back to dock
- **Hide/Show**: Use **View** menu to toggle panels
- **Save Layout**: **View → Save Layout** (automatic on close)
- **Reset Layout**: **View → Reset to Default Layout**

### Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| New World | `Ctrl+N` |
| Open World | `Ctrl+O` |
| Save | `Ctrl+S` |
| Create Event | `Ctrl+Shift+E` |
| Create Entity | `Ctrl+E` |
| Search | `Ctrl+F` |
| Undo | `Ctrl+Z` |
| Redo | `Ctrl+Y` or `Ctrl+Shift+Z` |
| Delete | `Delete` |
| Copy | `Ctrl+C` |
| Paste | `Ctrl+V` |
| Find in Text | `Ctrl+F` (in editor) |

---

## Core Concepts

### Events

**Events** are the fundamental building blocks of your world's timeline. They represent moments or periods in your world's history.

**Key Properties:**
- **Name**: Descriptive title (e.g., "The Battle of Crimson Pass")
- **Date**: Temporal position (precise to the second)
- **Type**: Category (historical, battle, discovery, political, etc.)
- **Duration**: How long the event lasted (0 = instant)
- **Description**: Rich text narrative with wiki links

**Event Types:**
- `generic` - General events
- `battle` - Combat encounters
- `discovery` - New findings
- `political` - Political events
- `natural` - Natural phenomena
- `custom` - User-defined types

### Entities

**Entities** represent people, places, things, and concepts in your world.

**Entity Types:**
- **character** - People, NPCs, creatures
- **location** - Places, cities, regions, landmarks
- **faction** - Organizations, groups, nations
- **artifact** - Objects, items, relics
- **concept** - Ideas, philosophies, magic systems

**Key Properties:**
- **Name**: Entity name
- **Type**: Category (see above)
- **Description**: Rich text with wiki links
- **Attributes**: Flexible custom fields (JSON)

### Relations

**Relations** connect events and entities, forming the web of your world.

**Relation Types:**
- `caused` - Causal relationship (Event A caused Event B)
- `located_in` - Spatial containment (Entity in Location)
- `involved` - Participation (Character involved in Event)
- `owns` - Ownership (Character owns Artifact)
- `member_of` - Membership (Character member of Faction)
- `rules` - Authority (Character rules Location)
- `founded` - Creation (Event founded Entity)
- `custom` - User-defined types

**Temporal Relations:**
Relations can have start and end dates for dynamic relationships that change over time.

### Attributes

**Attributes** are flexible custom fields stored as JSON.

**Examples:**
```json
{
  "age": 45,
  "role": "Queen",
  "alignment": "Lawful Good",
  "hp": 120,
  "_tags": ["royalty", "npc", "major_character"]
}
```

**Tags**: Stored under `_tags` key as a list of strings.

---

## Working with Events

### Creating an Event

1. **Open Event Creator**
   - Click **Create → Event** (or press `Ctrl+Shift+E`)
   - Or click **+ Event** button in event list

2. **Fill in Details**
   - **Name**: Enter event name
   - **Date**: Enter date using natural language or date picker
     - Examples: "1st of Spring", "100.5", "2024-01-15"
   - **Type**: Select event type from dropdown
   - **Duration**: Enter duration (optional)
     - Examples: "3 days", "2.5", "1 year"
   - **Description**: Write narrative description
     - Use `[[Entity Name]]` for wiki links
     - Formatting: **bold**, *italic*, `code`

3. **Add Metadata**
   - **Tags**: Add tags for categorization
   - **Attributes**: Add custom fields (click "Add Attribute")

4. **Save**
   - Click **Save** (or press `Ctrl+S`)

### Editing an Event

1. **Select Event**
   - Click event in Event List or Timeline
   - Event details appear in editor

2. **Modify Fields**
   - Change any field as needed
   - Click **Save** when done

3. **Auto-Save**
   - Changes are saved automatically on world close

### Deleting an Event

1. **Select Event**
2. **Delete**
   - Press `Delete` key
   - Or click **Delete** button
   - Or **Edit → Delete Event**
3. **Confirm** deletion dialog
4. **Undo Available** - Use `Ctrl+Z` to restore if needed

### Event Date Entry

**Natural Language Dates:**
- "1st of Spring" - Uses custom calendar
- "Day 100" - Absolute day number
- "2 weeks after" - Relative to current timeline position
- "Year 245, Month 3, Day 15" - Explicit date

**Numeric Dates:**
- Float values: `100.5` = Day 100, halfway through
- Time resolution: 1.0 = 1 day
- Cosmic scale: Can represent millions of years

**Date Picker:**
- Click calendar icon in date field
- Select year, month, day
- Hour/minute for precise timing (optional)

### Event Duration

- **Instant Events**: Duration = 0 (default)
- **Timed Events**: Duration > 0
  - Displayed as bars on timeline
  - Examples: "The Mage Wars" (25 years), "The Harvest Festival" (3 days)

### Event Attachments

**Adding Images:**
1. In Event Editor, click **Gallery** tab
2. Click **Add Image**
3. Select image file(s)
4. Optionally add captions

**Image Storage:**
- Stored in `worlds/[World Name]/assets/images/events/[event_id]/`
- Thumbnails generated automatically
- Supports: JPG, PNG, GIF, BMP

---

## Working with Entities

### Creating an Entity

1. **Open Entity Creator**
   - Click **Create → Entity** (or press `Ctrl+E`)
   - Or click **+ Entity** button in entity list

2. **Fill in Details**
   - **Name**: Enter entity name
   - **Type**: Select entity type (character, location, faction, artifact, concept)
   - **Description**: Write description with wiki links

3. **Add Custom Fields**
   - Click **Attributes** tab
   - Add custom fields:
     - Age, role, alignment (characters)
     - Population, climate (locations)
     - Members, goals (factions)
     - Power, rarity (artifacts)

4. **Add Tags**
   - Add tags for filtering and organization
   - Examples: "npc", "major_character", "city", "magic_item"

5. **Save** - `Ctrl+S`

### Entity Types in Detail

#### Characters
- Represent people, NPCs, creatures
- Common attributes: age, role, alignment, race, class
- Link to events via "involved", "witnessed", etc.
- Link to locations via "located_in", "born_in"

#### Locations
- Represent places, cities, regions, landmarks
- Common attributes: population, climate, terrain
- Use hierarchical relations: City → Region → Continent
- Can have map markers

#### Factions
- Organizations, groups, nations
- Common attributes: members, goals, alignment, resources
- Link members via "member_of" relations
- Track founding and dissolution events

#### Artifacts
- Objects, items, relics
- Common attributes: power, rarity, material, creator
- Track ownership via "owns" relations
- Link creation events

#### Concepts
- Ideas, philosophies, magic systems, religions
- Common attributes: followers, origin, principles
- Use for abstract worldbuilding elements

### Editing Entities

- Same as events - select, modify, save
- Changes reflected immediately in relations and graph

### Entity Attachments

- Same as events - add images via Gallery tab
- Multiple images supported
- Stored in `worlds/[World Name]/assets/images/entities/[entity_id]/`

---

## Relations and Connections

### Adding a Relation

1. **Select Source Object**
   - Click event or entity in list

2. **Open Relations Section**
   - In editor, scroll to **Relations** section

3. **Add New Relation**
   - Click **Add Relation** button
   - Select target object (event or entity)
   - Select relation type from dropdown
   - Optionally add:
     - Start date (when relation began)
     - End date (when relation ended)
     - Custom attributes
   - Click **Add**

### Relation Types

**Event ↔ Entity:**
- `involved` - Entity participated in event
- `caused` - Event affected entity
- `founded` - Event created entity
- `held_at` - Event occurred at location

**Entity ↔ Entity:**
- `located_in` - Spatial containment
- `member_of` - Membership
- `owns` - Ownership
- `rules` - Authority
- `allied_with` - Alliance
- `enemy_of` - Conflict
- `parent_of` / `child_of` - Lineage

**Event ↔ Event:**
- `caused` - Causal chain
- `triggered_by` - Causal reverse
- `concurrent_with` - Simultaneous

### Temporal Relations

Relations can have temporal scope:

**Start Date**: When relation began
**End Date**: When relation ended (optional)

**Example:**
```
Character "Lord Marcus" member_of "Knights of Dawn"
- Start: Year 220 (joined order)
- End: Year 245 (retired)
```

**Dynamic Display**: Timeline can show entity state at specific points in time based on active relations.

### Viewing Relations

**In Editor:**
- Relations section shows all connections
- Click relation to edit or delete

**In Graph View:**
- Visual network of connections
- Node colors by type
- Edge labels show relation types

**Backlinks:**
- Selecting an entity shows all events/entities referencing it

---

## Timeline Features

### Timeline Views

ProjektKraken offers three timeline visualization modes:

#### 1. Timeline Ruler (Bottom Panel)
- Horizontal timeline with zoom controls
- Click to jump to time period
- Drag playhead to scrub through time
- Shows event markers as dots or bars

#### 2. Lane-Based Graphic Timeline
- Events displayed in horizontal lanes (swim lanes)
- Long-duration events shown as bars
- Color-coded by type or tag
- Supports grouping by type or tag

#### 3. Card-Style Text Timeline
- Vertical list of event cards
- Chronological order
- Shows full event details
- Filterable and searchable

### Timeline Navigation

**Zoom In/Out:**
- Mouse wheel while hovering over timeline
- Zoom buttons in toolbar
- `Ctrl++` / `Ctrl+-` keyboard shortcuts

**Pan:**
- Click and drag timeline background
- Arrow keys for fine adjustment
- Home/End keys to jump to start/end

**Jump to Date:**
- Click date field in toolbar
- Enter date or day number
- Press Enter to jump

**Return to Present:**
- Click **Return to Present** button
- Jumps to current timeline position
- Current position saved per world

### Filtering Timeline

1. **Open Filter Panel**
   - Click **Filter** button in timeline toolbar

2. **Filter Options:**
   - **By Type**: Check event types to show
   - **By Tag**: Enter tags (comma-separated)
   - **By Date Range**: Enter start and end dates
   - **By Text**: Search event names/descriptions

3. **Apply Filters**
   - Timeline updates in real-time
   - Filtered events hidden but not deleted

4. **Clear Filters**
   - Click **Clear All** button

### Grouping Events

**Group By Type:**
- Events organized by type (battle, political, etc.)
- Collapsible groups

**Group By Tag:**
- Events organized by shared tags
- Events can appear in multiple groups

**No Grouping:**
- Pure chronological order

### Timeline Playhead

The **playhead** represents the "current" time in your world:

- Red vertical line on timeline
- Drag to move through time
- Used for temporal relation queries
- Position saved per world

**Use Cases:**
- View world state at specific time
- Show active relations at date
- Filter "past" vs "future" events

---

## Calendar System

### Default Calendar

ProjektKraken starts with a Gregorian-like calendar:
- 12 months (January-December)
- 7-day weeks (Monday-Sunday)
- Leap years every 4 years

### Creating a Custom Calendar

1. **Open Calendar Settings**
   - **Tools → Calendar Settings**

2. **Create New Calendar**
   - Click **New Calendar**
   - Enter calendar name (e.g., "Eldorian Calendar")

3. **Define Months**
   - Add months with names and day counts
   - Example: Spring (30), Summer (30), Autumn (30), Winter (30)

4. **Define Weeks**
   - Add day names
   - Example: Moonday, Tideday, Earthday, Fireday, Skyway, Starday, Sunday

5. **Leap Year Rules** (Optional)
   - Add leap year rule
   - Frequency: Every N years
   - Month to add day: Which month gets extra day

6. **Save Calendar**
   - Click **Save**

### Activating a Calendar

1. In Calendar Settings, select calendar
2. Click **Set Active**
3. All date fields now use custom calendar

### Calendar Conversion

- **Internal Storage**: All dates stored as floats (1.0 = 1 day)
- **Display**: Converted to calendar format automatically
- **Precision**: Sub-day resolution maintained (hours, minutes, seconds)

### Natural Language Dates with Calendar

Once a custom calendar is active:
- "1st of Spring" - First day of Spring month
- "15th of Autumn, Year 245" - Specific date
- "Moonday, 3rd week of Summer" - Week-based date

---

## Maps and Trajectories

### Creating a Map

1. **Create Map**
   - **Tools → Create Map** (or `Ctrl+Shift+M`)
   - Enter map name
   - Select image file (JPG, PNG)
   - Click **Create**

2. **Map Created**
   - Image stored in `worlds/[World Name]/assets/maps/`
   - Map appears in Maps list

### Viewing a Map

1. **Open Map**
   - Double-click map in Maps list
   - Or select map and click **Open**

2. **Map Widget**
   - Interactive pan and zoom
   - Shows markers for entities and events
   - Timeline playhead controls temporal display

### Adding Markers

**Manual Markers:**
1. Right-click on map
2. Select **Add Marker**
3. Choose entity or event
4. Marker placed at click position

**Automatic Markers:**
- Entities/events with location attributes automatically marked

### Map Calibration

**Purpose**: Set real-world scale for distance calculations

1. **Open Calibration**
   - Click **Calibrate** button in map toolbar

2. **Draw Distance Line**
   - Click start point on map
   - Click end point
   - Enter known distance (e.g., "100 miles")

3. **Apply Calibration**
   - Map now has scale
   - Distance calculations enabled

### Temporal Maps (Trajectories)

**Concept**: Entities move across maps over time.

**Creating a Trajectory:**
1. Select entity on map
2. Click **Add Trajectory Keyframe**
3. Set position and time
4. Repeat for multiple positions
5. System interpolates movement between keyframes

**Trajectory Format:**
- MF-JSON (OGC Moving Features JSON)
- Supports linear and curved interpolation
- Stores as temporal data

**Clock Mode:**
1. Enable **Clock Mode** in map toolbar
2. Drag timeline playhead
3. Markers move to positions at that time
4. Visualize entity positions throughout history

**Use Cases:**
- Character journeys
- Army movements during war
- Migration patterns
- Trade route evolution

---

## Wiki Linking

### Wiki Link Syntax

**Basic Syntax:**
```
[[Entity Name]]
```

**Examples:**
```
The [[Hero]] traveled to [[The Dark Tower]] and met [[The Wizard]].
```

**Auto-completion:**
- Type `[[` to trigger autocomplete
- List of all entities appears
- Arrow keys to select
- Enter to insert

### Creating Links

1. **In Description Field**
   - Type `[[`
   - Select or type entity name
   - Type `]]`

2. **Auto-Linking**
   - If entity exists, link is blue and clickable
   - If entity doesn't exist, link is red (broken link)

3. **Quick Entity Creation**
   - Click broken link
   - Choose "Create Entity"
   - Entity created and link resolved

### Navigating Links

**Click Link:**
- Ctrl+Click (or Cmd+Click on Mac)
- Opens linked entity in editor

**Back Navigation:**
- Use browser-style back button
- Or `Alt+Left Arrow`

### Backlinks

**View Backlinks:**
- Select an entity
- **Relations** section shows "Mentioned In"
- Lists all places where entity is wiki-linked

**Use Cases:**
- Find all references to a character
- See where a location is mentioned
- Track concept usage across world

### Wiki Link Parsing

**Technical Details:**
- Wiki links parsed into AST (Abstract Syntax Tree)
- Converted to HTML for display
- Source position tracking for cursor sync
- Supports nested markdown formatting

---

## Graph Visualization

### Opening Graph View

- **View → Graph View**
- Or click **Graph** tab in right panel

### Graph Display

**Nodes:**
- Events: Circle nodes
- Entities: Rounded square nodes
- Color-coded by type
- Size indicates connection count

**Edges:**
- Lines connecting nodes
- Labels show relation type
- Arrows indicate direction
- Color indicates relation category

### Graph Interaction

**Pan:**
- Click and drag background
- Or arrow keys

**Zoom:**
- Mouse wheel
- Or zoom buttons

**Select Node:**
- Click node to select
- Selected node highlighted
- Editor updates to show details

**Multi-Select:**
- Ctrl+Click to add to selection
- Drag to select multiple

**Move Node:**
- Drag node to reposition
- Physics simulation updates

### Graph Filtering

1. **Open Filter Bar**
   - Click **Filter** button

2. **Filter Options:**
   - **Node Types**: Show/hide event/entity types
   - **Relation Types**: Show/hide specific relation types
   - **Tags**: Filter by tags
   - **Depth**: Limit connection depth from selected node

3. **Apply Filters**
   - Graph updates in real-time

### Force-Directed Layout

**Physics Simulation:**
- Nodes repel each other
- Connected nodes attract
- Auto-arranges for readability

**Layout Controls:**
- **Strength**: Adjust force strength
- **Distance**: Set ideal edge length
- **Pause/Resume**: Freeze layout
- **Reset**: Re-run simulation

### Graph Export

**Export as Image:**
- **File → Export → Graph as PNG**
- Saves current view

**Export as JSON:**
- **File → Export → Graph Data**
- Node/edge data for external tools

---

## Longform Documents

### Creating a Document

1. **Create Longform Document**
   - **File → New Longform Document**
   - Enter document name
   - Click **Create**

2. **Document Structure**
   - Hierarchical outline
   - Chapters, sections, subsections
   - Rich text content

### Writing Content

**Editor Interface:**
- Left: Outline tree view
- Right: Content editor

**Adding Sections:**
1. Right-click in outline
2. Select **Add Section**
3. Enter section name
4. Start writing in editor

**Nested Sections:**
- Drag sections to nest under others
- Create hierarchical structure

**Content Formatting:**
- **Bold**: `Ctrl+B`
- **Italic**: `Ctrl+I`
- **Headings**: Select heading level from toolbar
- **Lists**: Bullet and numbered lists
- **Wiki Links**: Use `[[Entity Name]]` syntax

### Linking to World Data

**Embed Entity Information:**
- Use wiki links to reference entities
- Links resolve to entity data
- Clicking link opens entity in editor

**Timeline References:**
- Reference events by name
- Maintain consistency across documents

### Exporting Documents

**Export as Markdown:**
1. **File → Export → Longform as Markdown**
2. Choose output location
3. Document exported with formatting preserved

**Export as HTML:**
1. **File → Export → Longform as HTML**
2. Standalone HTML file with styles

**Export to Obsidian:**
1. **File → Export → To Obsidian**
2. Select Obsidian vault
3. Exports with wiki links compatible with Obsidian

---

## Semantic Search and AI

### Setting Up Semantic Search

**Prerequisites:**
- LM Studio or compatible OpenAI API server
- Embedding model (e.g., bge-small-en-v1.5)

**Configuration:**
1. Install and launch LM Studio
2. Download embedding model
3. Start local server (default: http://localhost:8080)
4. Set environment variables:
   ```bash
   export EMBED_PROVIDER=lmstudio
   export LMSTUDIO_EMBED_URL=http://localhost:8080/v1/embeddings
   export LMSTUDIO_MODEL=bge-small-en-v1.5
   ```

**Build Index:**
```bash
python -m src.cli.index rebuild --database "worlds/My World/My World.kraken"
```

### Using Semantic Search

1. **Open AI Search Panel**
   - **View → AI Search** (or press `Ctrl+Shift+F`)

2. **Enter Query**
   - Type natural language query
   - Example: "ancient wizard with staff"

3. **View Results**
   - Ranked results by relevance
   - Shows entities and events matching query

4. **Navigate to Result**
   - Click result to open in editor

### Query Examples

**Find Characters:**
- "brave knight who protects the kingdom"
- "mysterious old wizard"
- "young girl with magical powers"

**Find Locations:**
- "dark forest with ancient ruins"
- "bustling port city on the coast"
- "hidden mountain temple"

**Find Events:**
- "great battle that changed the kingdom"
- "discovery of magical artifact"
- "peace treaty between nations"

### LLM Generation

**Prerequisites:**
- LM Studio with text generation model
- Or OpenAI API key

**Generate Content:**
1. Select entity or event
2. Click **Generate with AI** button
3. Choose generation type:
   - Expand description
   - Generate backstory
   - Suggest plot hooks
   - Create dialogue
4. Review generated content
5. Accept or modify

**Custom Prompts:**
1. **Tools → LLM Prompts**
2. Create custom prompt templates
3. Use variables: `{entity_name}`, `{entity_type}`
4. Save and reuse

### RAG (Retrieval-Augmented Generation)

**Context-Aware Generation:**
- System retrieves relevant world data
- Passes to LLM as context
- Generated content consistent with world lore

**Example:**
1. Select character
2. Request "Generate backstory"
3. System retrieves:
   - Related events
   - Connected entities
   - Location information
4. LLM generates backstory using context
5. Result is lore-consistent

---

## Fast Inject System

### What is Fast Inject?

Fast Inject enables rapid creation of entities and events using templates with variable substitution.

**Use Cases:**
- Quickly populate world with NPCs
- Create sets of related entities
- Generate location hierarchies
- Batch create events

### Creating a Template

1. **Create Template File**
   - Location: `worlds/[World Name]/fastinject/my_template.json`

2. **Template Format:**
   ```json
   {
     "name": "{entity_name}",
     "type": "character",
     "description": "A {role} from {location}",
     "attributes": {
       "role": "{role}",
       "age": "{age}"
     },
     "tags": ["npc", "{role}"]
   }
   ```

3. **Variable Syntax:**
   - `{variable_name}` - Replaced at creation time
   - Can use in any string field

### Using Fast Inject

1. **Open Fast Inject**
   - **Tools → Fast Inject** (or `Ctrl+Shift+I`)

2. **Select Template**
   - Choose from available templates

3. **Fill Variables**
   - Enter values for each variable
   - Example:
     - entity_name: "Guard Captain Bran"
     - role: "guard_captain"
     - location: "Silverkeep"
     - age: "35"

4. **Create**
   - Click **Create**
   - Entity created instantly

### Batch Creation

**CSV Import:**
1. Create CSV file with columns matching variables
2. **Fast Inject → Batch Create**
3. Select template and CSV file
4. All rows processed automatically

**Example CSV:**
```csv
entity_name,role,location,age
Guard Bran,guard_captain,Silverkeep,35
Merchant Talia,merchant,Market District,42
Priest Eldrin,priest,Temple,58
```

---

## Undo and Redo

### Basic Undo/Redo

**Undo:**
- **Edit → Undo** (or `Ctrl+Z`)
- Reverses last action

**Redo:**
- **Edit → Redo** (or `Ctrl+Y` or `Ctrl+Shift+Z`)
- Re-applies undone action

**Supported Actions:**
- Create/edit/delete events
- Create/edit/delete entities
- Add/remove relations
- Move markers on map
- Edit attributes
- And more...

### History Panel

**Open History Panel:**
- **View → History Panel**

**History Display:**
- Visual list of all commands
- Recent commands at top
- Arrows indicate undo/redo position
  - ▲ Undo-able commands (above cursor)
  - ▼ Redo-able commands (below cursor)
- Color-coded by command type

**Navigate History:**
- Click any command to jump to that state
- Multi-step undo/redo

### Command History Persistence

**Persistent History:**
- Undo history saved with world
- Survives application close/reopen
- Edit sessions tracked

**History Limits:**
- Default: 100 commands
- Configurable in settings
- Old commands pruned automatically

---

## Backup and Recovery

### Automated Backups

**Auto-Save:**
- World saved automatically on changes
- No need to manually save

**Periodic Backups:**
- Automatic backups created periodically
- Location: User data directory / backups
- Retention policy: Keep last N backups

### Manual Backup

**Create Backup:**
1. **File → Backup World**
2. Choose backup location
3. Backup created as ZIP or JSON

**Backup Contents:**
- Database (.kraken file)
- All assets (images, attachments)
- World manifest
- Timestamp and metadata

### Restoring from Backup

**Restore World:**
1. **File → Restore World**
2. Select backup file
3. Choose restoration method:
   - **Full Restore**: Replace entire world
   - **Import**: Merge with existing world
4. Confirm restoration

**Backup Location:**
- Default: `%APPDATA%/ProjektKraken/backups/` (Windows)
- Or: `~/.local/share/ProjektKraken/backups/` (Linux)

### Data Recovery

**Undo for Mistakes:**
- Use undo/redo for recent mistakes
- Persistent history available

**Backup for Major Issues:**
- Use backups for corrupted worlds
- Test backups periodically

---

## Import and Export

### JSON Import

**Import World Data:**
1. **File → Import → From JSON**
2. Select JSON file
3. Choose import mode:
   - **Replace**: Replace entire world
   - **Merge**: Add to existing world
   - **Update**: Update existing, add new
4. Click **Import**

**Import Processing:**
- **Two-Pass System**:
  - Pass 1: Create all entities/events
  - Pass 2: Resolve relations and references
- **Deduplication**: Prevents duplicate imports
- **Cycle Resolution**: Handles circular references

**JSON Format:**
```json
{
  "entities": [
    {
      "id": "uuid-here",
      "name": "Character Name",
      "type": "character",
      "description": "...",
      "attributes": {}
    }
  ],
  "events": [...],
  "relations": [...]
}
```

### Export to JSON

**Export World:**
1. **File → Export → To JSON**
2. Choose export scope:
   - **Full World**: All data
   - **Selected**: Only selected entities/events
   - **Filtered**: Based on current filters
3. Select output location
4. Click **Export**

### Obsidian Export

**Export to Obsidian:**
1. **File → Export → To Obsidian**
2. Select Obsidian vault path
3. Choose options:
   - Include attachments
   - Convert wiki links
   - Folder structure
4. Click **Export**

**Output:**
- Each entity → Markdown file
- Each event → Markdown file
- Wiki links preserved
- Attachments copied

---

## Customization

### Themes

**Change Theme:**
1. **View → Themes**
2. Select theme from list
3. Theme applied immediately

**Available Themes:**
- Dark Mode (default)
- Light Mode
- Custom themes (if available)

**Custom Themes:**
- Edit `themes.json` in application directory
- Define colors, fonts, styles
- Reload application to apply

### Layout Customization

**Save Custom Layout:**
1. Arrange panels as desired
2. **View → Save Layout**
3. Layout saved automatically

**Reset Layout:**
- **View → Reset to Default Layout**
- Restores factory defaults

**Capture Default Layout (Developers):**
```bash
python -m src.app.main --set-default-layout
```
- Saves current layout as new default
- Stored in `src/assets/default_layout.json`

### Settings

**Application Settings:**
- **Edit → Preferences**
- Configure:
  - Auto-save interval
  - Backup retention
  - Theme selection
  - Font sizes
  - Timeline settings

### Keyboard Shortcuts

**Customize Shortcuts:**
- **Edit → Keyboard Shortcuts**
- Assign new shortcuts to actions
- Reset to defaults option

---

## Tips and Best Practices

### Worldbuilding Tips

1. **Start with Timeline**: Create major historical events first
2. **Use Tags Consistently**: Develop a tagging system early
3. **Wiki Link Everything**: Build connections naturally
4. **Document as You Go**: Don't wait to add descriptions
5. **Use Custom Attributes**: Track world-specific data

### Organization

1. **Naming Conventions**: Use consistent naming (e.g., "The Kingdom of X")
2. **Type Hierarchy**: Use types consistently
3. **Tag Taxonomy**: Create tag categories (character_type, location_type, etc.)
4. **Relation Discipline**: Use relation types meaningfully

### Performance

1. **Large Worlds**: Use filtering to focus on relevant data
2. **Graph View**: Filter deep graphs to improve performance
3. **Semantic Search**: Rebuild index periodically for accuracy
4. **Backups**: Keep backups separate from main world folder

### Collaboration

1. **Export/Import**: Share world data via JSON
2. **Version Control**: Store world in Git (use .gitignore for binaries)
3. **Documentation**: Use longform for world bible/style guide

---

## Troubleshooting

See [FAQ](FAQ.md) for common issues and solutions.

**Quick Fixes:**
- **App won't start**: `python launcher.py --reset-settings`
- **Corrupted world**: Restore from backup
- **Missing images**: Check `worlds/[World]/assets/` folder
- **Slow performance**: Reduce graph size, filter timeline

---

**Next:** See [Workflows](WORKFLOWS.md) for step-by-step tutorials.
