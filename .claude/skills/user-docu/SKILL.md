---
name: user-docu
description: Generate user-facing documentation from Python code (especially PySide6 apps). Triggers on "create user docs", "write documentation for this feature", "generate end-user guide", "create docs for Projekt Kraken", or when pasting code asking for user-facing documentation.
user-invocable: true
metadata:
  triggers:
    - create user docs
    - write documentation for this feature
    - generate end-user guide
    - create docs for Projekt Kraken
    - user-facing documentation
---

# User Documentation Generator

Converts Python application code into end-user-focused markdown documentation. Extracts features and explains what users can accomplish, how to use the feature, and common workflows — without exposing technical internals.

## When to Use

- Documenting new features in ProjektKraken (Entity Inspector, Map Editor, Timeline, Graph View, etc.)
- Creating user guides for worldbuilders on how to use the app
- Extracting user-facing documentation from widgets and commands
- Building help pages for specific workflows (creating entities, establishing relations, designing maps, etc.)

## How It Works

The skill extracts features from your code and produces markdown documentation structured for end users:

1. **Identifies features** — UI components, data systems, workflows, and tools users interact with
2. **Extracts capabilities** — What users can do with the feature
3. **Generates step-by-step guides** — How to use each feature
4. **Documents workflows** — Real, recognizable multi-step user tasks
5. **Adds tips and gotchas** — Common mistakes and helpful advice

## Output Structure

Each feature gets one `.md` file with these sections:

### What This Does
A plain-language explanation of what the feature accomplishes. No jargon, no technical terms.

### What You Can Do
- Action-oriented capabilities (e.g., "Select hexes", "Highlight paths")
- Outcome-focused, not implementation-focused
- Active voice throughout

### How to Use It
Task-by-task instructions with:
- Step-by-step walkthroughs
- UI guidance ("Click the button labeled...")
- Expected results ("You'll see...")

### Common Workflows
Real, multi-step user tasks showing how features work together.

### Tips & Gotchas
Helpful hints and common mistakes users encounter.

## Target Audience

- End users of the application (non-technical)
- Game masters / worldbuilders using the app
- Anyone using the feature without needing implementation details

## Key Principles

- **User-centric**: Document outcomes, not implementation
- **Plain language**: No "entities", "signals", "instantiation", or "methods"
- **Task-focused**: Show how to do things, not how the system works
- **Actionable**: Every instruction must be followable by non-technical users
- **Non-technical**: Assume zero knowledge of Python or Qt

## What to Exclude ❌

- Class names, method signatures, type hints
- "Under the hood" explanations
- Data structure details
- Internal APIs or private methods
- Code examples (except UI instructions like "click the button labeled X")
- Architecture or design patterns
- Performance considerations (unless they directly affect the user)

## What to Include ✅

- What the user can do (capabilities)
- Why they'd want to do it (motivation)
- How to do it (step-by-step instructions)
- What they'll see (expected outcomes)
- Common tasks and workflows
- Tips, warnings, and gotchas
- How this feature connects to other features (from a user perspective)

## Feature Extraction Rules

### What counts as a feature?

- A UI component the user interacts with
- A data system the user works with (entities, events, relationships)
- A workflow or tool the user employs (import/export, search)

### How to identify features in ProjektKraken

1. **Think like a worldbuilder**: What would a GM or author call this? Examples from ProjektKraken:
   - "Entity Inspector" (viewing/editing characters, locations, factions)
   - "Event Timeline" (viewing and organizing historical events)
   - "Relation Graph" (visualizing connections between entities)
   - "Map Editor" (designing world maps with markers, regions, layers)
   - "Calendar System" (establishing time periods and date systems)
   - "Search" (finding entities, events, and content)
   - "Longform Editor" (writing narrative documents and wiki entries)
   - "Raster Layer Editor" (adding themed regions to maps)

2. Look for distinct user workflows with independent, recognizable tasks
3. Check docstrings for feature markers (e.g., `"""Feature: Timeline Display"""`)
4. Multiple files often constitute one feature (e.g., map editing spans `map_graphicsview.py`, `raster_layer_item.py`, `marker_commands.py`)

## File Naming

Use lowercase with hyphens: `entity-inspector.md`, `event-timeline.md`, `relation-graph.md`, `map-editor.md`, `calendar-system.md`

## ProjektKraken Domain Language

When documenting ProjektKraken features, use the user's vocabulary:

- **Entities**: Characters, locations, factions, organizations, objects — anything that exists in the world
- **Events**: Points in time, historical moments, story beats — things that happen
- **Relations**: Connections between entities (e.g., "is ally of", "rules over", "parent of")
- **Maps**: Spatial representations of the world (hex grids, geographic maps, floor plans)
- **Markers**: Points of interest on maps (cities, landmarks, dungeons)
- **Layers**: Themed overlays on maps (political boundaries, climate zones, magical effects)
- **Calendar**: The world's time system (years, months, seasons, eras)
- **Longform**: Narrative documents and worldbuilding notes (wiki entries, backstory, lore)
- **Tags**: Organizational labels for grouping related content
- **Search**: Finding content across entities, events, and notes (both text search and semantic search)

**Avoid** technical terms like "repository", "command", "widget", "signal", "database", "serialization". Use plain language instead.

Common User Workflows in ProjektKraken:

1. **Building the cast**: Create entities (characters, NPCs), add details, establish relationships
2. **Timeline building**: Create events, date them on the calendar, arrange chronologically
3. **World mapping**: Design maps, place markers, add themed layers (climate, politics, magic)
4. **Lore writing**: Write longform documents, link to entities, build a wiki
5. **Searching**: Find entities by name, search notes by content, discover relations
6. **Organizing**: Tag content, group related entities, establish hierarchies

## Deduplication

Always check if documentation for the feature already exists or overlaps with existing docs. If so, edit the existing file instead of creating a new one. Avoid redundancy across documentation files.

## Example Transformation

### ❌ Technical Focus (Wrong)

```markdown
# EntityInspectorWidget

## Core Features

### Entity Editor Panel
The `EntityEditorPanel` widget allows programmatic updates to entity attributes via the `update_entity_details()` method. Supports the `EntityUpdatedSignal` for reactivity.

### Relation Manager
Manages entity-relation connections via `RelationRepository`. Emits `relations_changed_signal` when the relation graph is modified.

### Event Timeline
Displays entity events chronologically. Internally queries `EventRepository` filtered by entity ID.
```

### ✅ User-Focused (Correct)

```markdown
# Entity Inspector

## What This Does
The Entity Inspector is where you view and edit all the details about a character, location, faction, or other element in your world. You can see everything about an entity in one place, add new details, update existing information, and see what events involve this entity.

## What You Can Do
- View an entity's name, description, and custom attributes
- Edit any detail about an entity at any time
- Add new information and custom fields
- See all events connected to an entity (timeline)
- View relationships to other entities
- Add tags and notes to organize your world
- Attach images and documents to entities

## How to Use It

### View an Entity's Details
1. Click on an entity in the Explorer to select it
2. The Entity Inspector opens on the right side
3. You'll see all the information about that entity

### Edit Entity Information
1. Click on any field in the Inspector (name, description, etc.)
2. Type or paste new information
3. Changes save automatically

### Add Relationships to an Entity
1. In the Entity Inspector, go to the "Relationships" section
2. Click "Add Relationship"
3. Select another entity and the type of relationship (e.g., "is parent of", "rules over")
4. The relationship appears in both entities

## Common Workflows

### Create a New Character
1. Click "New Entity" in the toolbar
2. Type the character's name
3. Click the Inspector to add details (description, role, background)
4. Add relationships to other characters
5. Tag them (e.g., "NPC", "Companion", "Enemy")

### Track a Location's History
1. Open a location entity in the Inspector
2. Look at the "Events" section to see what happened there
3. Add new events by clicking "Create Event" and linking them to this location

## Tips & Gotchas
- Changes save automatically, so don't worry about losing work
- You can create custom fields to track anything unique about your entities (allegiance, power level, magical abilities, etc.)
- Searching will find entities by name or by the text in their descriptions
```

## Quality Checklist

Before finalizing documentation:

- [ ] Overview explains the feature in plain language (no jargon)
- [ ] "What You Can Do" lists are action-oriented and user-focused
- [ ] "How to Use It" instructions are step-by-step and followable
- [ ] Workflows show real, recognizable user tasks
- [ ] No code internals, no class/method names in the user docs
- [ ] Tips & Gotchas address common user confusion
- [ ] All outcomes and results are clear ("You'll see...", "This allows you to...")

## Code Architecture Context

When extracting documentation from ProjektKraken code, know where to look:

**UI Widgets** (`src/gui/widgets/`)
- These contain the user-facing features
- Look at widget constructors and public methods to understand what users can do
- Check docstrings for feature descriptions
- Examine signal emissions to understand outcomes ("what happens when the user clicks this?")

**Commands** (`src/commands/`)
- Commands represent user actions (CreateEntityCommand, AddMarkerCommand, etc.)
- Command names often translate directly to user workflows
- The `execute()` method shows what the action accomplishes

**Services** (`src/services/`)
- Services handle data and complex operations behind the scenes
- User documentation should focus on *outcomes*, not service logic
- Example: Don't explain "SearchService does lexical + semantic search", say "Search finds entities by name and by content"

**Domain Models** (`src/core/`)
- Entity, Event, Relation, Map, Calendar, etc. represent what users work with
- The attributes on these models are often the "details" users can edit
- Docstrings on models explain what each thing represents

**Workflows & Multi-Feature Tasks**
- Many user workflows involve multiple widgets and commands working together
- Document the *user's perspective* of these workflows, not the technical coordination
- Example: "Creating a character" involves EntityInspector + RelationManager + Timeline view, but users just think of it as one task