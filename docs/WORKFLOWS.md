# Workflows

This guide provides step-by-step workflows for common worldbuilding tasks in ProjektKraken. Each workflow includes practical examples and best practices.

## Table of Contents

1. [Building Your First World](#building-your-first-world)
2. [Timeline-First Worldbuilding](#timeline-first-worldbuilding)
3. [Character Biography](#character-biography)
4. [Faction Creation](#faction-creation)
5. [Location Hierarchy](#location-hierarchy)
6. [Event Chains](#event-chains)
7. [Map-Based Worldbuilding](#map-based-worldbuilding)
8. [Campaign Planning](#campaign-planning)
9. [Wiki Documentation](#wiki-documentation)
10. [Data Migration](#data-migration)

---

## Building Your First World

### Goal
Create a basic fantasy world with locations, characters, and a founding event.

### Step 1: Set Up Your Calendar

A custom calendar makes dates more immersive.

1. **Open Calendar Settings**
   - Click **Tools → Calendar Settings**
   
2. **Create Custom Calendar**
   - Click **New Calendar**
   - Name: "Eldorian Calendar"
   - Months: Enter month names and days
     ```
     Spring (30 days)
     Summer (30 days)
     Autumn (30 days)
     Winter (30 days)
     ```
   - Week: Enter day names
     ```
     Moonday, Tideday, Earthday, Fireday, Skyway, Starday, Sunday
     ```
   - Click **Save**

3. **Set as Active**
   - Select "Eldorian Calendar"
   - Click **Set Active**

**Result**: Date inputs now use your custom calendar (e.g., "1st of Spring, Year 1").

### Step 2: Create Core Locations

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
   - Click **Save** (`Ctrl+S`)

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

**Result**: Your world now has a geography foundation.

### Step 3: Create Characters

Populate your world with people.

1. **Create Main Character**
   - Click **Create → Entity** (`Ctrl+E`)
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

**Result**: Your world has key characters with relationships.

### Step 4: Create Founding Event

Establish your world's history.

1. **Create Historical Event**
   - Click **Create → Event** (`Ctrl+Shift+E`)
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
     - Add relation to Queen Lyanna (type: "ancestor_founded")

3. **Create Recent Event**
   - Name: "The Harvest Festival"
   - Date: "15th of Autumn, Year 245" (current time in your story)
   - Type: "celebration"
   - Description: Annual harvest celebration at Silverkeep
   - Link to: Queen Lyanna (type: "attended"), Silverkeep (type: "held_at")

**Result**: Your world has temporal context - past and present.

---

## Timeline-First Worldbuilding

### Goal
Create a rich history spanning centuries using a timeline-first approach.

### Quick Timeline Creation

1. **Start with Major Eras**
   Create events at key historical moments:
   ```
   Year 1     - "The Founding of Eldoria" (historical)
   Year 50    - "The Mage Wars Begin" (conflict)
   Year 75    - "Peace Treaty of Dawn" (political)
   Year 100   - "The Great Drought" (disaster)
   Year 150   - "Discovery of Iron Deposits" (discovery)
   Year 200   - "Golden Age Begins" (era)
   Year 245   - "Current Time" (present)
   ```

2. **Use Batch Event Creation**
   - Create events in chronological order
   - Use consistent tagging: "war", "peace", "disaster", "discovery"
   - Group related events with shared tags

3. **Add Duration for Long Events**
   - The Mage Wars: Start date Year 50 + 25 year duration
   - The Great Drought: 10 year duration
   - Shows as a bar on timeline

### Timeline Navigation

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

**Result**: A navigable historical timeline for your world.

---

## Character Biography

### Goal
Track a character's life events and relationships over time.

### Create Character with Life Events

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
   - Link all events to Aric with "involved" or "witnessed" relations

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

**Result**: Character has a documented life story on the timeline.

---

## Faction Creation

### Goal
Create an organization with hierarchy and agenda.

### Build a Faction

1. **Create Faction Entity**
   - Name: "The Order of the Silver Dawn"
   - Type: "faction"
   - Description: "Elite knights dedicated to protecting Eldoria"
   - Attributes:
     - Motto: "Light through Darkness"
     - Founded: Year 50
     - Members: ~200
     - Headquarters: "Fortress of Dawn"
   - Tags: "military", "knights", "major_faction"

2. **Create Member Characters**
   - Create 3-5 key member characters
   - Link each to faction with "member_of" relation
   - Add temporal scope:
     - Start date: When they joined
     - End date: When they left (if applicable)

3. **Create Founding Event**
   - Name: "Founding of the Silver Dawn"
   - Date: Year 50
   - Type: "historical"
   - Description: Founding story
   - Link to faction (type: "founded")

4. **Create Faction Location**
   - Name: "Fortress of Dawn"
   - Type: "location"
   - Link to faction (type: "headquarters_of")

5. **Document Major Actions**
   - Create events for faction's key activities:
     - "Defense of the Northern Border" (Year 75)
     - "The Silver Dawn Tournament" (Year 100)
     - "Alliance with the Mage Guild" (Year 150)
   - Link events to faction with "involved" relations

**Result**: A fully documented faction with members, history, and location.

---

## Location Hierarchy

### Goal
Create a geographic hierarchy from continents to buildings.

### Build Location Tree

1. **Create Top-Level Location**
   - Name: "The Continent of Aetheria"
   - Type: "location"
   - Tags: "continent", "geography"

2. **Create Regions**
   - "The Western Valleys" (region)
   - "The Northern Mountains" (region)
   - "The Eastern Coastlands" (region)
   - Link each to continent with "located_in"

3. **Create Kingdoms/Nations**
   - "The Kingdom of Eldoria" (nation)
   - Link to "The Western Valleys" with "located_in"

4. **Create Cities**
   - "Silverkeep" (city, capital)
   - "Port Haven" (city, port)
   - Link each to kingdom with "located_in"

5. **Create Districts/Buildings**
   - "The Royal Palace" (building)
   - "The Market Quarter" (district)
   - Link to city with "located_in"

### Use the Graph View

1. **Open Graph View**
   - View → Graph View

2. **Select Top Location**
   - Click "The Continent of Aetheria"

3. **Adjust Filter**
   - Filter → Relation Types → Show only "located_in"
   - Depth → 5 levels

**Result**: A visual tree of your world's geography.

---

## Event Chains

### Goal
Create causal chains of events that show cause and effect.

### Build Historical Causality

1. **Create Initial Event**
   - Name: "Discovery of the Ancient Artifact"
   - Date: Year 100
   - Type: "discovery"
   - Description: Adventurers find mysterious artifact

2. **Create Caused Event**
   - Name: "The Artifact's Dark Power Awakens"
   - Date: Year 101 (shortly after)
   - Type: "supernatural"
   - Link to previous event with "caused" relation

3. **Create Cascade**
   - "The King Falls Under the Artifact's Curse" (Year 101)
   - "The Kingdom Descends into Chaos" (Year 102)
   - "The Heroes Quest to Destroy the Artifact" (Year 103)
   - "The Final Battle at the Dark Tower" (Year 104)
   - Link each event to the previous with "caused"

4. **View Causal Chain**
   - Select first event
   - Graph view shows chain
   - Timeline shows sequence

**Result**: A clear narrative arc with cause and effect documented.

---

## Map-Based Worldbuilding

### Goal
Use maps to build your world spatially first.

### Create World from Map

1. **Import World Map**
   - Tools → Create Map
   - Name: "Map of Aetheria"
   - Select image file
   - Click Create

2. **Calibrate Map**
   - Click **Calibrate** button
   - Draw line between two known points
   - Enter distance: "1000 miles"
   - Apply

3. **Place Major Locations**
   - Right-click on map → Add Marker
   - Select existing location or create new
   - Place markers for:
     - Silverkeep (capital)
     - Port Haven (port city)
     - Darkwood Forest
     - Temple of the Dawn

4. **Create Journey Events**
   - Name: "The Royal Procession to Port Haven"
   - Date: Year 240
   - Link to: Queen Lyanna, Silverkeep, Port Haven
   - Create trajectory:
     - Start position: Silverkeep
     - End position: Port Haven
     - Duration: 5 days

5. **Use Clock Mode**
   - Enable Clock Mode in map toolbar
   - Drag timeline playhead
   - Watch markers move along trajectories

**Result**: A spatial-temporal world where locations and movements are mapped.

---

## Campaign Planning

### Goal
Plan a tabletop RPG campaign with sessions and plot arcs.

### Set Up Campaign

1. **Create Campaign Entity**
   - Name: "The Shadow Rising Campaign"
   - Type: "concept"
   - Tags: "campaign", "active"

2. **Create Player Characters**
   - Create 4-5 character entities
   - Type: "character"
   - Tags: "pc", "player_character"
   - Add attributes: player_name, class, level, etc.

3. **Create Session Events**
   - Name: "Session 1: The Mysterious Summons"
   - Date: Real date or in-world date
   - Type: "session"
   - Description: Session recap
   - Link to: PCs involved, locations visited, NPCs met

4. **Create Plot Arc Events**
   - "Arc 1 Begins: The Cult Discovered"
   - "Arc 1 Midpoint: The Betrayal"
   - "Arc 1 Climax: Battle at the Temple"
   - "Arc 1 Conclusion: The Artifact Secured"
   - Link events with "caused" to show progression

5. **Track NPC Relations**
   - Create NPCs as entities
   - Add relations to PCs: "ally_of", "enemy_of", "mentor_of"
   - Use temporal relations for changing relationships

**Result**: A documented campaign with sessions, arcs, and character development tracked.

---

## Wiki Documentation

### Goal
Create a comprehensive wiki-style documentation system.

### Build Wiki Structure

1. **Create Index Entity**
   - Name: "World Encyclopedia"
   - Type: "concept"
   - Description: Central index page
   - Use wiki links to categorize:
     ```
     # Major Topics
     - [[Geography of Aetheria]]
     - [[History of Eldoria]]
     - [[Notable Figures]]
     - [[Magic System]]
     - [[Religions and Beliefs]]
     ```

2. **Create Category Pages**
   - Create entity for each major topic
   - Use wiki links to sub-topics
   - Example: "Geography of Aetheria":
     ```
     # Continents
     - [[The Continent of Aetheria]]
     
     # Regions
     - [[The Western Valleys]]
     - [[The Northern Mountains]]
     - [[The Eastern Coastlands]]
     
     # Major Cities
     - [[Silverkeep]]
     - [[Port Haven]]
     ```

3. **Cross-Reference Everything**
   - Use wiki links liberally in descriptions
   - Create backlink trails
   - Build web of connections

4. **Use Longform for Deep Dives**
   - Create longform document: "The Complete History of Eldoria"
   - Outline:
     - Chapter 1: The Founding Era
     - Chapter 2: The Mage Wars
     - Chapter 3: The Golden Age
   - Write narrative content with wiki links

**Result**: A navigable wiki with structured content and cross-references.

---

## Data Migration

### Goal
Import data from external sources or migrate between worlds.

### Import from JSON

1. **Prepare JSON File**
   - Format data as JSON with entities, events, relations
   - Example structure:
     ```json
     {
       "entities": [
         {"id": "uuid", "name": "Character", "type": "character", ...}
       ],
       "events": [
         {"id": "uuid", "name": "Event", "lore_date": 100.0, ...}
       ],
       "relations": [
         {"source_id": "uuid1", "target_id": "uuid2", "rel_type": "caused"}
       ]
     }
     ```

2. **Import Data**
   - File → Import → From JSON
   - Select JSON file
   - Choose mode: Merge (add to existing)
   - Click Import

3. **Review Imported Data**
   - Check entity list for new entities
   - Check event list for new events
   - Verify relations in graph view

### Export to Obsidian

1. **Prepare Export**
   - File → Export → To Obsidian
   - Select Obsidian vault path

2. **Configure Options**
   - Include attachments: ✓
   - Convert wiki links: ✓
   - Folder structure: By type

3. **Export**
   - Click Export
   - Review generated markdown files in Obsidian

**Result**: Data successfully migrated or exported for use in other tools.

---

## Tips for Effective Workflows

### General Best Practices

1. **Start Small**: Begin with 3-5 core entities and events
2. **Build Connections**: Add relations as you go
3. **Use Tags Consistently**: Develop a tagging system early
4. **Document Incrementally**: Add details over time
5. **Review the Graph**: Use graph view to find gaps

### Timeline Workflow Tips

1. **Work Chronologically**: Create events in order
2. **Mark Present**: Set playhead to "current time" in your story
3. **Use Durations**: Add duration to long events for visual clarity
4. **Filter Aggressively**: Focus on relevant time periods

### Character Workflow Tips

1. **Biography First**: Create character before their events
2. **Link Early Events**: Birth, childhood, coming of age
3. **Track Relationships**: Use temporal relations for changing relationships
4. **Add Images**: Portraits help visualize characters

### Location Workflow Tips

1. **Hierarchy**: Build from large (continents) to small (buildings)
2. **Maps Early**: Add maps as soon as possible
3. **Calibrate**: Set scale for distance calculations
4. **Markers**: Place entities on maps

---

**Need More Help?** See the [User Guide](USER_GUIDE.md) for detailed feature documentation.
