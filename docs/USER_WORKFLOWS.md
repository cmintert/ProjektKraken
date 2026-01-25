---
project: ProjektKraken
document: User Workflows Guide
last_updated: 2026-01-25
audience: End Users
---

# User Workflows Guide

This guide demonstrates common workflows in ProjektKraken for worldbuilding tasks. Each workflow includes step-by-step instructions with practical examples.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Building Your First World](#building-your-first-world)
3. [Timeline-First Worldbuilding](#timeline-first-worldbuilding)
4. [Character & Faction Workflows](#character--faction-workflows)
5. [Location & Map Workflows](#location--map-workflows)
6. [Event & Timeline Workflows](#event--timeline-workflows)
7. [Wiki Linking & Documentation](#wiki-linking--documentation)
8. [Semantic Search & AI Assistance](#semantic-search--ai-assistance)
9. [Export & Publishing](#export--publishing)
10. [Backup & Recovery](#backup--recovery)

---

## Getting Started

### First Launch

**Goal:** Create your first world and understand the interface.

1. **Launch ProjektKraken**
   - Run `ProjektKraken.exe` (Windows) or `python launcher.py` (from source)
   - The application creates a `worlds/` directory automatically

2. **Create a New World**
   - Click **File → New World** (or `Ctrl+N`)
   - Enter world name: e.g., "My Fantasy Campaign"
   - Choose template: "Blank World" or "Fantasy Starter"
   - Click **Create**

3. **Understand the Interface**
   - **Left Panel:** Timeline view (events listed chronologically)
   - **Center Panel:** Editor (edit entities, events, documents)
   - **Right Panel:** Relations graph or entity list
   - **Bottom Panel:** Timeline ruler (visual timeline)

4. **Explore the Workspace**
   - Drag panel dividers to resize
   - Click panel tabs to switch views
   - Use **View** menu to show/hide panels

**Result:** You now have an empty world ready for content.

---

## Building Your First World

### Workflow: Fantasy Campaign Setup

**Goal:** Create a basic fantasy world with locations, characters, and an opening event.

#### Step 1: Set Up Your Calendar

A custom calendar makes dates more immersive.

1. **Open Calendar Settings**
   - Click **Tools → Calendar Settings**
   
2. **Create Custom Calendar**
   - Click **New Calendar**
   - Name: "Eldorian Calendar"
   - Months: Enter month names and days
     ```
     Spring (30 days), Summer (30 days), Autumn (30 days), Winter (30 days)
     ```
   - Week: Enter day names
     ```
     Moonday, Tideday, Earthday, Fireday, Skyway, Starday, Sunday
     ```
   - Click **Save**

3. **Set as Active**
   - Select "Eldorian Calendar"
   - Click **Set Active**

**Result:** Date inputs now use your custom calendar (e.g., "1st of Spring, Year 1").

#### Step 2: Create Core Locations

Build your world's geography first.

1. **Create a Location Entity**
   - Click **Create → Entity** (or press `Ctrl+E`)
   - Name: "The Kingdom of Eldoria"
   - Type: Select "location"
   - Description: 
     ```
     A prosperous kingdom in the western valleys, 
     known for its skilled craftsmen and fertile lands.
     ```
   - Tags: Add "kingdom", "major_location"
   - Click **Save** (or `Ctrl+S`)

2. **Create Sub-Locations**
   - Repeat for:
     - "Capital City: Silverkeep" (type: location, tags: city, capital)
     - "The Darkwood Forest" (type: location, tags: wilderness, danger)
     - "Temple of the Dawn" (type: location, tags: temple, sacred)

3. **Create Relations Between Locations**
   - Select "Silverkeep" in the editor
   - In the **Relations** section, click **Add Relation**
   - Target: "The Kingdom of Eldoria"
   - Type: "located_in"
   - Click **Add**

**Result:** Your world now has a geography foundation.

#### Step 3: Create Characters

Populate your world with people.

1. **Create Main Character**
   - Click **Create → Entity** (or `Ctrl+E`)
   - Name: "Queen Lyanna Silverbrook"
   - Type: "character"
   - Description:
     ```
     The wise and just ruler of Eldoria. In her 20th year of reign,
     she is known for her diplomatic skills and devotion to her people.
     ```
   - Attributes (custom fields):
     - Age: 45
     - Role: Monarch
     - Alignment: Lawful Good
   - Tags: "royalty", "npc", "major_character"
   - Click **Save**

2. **Add Character Portrait**
   - In the editor, click **Gallery** tab
   - Click **Add Image**
   - Select portrait image from your files
   - Optionally add caption: "Queen Lyanna's official portrait"

3. **Link Character to Location**
   - In **Relations** section, click **Add Relation**
   - Target: "The Kingdom of Eldoria"
   - Type: "rules"
   - Click **Add**

4. **Create Supporting Characters**
   - Repeat for:
     - "Sir Marcus Brightblade" (Knight Commander)
     - "Eldrin the Wise" (Court Mage)
     - "Thalia Shadowstep" (Master of Spies)

**Result:** Your world has key characters with relationships.

#### Step 4: Create Founding Event

Establish your world's history.

1. **Create Historical Event**
   - Click **Create → Event** (or `Ctrl+Shift+E`)
   - Name: "The Founding of Eldoria"
   - Date: "1st of Spring, Year 1" (or use float: `1.0`)
   - Type: "historical"
   - Description:
     ```
     King Aldric Silverbrook united the warring clans of the western
     valleys and established the Kingdom of Eldoria, bringing an era
     of peace and prosperity.
     ```
   - Tags: "founding", "historical", "kingdom"
   - Click **Save**

2. **Link Event to Entities**
   - In **Relations** section:
     - Add relation to "The Kingdom of Eldoria" (type: "founded")
     - Add relation to dynasty entity if created (type: "established")

3. **Create Recent Event**
   - Name: "The Harvest Festival"
   - Date: "15th of Autumn, Year 245" (current time in your story)
   - Type: "celebration"
   - Description: Annual harvest celebration at Silverkeep
   - Link to: Queen Lyanna (type: "attended"), Silverkeep (type: "held_at")

**Result:** Your world has temporal context - past and present.

---

## Timeline-First Worldbuilding

### Workflow: Building a Historical Timeline

**Goal:** Create a rich history spanning centuries.

#### Quick Timeline Creation

1. **Start with Major Eras**
   ```
   Year 1     - "The Founding of Eldoria" (historical)
   Year 50    - "The Mage Wars Begin" (conflict)
   Year 75    - "Peace Treaty of Dawn" (political)
   Year 100   - "The Great Drought" (disaster)
   Year 150   - "Discovery of Iron Deposits" (discovery)
   Year 200   - "Current Age"
   ```

2. **Use Batch Event Creation**
   - Create events in chronological order
   - Use relative dates: "2 years later", "50 days after"
   - Group related events with shared tags

3. **Add Duration for Long Events**
   - The Mage Wars: Start date + 25 year duration
   - The Great Drought: 10 year duration
   - Shows as a bar on timeline

#### Timeline Navigation

1. **Jump to Time Period**
   - Use the timeline ruler at bottom
   - Click on a year to jump there
   - Drag the playhead to scrub through time

2. **Filter Timeline View**
   - Click **Filter** button in timeline panel
   - Filter by:
     - Event type (historical, combat, political)
     - Tags (war, peace, discovery)
     - Date range (Year 1-100)

3. **Group Events**
   - Right-click timeline → **Group By**
   - Options: Type, Tags, No Grouping
   - Organizes events into collapsible sections

**Result:** A navigable historical timeline for your world.

---

## Character & Faction Workflows

### Workflow: Character Biography with Timeline

**Goal:** Track a character's life events and relationships over time.

#### Create Character with Life Events

1. **Create Character Entity**
   - Name: "Aric Stormborn"
   - Type: "character"
   - Description: Brief background
   - Tags: "player_character", "warrior"

2. **Create Birth Event**
   - Name: "Birth of Aric Stormborn"
   - Date: "10th of Winter, Year 215"
   - Type: "life_event"
   - Description: "Born to peasant farmers during a fierce storm"
   - Link to character (type: "birth_of")

3. **Create Life Milestones**
   - "Aric's Training Begins" (Year 230, age 15)
   - "Aric Earns Knighthood" (Year 235, age 20)
   - "The Battle of Crimson Pass" (Year 240, age 25)

4. **Use Wiki Links in Descriptions**
   ```
   Born in [[The Village of Millbrook]] to [[Harold Stormborn]] 
   and [[Mira Stormborn]]. Later trained under [[Sir Marcus Brightblade]]
   at [[The Knight's Academy]].
   ```
   - Typing `[[` triggers autocomplete
   - Links create automatic "mentions" relations

5. **Track Relationships**
   - Add relations:
     - To "Sir Marcus Brightblade" (type: "trained_by")
     - To "Queen Lyanna" (type: "serves")
     - To "The Village of Millbrook" (type: "born_in")

**Result:** Character has a documented life story on the timeline.

### Workflow: Faction with Members and Goals

**Goal:** Create an organization with hierarchy and agenda.

1. **Create Faction Entity**
   - Name: "The Order of the Silver Dawn"
   - Type: "faction"
   - Description: "Elite knights dedicated to protecting Eldoria"
   - Attributes:
     - Motto: "Light through Darkness"
     - Founded: Year 50
     - Members: ~200
   - Tags: "military", "knights", "active"

2. **Create Member Entities**
   - Link existing characters to faction
   - Relation type: "member_of"
   - Add attribute to relation: "rank" = "Knight Commander"

3. **Create Faction Events**
   - "Founding of the Order" (Year 50)
   - "The Great Crusade" (Year 100-105)
   - "Current Recruitment Drive" (Year 245)

4. **Document Faction Goals**
   - Use **Longform Editor**:
     - Create document entry titled "The Order of the Silver Dawn"
     - Add sections:
       - History
       - Structure & Hierarchy
       - Current Objectives
       - Key Members

**Result:** Faction with documented history, members, and narrative.

---

## Location & Map Workflows

### Workflow: Create Locations with Maps

**Goal:** Build visual geography for your world.

#### Upload World Map

1. **Create Map**
   - Click **Maps** tab (or **View → Maps**)
   - Click **New Map**
   - Name: "Eldoria - Political Map"
   - Click **Choose Image** → select your map file
   - Click **Create**

2. **Calibrate Map Coordinates**
   - Map uses normalized coordinates (0.0 to 1.0)
   - Top-left: (0, 0)
   - Bottom-right: (1, 1)
   - Click anywhere to test coordinates

#### Add Location Markers

1. **Place Capital City**
   - With map open, click **Add Marker**
   - Link to entity: "Silverkeep"
   - Click on map where city is located
   - Marker appears with entity name

2. **Place Other Locations**
   - Repeat for:
     - "Darkwood Forest"
     - "Temple of the Dawn"
     - "The Iron Mountains"

3. **Customize Marker Icons**
   - Right-click marker → **Properties**
   - Choose icon: city, forest, mountain, temple
   - Set color: Can use faction colors

#### Temporal Maps (Movement Over Time)

1. **Create Journey Event**
   - Name: "Aric's Quest for the Crystal"
   - Date: "1st of Spring, Year 245"
   - Duration: 60 days

2. **Add Trajectory to Map**
   - In map view, enable **Temporal Mode**
   - Select entity: "Aric Stormborn"
   - Click **Add Keyframe**:
     - Time: Day 0 (Spring 1st) → Position: Silverkeep
     - Time: Day 30 (Spring 30th) → Position: Darkwood Forest
     - Time: Day 60 (Autumn 1st) → Position: Temple of the Dawn
   
3. **Scrub Timeline on Map**
   - Use time slider at bottom of map
   - Watch marker move along trajectory
   - Shows Aric's position at any point in journey

**Result:** Visual geography with temporal movement tracking.

---

## Event & Timeline Workflows

### Workflow: Plan and Execute a Campaign

**Goal:** Create a session-by-session campaign structure.

#### Campaign Planning

1. **Create Campaign Arc Event**
   - Name: "Act I: The Rising Shadow"
   - Date: "1st of Spring, Year 245"
   - Duration: 90 days (3 months of sessions)
   - Type: "campaign_arc"
   - Description: Overview of act

2. **Create Session Events**
   ```
   Session 1: "The Call to Adventure" (Spring 1st)
   Session 2: "Into the Darkwood" (Spring 8th)
   Session 3: "The Temple's Secret" (Spring 15th)
   Session 4: "Betrayal at Midnight" (Spring 22nd)
   ```

3. **Link Sessions to Arc**
   - Each session event:
     - Add relation to "Act I" (type: "part_of")
     - Link to participating characters (type: "participated")

4. **Track Session Notes**
   - In each session event description, use template:
     ```
     ## What Happened
     - Party arrived at [[Darkwood Forest]]
     - Encountered [[Ancient Guardian]]
     - Found clue about [[The Shadow Cult]]
     
     ## NPCs Met
     - [[Eldrin the Hermit]] - gave party quest
     
     ## Loot
     - Ring of Protection +1
     - 500 gold pieces
     
     ## Next Session Hook
     - Must reach [[Temple of the Dawn]] before full moon
     ```

5. **Use Fast Inject for NPCs**
   - Create template: "Random NPC"
   - Variables: Name, Role, Location
   - Quick-generate NPCs during sessions
   - Click **Tools → Fast Inject** → select template

**Result:** Organized campaign with session history.

### Workflow: Battle Event with Participants

**Goal:** Document a major battle with all involved parties.

1. **Create Battle Event**
   - Name: "The Siege of Silverkeep"
   - Date: "15th of Summer, Year 245"
   - Duration: 3 days
   - Type: "combat"
   - Tags: "siege", "major_battle", "act_one"

2. **Link All Participants**
   - Add relations:
     - Queen Lyanna (type: "defended")
     - Aric Stormborn (type: "fought_in")
     - The Shadow Cult (type: "attacked")
     - Order of the Silver Dawn (type: "defended")
     - 20+ individual character entities

3. **Document Battle Stages**
   - Use **Longform Editor** or event description:
     ```
     ## Day 1: The Arrival
     The [[Shadow Cult]] army arrived at dawn...
     
     ## Day 2: The Breach
     The walls were breached at the eastern gate...
     
     ## Day 3: The Final Stand
     [[Aric Stormborn]] led the counter-charge...
     ```

4. **Create Aftermath Events**
   - "Casualties of the Siege" (linked to individual deaths)
   - "Victory Celebration" (linked to survivors)
   - "Reconstruction Begins" (linked to damaged locations)

5. **Visualize in Graph View**
   - Click **Graph** tab
   - Filter to show battle event + all linked entities
   - See web of relationships

**Result:** Comprehensive battle documentation with all connections.

---

## Wiki Linking & Documentation

### Workflow: Build an Interconnected World

**Goal:** Create a wiki-style knowledge base with cross-references.

#### Use Wiki Links Everywhere

1. **Enable Auto-Completion**
   - Already enabled by default
   - Type `[[` in any description field
   - Autocomplete shows matching entities/events

2. **Write Natural Descriptions**
   ```
   [[Queen Lyanna Silverbrook]] rules from [[Silverkeep]], the capital
   of [[The Kingdom of Eldoria]]. Her reign began after the death of
   her father, [[King Aldric III]], during [[The Great Plague]].
   
   She is advised by [[Eldrin the Wise]] and protected by the
   [[Order of the Silver Dawn]], led by [[Sir Marcus Brightblade]].
   ```

3. **Navigate via Links**
   - `Ctrl+Click` any wiki link to jump to that entity
   - Creates "mentions" relation automatically
   - Use **Back** button to return

4. **Find Broken Links**
   - Click **Tools → Validate Wiki Links**
   - Shows links pointing to non-existent entities
   - Options: Create entity, update link, remove link

#### Create a Longform Codex

1. **Open Longform Editor**
   - Click **Longform** tab (or **View → Longform Document**)
   
2. **Build Hierarchical Structure**
   ```
   World Codex
   ├── Geography
   │   ├── [[The Kingdom of Eldoria]]
   │   ├── [[Silverkeep]]
   │   └── [[Darkwood Forest]]
   ├── History
   │   ├── [[The Founding of Eldoria]]
   │   ├── [[The Mage Wars]]
   │   └── [[Peace Treaty of Dawn]]
   ├── Factions
   │   ├── [[Order of the Silver Dawn]]
   │   └── [[The Shadow Cult]]
   └── Characters
       ├── Major Characters
       │   ├── [[Queen Lyanna Silverbrook]]
       │   └── [[Aric Stormborn]]
       └── Supporting Cast
   ```

3. **Add Document Entries**
   - Click **Add Entry** → select entity/event
   - Drag to reorder or nest under parents
   - Each entry shows entity's full description

4. **Add Narrative Sections**
   - Click **Add Section** (creates text-only node)
   - Write connecting narrative:
     ```
     ## The Age of Heroes
     
     Following the Mage Wars, a new generation of heroes arose
     to shape the future of Eldoria...
     ```

5. **Export to Markdown**
   - Click **File → Export Longform**
   - Generates single markdown file with full hierarchy
   - Includes all linked entity descriptions
   - Perfect for sharing with players

**Result:** Comprehensive codex with all world knowledge.

---

## Semantic Search & AI Assistance

### Workflow: Find and Generate Content

**Goal:** Use AI to search and generate world content.

#### Set Up Semantic Search

1. **Configure LLM Provider**
   - Click **Tools → AI Settings**
   - Choose provider:
     - **LM Studio** (local, recommended): Set URL to `http://localhost:8080`
     - **OpenAI**: Enter API key
     - **Anthropic**: Enter API key
   - Select embedding model (for search)
   - Select generation model (for content creation)
   - Click **Save**

2. **Build Search Index**
   - Click **Tools → Rebuild Search Index**
   - Or use CLI: `python -m src.cli.index rebuild -d world.kraken`
   - Wait for indexing to complete (shows progress)
   - Index stored in user data directory

#### Search Your World

1. **Open AI Search Panel**
   - Click **View → AI Search Panel** (or press `Ctrl+F`)
   - Panel appears in sidebar

2. **Natural Language Search**
   - Type: "characters who are knights"
   - Results show: Sir Marcus, Aric Stormborn, etc.
   - Click result to open in editor

3. **Advanced Queries**
   ```
   "locations in the western region"
   "events involving the Shadow Cult"
   "all battles in Year 245"
   "characters trained by Marcus"
   "magical artifacts"
   ```

4. **Filter Search Results**
   - Use dropdowns:
     - Type: Entity, Event, or Both
     - Limit: 5, 10, 20 results

**Result:** Fast retrieval of world information.

#### Generate Content with AI

1. **Generate Entity Description**
   - Select an entity with minimal description
   - Click **AI** button in editor
   - Choose: "Expand Description"
   - Review generated text
   - Click **Accept** to keep, **Reject** to discard

2. **Generate Character Background**
   - Select character entity
   - Click **AI** → **Generate Background**
   - Prompt: "Create a detailed background for [Character Name], including childhood, training, and motivations"
   - AI uses existing world context (RAG)
   - Edit and refine generated content

3. **Generate Event Details**
   - Select event with basic info
   - Click **AI** → **Generate Details**
   - AI expands event description using related entities
   - Maintains consistency with existing lore

4. **Custom Prompts**
   - Click **Tools → Custom Prompts**
   - Create reusable prompts:
     ```
     "Generate a detailed physical description for this character"
     "Create a legend about this location"
     "Write a dramatic account of this battle from a soldier's perspective"
     ```

**Result:** AI-assisted content creation with world awareness.

---

## Export & Publishing

### Workflow: Share Your World

**Goal:** Export world data for various uses.

#### Export to Markdown

1. **Export Longform Document**
   - Click **File → Export Longform**
   - Choose output file: `world_codex.md`
   - Options:
     - Include descriptions: Yes
     - Include attributes: Optional
     - Include relations: Optional
   - Click **Export**

2. **Export Individual Entities**
   - Right-click entity → **Export to Markdown**
   - Creates single markdown file with all details

**Result:** Markdown files for sharing or publishing.

#### Export to Obsidian

1. **Export World to Obsidian Vault**
   - Click **File → Export to Obsidian**
   - Or use CLI: `python -m src.cli.obsidian export -d world.kraken --vault-path ./vault`
   
2. **Vault Structure**
   ```
   vault/
   ├── Entities/
   │   ├── Queen Lyanna Silverbrook.md
   │   ├── Aric Stormborn.md
   │   └── ...
   ├── Events/
   │   ├── The Founding of Eldoria.md
   │   ├── The Siege of Silverkeep.md
   │   └── ...
   └── Maps/
       └── images/
   ```

3. **Open in Obsidian**
   - Open vault in Obsidian
   - Wiki links work natively
   - View graph view
   - Edit and reimport if needed

**Result:** Obsidian vault for portable note-taking.

#### Export to JSON

1. **Export All Data**
   - Click **File → Export to JSON**
   - Or use CLI: `python -m src.cli.importer export -d world.kraken --output export.json`

2. **JSON Structure**
   ```json
   {
     "entities": [...],
     "events": [...],
     "relations": [...]
   }
   ```

3. **Use Cases**
   - Backup before major changes
   - Share with other tools
   - Custom processing with scripts
   - Import into other ProjektKraken worlds

**Result:** Portable data format for flexibility.

#### Web API Access

1. **Start World**
   - Open world in ProjektKraken
   - Embedded webserver starts automatically on `http://localhost:8000`

2. **Access Longform Document**
   ```bash
   # In browser
   http://localhost:8000/longform
   
   # Or curl
   curl http://localhost:8000/longform > world.html
   ```

3. **Health Check**
   ```bash
   curl http://localhost:8000/health
   # Returns: {"status": "ok"}
   ```

**Result:** Live web access to world data.

---

## Backup & Recovery

### Workflow: Protect Your World

**Goal:** Ensure your world data is never lost.

#### Automatic Backups

1. **Configure Auto-Save**
   - Enabled by default
   - Saves every 5 minutes
   - No user action required

2. **Check Backup Settings**
   - Click **Tools → Backup Settings**
   - Options:
     - Auto-save interval: 5 minutes
     - Daily backups: Enabled (keeps last 7)
     - Weekly backups: Enabled (keeps last 4)
     - Monthly backups: Enabled (keeps last 12)

3. **View Backup Location**
   - Backups stored in user data directory:
     - Windows: `%APPDATA%\ProjektKraken\backups\`
     - macOS: `~/Library/Application Support/ProjektKraken/backups/`
     - Linux: `~/.local/share/ProjektKraken/backups/`

**Result:** Automatic protection against data loss.

#### Manual Backup

1. **Create Manual Backup**
   - Click **File → Create Backup** (or `Ctrl+B`)
   - Or use CLI: `python -m src.cli.backup create -d world.kraken`
   - Backup saved with timestamp
   - Labeled as "Manual" backup

2. **Save Backup Externally**
   - Copy world folder: `worlds/My Fantasy World/`
   - Includes:
     - `world.kraken` (database)
     - `world.json` (manifest)
     - `assets/` (all images)
   - Store on external drive, cloud storage, etc.

**Result:** Additional backup for peace of mind.

#### Restore from Backup

1. **List Available Backups**
   - Click **File → Restore from Backup**
   - Shows all backups with timestamps
   - Types: Auto-save, Daily, Weekly, Monthly, Manual

2. **Preview Backup**
   - Select backup from list
   - Shows:
     - Date created
     - Size
     - Number of entities/events
   - Click **Preview** to see contents

3. **Restore Backup**
   - Select backup
   - Click **Restore**
   - Confirm: "This will replace current world data"
   - Click **Yes**
   - World restored to backup state

4. **CLI Restore**
   ```bash
   # List backups
   python -m src.cli.backup list -d world.kraken
   
   # Restore specific backup
   python -m src.cli.backup restore -d world.kraken --backup-id <id>
   ```

**Result:** World recovered to previous state.

---

## Advanced Workflows

### Workflow: Campaign Session Tracking

**Goal:** Track every session with full detail.

1. **Session Template**
   - Create fast inject template: "Session Note"
   - Variables:
     - Session Number: `{{session_num}}`
     - Date: `{{date}}`
     - Title: `{{title}}`
   - Attributes:
     - Present Players: `{{players}}`
     - XP Gained: `{{xp}}`
     - Loot: `{{loot}}`

2. **Pre-Session Setup**
   - Create session event
   - Link to expected participants
   - Add "planned" tag

3. **During Session**
   - Take notes in event description
   - Create entities as needed (NPCs, locations)
   - Use wiki links liberally
   - Update character attributes (HP, XP, inventory)

4. **Post-Session**
   - Update session event with outcomes
   - Create follow-up events (rumors, consequences)
   - Tag completed quests
   - Export session notes to share with players

### Workflow: Multiple Timelines / Parallel Stories

**Goal:** Track multiple story threads happening simultaneously.

1. **Use Event Tags**
   ```
   Main Campaign: "campaign_main"
   Side Quest A: "sidequest_rescue"
   Side Quest B: "sidequest_artifact"
   Faction Story: "faction_order_dawn"
   ```

2. **Filter Timeline Views**
   - Create multiple timeline tabs
   - Each filtered to different tag
   - Switch between story threads easily

3. **Show Temporal Overlap**
   - Both quests happening during "Summer, Year 245"
   - Timeline shows events side-by-side
   - Understand what's happening when

4. **Link Convergence Points**
   - Create event: "All Threads Converge"
   - Link to all active storylines
   - Shows relationships in graph view

### Workflow: World Consistency Checking

**Goal:** Ensure no contradictions in your lore.

1. **Use Semantic Search**
   - Query: "events mentioning dragons"
   - Review all dragon references
   - Ensure consistent portrayal

2. **Check Character Ages**
   - Birth event + current date = age
   - Search for all age mentions
   - Verify consistency

3. **Map Location Consistency**
   - View all events at a location
   - Ensure geography makes sense
   - Check travel times between locations

4. **Export and Review**
   - Export full world to markdown
   - Read through entire codex
   - Note inconsistencies
   - Update as needed

---

## Tips & Best Practices

### Naming Conventions

- **Entities:** Use proper nouns: "Queen Lyanna", "The Darkwood"
- **Events:** Use descriptive titles: "The Siege of Silverkeep", not just "Siege"
- **Tags:** Use lowercase, underscores: "player_character", "major_battle"

### Organization

- **Tag Everything:** Makes filtering and searching easier
- **Use Types:** Leverage entity/event types for organization
- **Consistent Dates:** Stick to one date format (calendar or float)

### Performance

- **Index Regularly:** Rebuild search index after major additions
- **Limit Images:** Use reasonable image sizes (< 5MB each)
- **Archive Old Content:** Tag completed arcs as "archived"

### Collaboration

- **Export Often:** Share exports with co-GMs or players
- **Use JSON Export:** For backing up before others make changes
- **Document Conventions:** Share tag/naming conventions with team

### Backup Strategy

1. **Auto-save:** Enabled (recovers from crashes)
2. **Manual before major changes:** Before importing, restructuring
3. **External backups:** Weekly copy to external drive
4. **Version control:** Consider git for world folder (advanced)

---

## Getting Help

### Documentation

- **[INDEX.md](INDEX.md)** - Complete documentation index
- **[CLI.md](CLI.md)** - Command-line tools reference
- **[WIKI_LINKING.md](WIKI_LINKING.md)** - Wiki syntax guide
- **[MAP_USAGE_EXAMPLES.md](MAP_USAGE_EXAMPLES.md)** - Map system details
- **[SEMANTIC_SEARCH.md](SEMANTIC_SEARCH.md)** - AI search setup
- **[LLM_INTEGRATION.md](LLM_INTEGRATION.md)** - LLM provider configuration

### Support

- **GitHub Issues:** Report bugs or request features
- **Discussions:** Ask questions, share workflows
- **Documentation:** Check docs/ folder for technical details

---

## Summary

ProjektKraken provides flexible workflows for worldbuilding:

✅ **Timeline-First:** Events are the foundation
✅ **Wiki-Style:** Everything interconnected with links
✅ **Visual:** Maps and graphs show relationships
✅ **AI-Powered:** Search and generate content
✅ **Portable:** Export to multiple formats
✅ **Safe:** Automatic backups protect your work

Start simple with a few entities and events, then expand as your world grows. The system grows with your needs.

Happy worldbuilding! 🌍✨
