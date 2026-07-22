# Workflows Guide

**Version:** 0.11.0 (Beta)  
**Last Updated:** February 2026

Step-by-step guides for common tasks and advanced workflows in ProjektKraken.

---

## Table of Contents

1. [Basic Workflows](#basic-workflows)
2. [Timeline Management](#timeline-management)
3. [Building a World](#building-a-world)
4. [Advanced Relation Management](#advanced-relation-management)
5. [Map Workflows](#map-workflows)
6. [Search and Discovery](#search-and-discovery)
7. [Export and Sharing](#export-and-sharing)
8. [Optimization Tips](#optimization-tips)

---

## Basic Workflows

### Creating Your First Event

**Goal**: Add a major historical event to your timeline.

1. **Create the Event**
   - Press **Ctrl+Shift+E** or **Events → New Event**
   - Enter name: "The Fall of the Old Empire"
   - Enter date: "Year 1234, Day 100"
   - Select type: "Battle" or "Political Event"
   - Click **Create**

2. **Add Details**
   - In Event Editor, write description:
     ```
     The [[Old Empire]] fell after a devastating siege.
     [[King Magnus]] was killed in battle.
     This event led to [[The Great Schism]].
     ```
   - Add tags: "major", "turning-point", "war"

3. **Link to Entities**
   - Drag "Old Empire" entity from Project Explorer
   - Drop on Event Editor
   - Hold **Shift** to show relation type picker
   - Select "involved" relation

4. **Position on Timeline**
   - Event appears on timeline at Year 1234, Day 100
   - Drag vertically to adjust lane if needed

---

### Creating a Character with Backstory

**Goal**: Create a detailed character with history.

1. **Create Entity**
   - **Entities → New Entity** (Ctrl+Shift+N)
   - Name: "Aria Shadowblade"
   - Type: Character
   - Tags: "protagonist", "rogue", "human"

2. **Write Backstory**
   ```
   Aria is a master thief from [[The Merchant Quarter]].
   She was trained by the [[Shadow Guild]] and is known
   for stealing the [[Crown of Stars]].
   
   Her parents died in [[The Great Fire]], which shaped
   her distrust of authority.
   ```

3. **Create Related Events**
   - Create event: "Theft of the Crown" (Year 1240)
   - Create event: "The Great Fire" (Year 1220)
   - Link both to Aria with "involved" relations

4. **Add Character Details**
   - In Attributes section, add custom fields:
     ```json
     {
       "age": "32",
       "appearance": "Dark hair, green eyes, scar on left cheek",
       "alignment": "Chaotic Good"
     }
     ```

---

### Linking Events with Causality

**Goal**: Show how one event caused another.

1. **Create First Event**
   - Name: "The Assassination of Duke Harren"
   - Date: Year 1235, Day 50

2. **Create Second Event**
   - Name: "The Civil War Begins"
   - Date: Year 1235, Day 75

3. **Create Causal Relation**
   - Method 1 (Drag-Drop):
     * Drag "Assassination" event
     * Drop on "Civil War" event editor
     * Hold **Shift** for type picker
     * Select **"caused"** relation
   
   - Method 2 (Relations Panel):
     * Select "Assassination" event
     * In Relations Panel, click **Add Relation**
     * Target: "Civil War"
     * Type: "caused"

4. **Verify in Graph**
   - Open Graph View (**Ctrl+G**)
   - See arrow: "Assassination" → "Civil War"

---

## Timeline Management

### Organizing Events by Category

**Goal**: Use group bands to organize timeline visually.

1. **Assign Event Types**
   - Edit each event
   - Set Type field:
     * "Political" for governance events
     * "War" for conflicts
     * "Cultural" for arts/religion
     * "Natural" for disasters

2. **Enable Group Bands**
   - Timeline → Settings
   - Enable "Group by Type"
   - Each type gets its own horizontal band

3. **Customize Band Colors**
   - Timeline → Band Settings
   - Assign colors to each type:
     * Political: Blue
     * War: Red
     * Cultural: Purple
     * Natural: Green

---

### Creating a Timeline Narrative

**Goal**: Generate a chronological narrative document.

1. **Filter Events**
   - In Project Explorer, filter:
     * Type: Events
     * Tags: "major" (to include only major events)
     * Date range: Year 1200-1300

2. **Open Longform Builder**
   - **Tools → Longform Builder**

3. **Configure Narrative**
   - **Template**: "Chronological Summary"
   - **Include**: Descriptions, Relations
   - **Format**: Markdown

4. **Generate and Export**
   - Click **Generate**
   - Review generated narrative
   - **Export** to file or clipboard

**Example Output:**
```markdown
# Timeline of the Kingdom Era (1200-1300)

## Year 1234 - The Fall of the Old Empire
The Old Empire fell after a devastating siege...

## Year 1235 - The Assassination of Duke Harren
Duke Harren was killed by unknown assassins...

## Year 1235 - The Civil War Begins
Following the assassination, the kingdom erupted into civil war...
```

---

### Working with Relative Dates

**Goal**: Position events relative to each other.

1. **Set Playhead**
   - Click on timeline at your reference point
   - Or enter date manually in playhead control

2. **Create Event with Relative Date**
   - New Event
   - Date field: "2 weeks later"
   - System calculates: Playhead date + 14 days

3. **Chain Multiple Events**
   - Event A: "Year 1234, Day 1"
   - Set playhead to Event A
   - Event B: "3 days later" → Day 4
   - Set playhead to Event B
   - Event C: "1 week later" → Day 11

---

## Building a World

### Establishing Core Locations

**Goal**: Create a geography foundation for your world.

1. **Create Main Locations**
   ```
   - "The Capital" (type: Location, tags: city, major)
   - "The Northern Wastes" (type: Location, tags: region, hostile)
   - "The Sacred Grove" (type: Location, tags: landmark, religious)
   ```

2. **Establish Spatial Relations**
   - "Capital" → "located_in" → "The Kingdom"
   - "Sacred Grove" → "located_in" → "The Kingdom"
   - "Northern Wastes" → "borders" → "The Kingdom"

3. **Add to Map**
   - Create map: "World Map"
   - Add markers for each location
   - Calibrate map scale

4. **Link to Events**
   - Create founding events:
     * "Founding of the Capital" (Year 1000)
     * "Discovery of the Sacred Grove" (Year 850)
   - Link locations to events with "depicted" or "involved"

---

### Creating a Faction Web

**Goal**: Model political organizations and relationships.

1. **Create Factions**
   ```
   - "The Royal Court" (type: Faction, tags: government)
   - "The Merchant Guild" (type: Faction, tags: commerce)
   - "The Shadow Guild" (type: Faction, tags: criminal, secret)
   - "The Temple of Light" (type: Faction, tags: religious)
   ```

2. **Establish Faction Relations**
   - Royal Court → "allied_with" → Temple of Light
   - Merchant Guild → "finances" → Royal Court
   - Shadow Guild → "opposes" → Royal Court
   - Shadow Guild → "infiltrated" → Merchant Guild

3. **Add Members**
   - Characters → "member_of" → Faction
   - Example: "Lord Harren" → "member_of" → "Royal Court"

4. **Track Faction Events**
   - Create events for each faction action
   - Link with "initiated_by" or "affected" relations

5. **Visualize in Graph**
   - Open Graph View
   - Filter by type: Faction
   - See faction network and relationships

---

### Building a Character Network

**Goal**: Create interconnected character relationships.

1. **Create Core Characters**
   - Protagonist, Antagonist, Supporting cast
   - Tag appropriately: "protagonist", "antagonist", "ally"

2. **Establish Relationships**
   - Family: "parent_of", "sibling_of", "child_of"
   - Social: "friend_of", "mentor_to", "rival_of"
   - Professional: "employed_by", "commands", "serves"

3. **Add Bidirectional Relations**
   - Enable "Bidirectional" when creating
   - Example: A "friend_of" B also creates B "friend_of" A

4. **Create Relationship Events**
   - "Meeting of Characters" (when they first met)
   - "Alliance Formed" (when they became allies)
   - "Betrayal" (when relationship changed)

---

## Advanced Relation Management

### Using Relation Attributes

**Goal**: Add temporal and conditional metadata to relations.

1. **Create Base Relation**
   - Character A → "allied_with" → Character B

2. **Add Attributes**
   - Right-click relation → Edit
   - Add attributes:
     ```json
     {
       "since": "Year 1234",
       "until": "Year 1240",
       "strength": "strong",
       "public": false,
       "reason": "Mutual enemy"
     }
     ```

3. **Use in Queries**
   - Filter relations by attribute
   - Search: Relations where `public = true`

---

### Modeling Temporal Relations

**Goal**: Track how relationships change over time.

1. **Create Multiple Relations for Same Pair**
   - Period 1: A → "allied_with" → B (attributes: {"since": "1234", "until": "1240"})
   - Period 2: A → "rival_of" → B (attributes: {"since": "1240", "until": "1250"})
   - Period 3: A → "neutral_to" → B (attributes: {"since": "1250"})

2. **Create Transition Events**
   - "The Betrayal" (Year 1240) - marks alliance ending
   - "The Reconciliation" (Year 1250) - marks rivalry ending

3. **Link Events to Relations**
   - Store event IDs in relation attributes
   - Or create "caused_by" meta-relations

---

## Map Workflows

### Creating a Regional Map

**Goal**: Set up a detailed map with locations.

1. **Prepare Map Image**
   - Create or find map image (PNG/JPG)
   - Recommended resolution: 2048x2048 or higher
   - Save to accessible location

2. **Import Map**
   - **Maps → New Map**
   - Upload image
   - Name: "Kingdom of Eldoria"

3. **Calibrate Scale**
   - **Tools → Calibrate Map**
   - Click two points of known distance
   - Enter distance: "500 miles"
   - Scale calculated automatically

4. **Add Location Markers**
   - For each location entity:
     * Right-click map → Add Marker
     * Link to entity
     * Customize icon and color
     * Position precisely

5. **Add Scale Bar**
   - **View → Show Scale Bar**
   - Position in corner

---

### Creating Multi-Map Hierarchies

**Goal**: Link maps at different zoom levels.

1. **Create World Map**
   - Upload full world map
   - Add major regions as markers

2. **Create Regional Maps**
   - Upload detailed map for each region
   - Name: "Region - Northern Kingdom"

3. **Link Maps**
   - On world map marker for "Northern Kingdom"
   - Add attribute: `{"detail_map": "Region - Northern Kingdom"}`

4. **Navigation**
   - Click world map marker
   - Use custom link to jump to regional map

---

## Search and Discovery

### Finding Related Content

**Goal**: Discover connections you forgot about.

1. **Select Entity/Event**
   - Click item in Project Explorer

2. **View Relations Panel**
   - See all direct connections

3. **Explore Second-Degree Connections**
   - Click a related item
   - See its relations
   - Discover indirect connections

4. **Use Graph View**
   - **Ctrl+G** to open graph
   - Set filter depth: 2 or 3
   - See network of connections

---

### Semantic Search Workflows

**Goal**: Find content using natural language.

1. **Build Search Index**
   - **Tools → AI Settings**
   - Configure Sentence Transformers or LM Studio
   - For LM Studio, enter the server URL and select a discovered embedding model
   - **Tools → Build Search Index**
   - Wait for indexing (one-time process)

2. **Search by Concept**
   - **Ctrl+K** for AI Panel
   - Query: "What magical artifacts exist?"
   - System finds entities with magic-related content

3. **Search by Theme**
   - Query: "Events related to betrayal"
   - System uses embeddings to find thematic matches
   - Not just keyword matching

4. **Refine Results**
   - Review top matches
   - Click to jump to item
   - Add more connections based on discoveries

---

### Using LLM Generation

**Goal**: Generate content with AI assistance.

1. **Select Context**
   - Select entity or event for context

2. **Configure LM Studio**
   - Open **Tools → AI Settings**
   - Enter the server URL, for example `http://localhost:1234`
   - Select **Refresh Models**
   - Choose a text-generation model; choose a separate embedding model if needed

3. **Open Generation Controls**
   - Expand **LLM Generation** in the entity or event editor

4. **Choose Prompt**
   - "Expand backstory" - for characters
   - "Generate description" - for locations
   - "Suggest relationships" - for entities

5. **Review and Edit**
   - AI generates text based on your world
   - Uses RAG to stay consistent with lore
   - Edit as needed
   - Choose **Replace**, **Append**, or **Discard** explicitly
   - Visible formatting and wiki links are preserved exactly

---

## Export and Sharing

### Exporting to Obsidian

**Goal**: Create an Obsidian vault from your world.

1. **Prepare Export**
   - Ensure all entities/events have good descriptions
   - Check wiki links are working

2. **Export**
   - **File → Export → Obsidian**
   - Choose destination folder

3. **Generated Structure**
   ```
   Obsidian_Export/
   ├── Events/
   │   ├── The Fall of the Empire.md
   │   └── The Great War.md
   ├── Entities/
   │   ├── Aria Shadowblade.md
   │   ├── The Capital.md
   │   └── The Royal Court.md
   └── _index.md
   ```

4. **Open in Obsidian**
   - Open folder as Obsidian vault
   - All wiki links work
   - Graph view shows connections

---

### Creating Shareable Summaries

**Goal**: Export a formatted document for sharing.

1. **Filter Content**
   - Select events/entities to include
   - Use tags to filter

2. **Generate Longform**
   - **Tools → Longform Builder**
   - Template: "Story Bible" or "World Summary"

3. **Export Format**
   - **Markdown**: For GitHub/Obsidian
   - **HTML**: For websites
   - **PDF**: For printing (requires external tool)

4. **Share**
   - Copy to blog
   - Share on Reddit/Discord
   - Email to collaborators

---

### Backup and Version Control

**Goal**: Safely version your world.

1. **Automatic Backups**
   - Enabled by default
   - Frequency: Every 15 minutes
   - Location: User data directory

2. **Manual Backup**
   - **File → Backup World**
   - Choose location
   - Timestamped `.kraken` file created

3. **Version Control with Git**
   - Navigate to world folder
   ```bash
   cd worlds/MyWorld
   git init
   git add .
   git commit -m "Initial commit"
   ```

4. **Restore from Backup**
   - **File → Restore World**
   - Select backup file
   - Confirm (current state backed up first)

---

## Optimization Tips

### Managing Large Worlds

**Goal**: Keep performance smooth with 10,000+ entities.

1. **Use Filtering**
   - Don't load everything at once
   - Filter by tags, types, date ranges

2. **Limit Graph Depth**
   - In Graph View, limit connection depth
   - Depth 2-3 is usually sufficient

3. **Archive Old Content**
   - Tag historical content as "archived"
   - Filter out by default
   - Include when needed

4. **Optimize Database**
   - **Tools → Database → Optimize**
   - Runs VACUUM and ANALYZE
   - Improves query performance

---

### Efficient Relation Management

**Goal**: Keep relations organized and useful.

1. **Use Consistent Types**
   - Standardize relation types
   - Document types in world notes
   - Examples: "caused", "influenced", "involved"

2. **Bidirectional Strategy**
   - Use bidirectional for symmetric relations
     * "allied_with", "rival_of", "friend_of"
   - Use unidirectional for asymmetric
     * "caused", "parent_of", "created"

3. **Prune Redundant Relations**
   - Review periodically
   - Remove unnecessary connections
   - Keep graph clean and meaningful

---

### Keyboard-First Workflows

**Goal**: Speed up common tasks with keyboard shortcuts.

**Quick Event Creation:**
```
1. Ctrl+Shift+E (new event)
2. Type name, Tab
3. Type date, Enter
4. Event created, editor open
```

**Fast Navigation:**
```
1. Ctrl+E (focus Project Explorer)
2. Type to search
3. Enter to open
4. Tab to switch panels
```

**Bulk Tagging:**
```
1. Select multiple items (Ctrl+Click)
2. Right-click → Add Tag
3. Type tag name
4. Applied to all selected
```

---

## Next Steps

### Continue Learning

- **[User Guide](USER_GUIDE.md)** - Reference for all features
- **[FAQ](FAQ.md)** - Common questions and troubleshooting
- **[Architecture](ARCHITECTURE.md)** - Technical details (for developers)

### Get Help

- **GitHub Issues**: Report bugs or request features
- **Discussions**: Share workflows and tips
- **Documentation**: Full docs at [docs/INDEX.md](INDEX.md)

---

**Navigation:**  
[← User Guide](USER_GUIDE.md) • [Back to Index](INDEX.md) • [FAQ →](FAQ.md)
