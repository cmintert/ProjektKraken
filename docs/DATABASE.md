# Database Documentation

**Version:** 0.11.0 (Beta)  
**Last Updated:** February 2026

Complete database schema and data model documentation for ProjektKraken.

---

## Table of Contents

1. [Overview](#overview)
2. [Database Configuration](#database-configuration)
3. [Core Tables](#core-tables)
4. [Supporting Tables](#supporting-tables)
5. [JSON Attributes](#json-attributes)
6. [Relationships and Foreign Keys](#relationships-and-foreign-keys)
7. [Indexes](#indexes)
8. [Migrations](#migrations)

---

## Overview

### Database Technology

- **Engine**: SQLite 3.35+
- **File Format**: Single `.kraken` file per world
- **Journal Mode**: WAL (Write-Ahead Logging)
- **Foreign Keys**: Enabled

### Design Philosophy

**Hybrid Schema Approach:**

- **Strict SQL Columns**: Searchable, sortable, indexed fields
- **JSON Attributes**: Flexible, world-specific custom properties

This combines the reliability of structured data with the flexibility of document storage.

---

## Database Configuration

### Initialization

```sql
-- Enable WAL mode for concurrency
PRAGMA journal_mode = WAL;

-- Enforce foreign key constraints
PRAGMA foreign_keys = ON;

-- Performance optimizations
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 268435456;  -- 256MB memory-mapped I/O
```

### WAL Mode Benefits

**Write-Ahead Logging** enables:

1. **Concurrent Reads**: Multiple readers don't block each other
2. **Non-Blocking Reads**: Readers don't block writers
3. **Better Performance**: Reduced disk I/O for commits
4. **Atomic Commits**: Multiple changes in single transaction

**Usage Pattern:**

```python
# Worker thread has write access
# Main thread has read-only connections
# WAL ensures isolation between threads
```

---

## Core Tables

### Events Table

Stores timeline events.

```sql
CREATE TABLE events (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT,
    lore_date REAL NOT NULL,
    lore_duration REAL DEFAULT 0.0,
    description TEXT,
    attributes TEXT DEFAULT '{}',
    created_at REAL,
    modified_at REAL
);

CREATE INDEX idx_events_date ON events(lore_date);
```

**Columns:**

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | UUID primary key |
| `name` | TEXT | Event title (required) |
| `type` | TEXT | Event category (e.g., "battle", "political") |
| `lore_date` | REAL | Timeline date (float: 1.0 = 1 day) |
| `lore_duration` | REAL | Event duration in days |
| `description` | TEXT | Rich text description with wiki links |
| `attributes` | TEXT | JSON for custom properties |
| `created_at` | REAL | Unix timestamp of creation |
| `modified_at` | REAL | Unix timestamp of last modification |

**Example Data:**

```json
{
  "id": "evt_123",
  "name": "The Fall of Atlantis",
  "type": "disaster",
  "lore_date": 450123.5,
  "description": "The [[City of Atlantis]] sank beneath the waves.",
  "attributes": {
    "severity": "catastrophic",
    "casualties": 10000,
    "custom_field": "custom_value"
  }
}
```

---

### Entities Table

Stores persistent world elements.

```sql
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT,
    description TEXT,
    attributes TEXT DEFAULT '{}',
    created_at REAL,
    modified_at REAL
);
```

**Columns:**

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | UUID primary key |
| `name` | TEXT | Entity name (required) |
| `type` | TEXT | Entity type (character, location, faction, item, concept) |
| `description` | TEXT | Rich text description with wiki links |
| `attributes` | TEXT | JSON for custom properties |
| `created_at` | REAL | Creation timestamp |
| `modified_at` | REAL | Last modification timestamp |

**Entity Types:**

- **character**: People, sentient beings
- **location**: Places, regions
- **faction**: Groups, organizations
- **item**: Objects, artifacts
- **concept**: Abstract ideas

**Example Data:**

```json
{
  "id": "ent_456",
  "name": "Gandalf the Grey",
  "type": "character",
  "description": "A powerful [[Wizard]] from [[Middle Earth]].",
  "attributes": {
    "race": "Maia",
    "alignment": "Good",
    "skills": ["Magic", "Wisdom", "Swordsmanship"]
  }
}
```

---

### Relations Table

Stores directed relationships between entities and events.

```sql
CREATE TABLE relations (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    rel_type TEXT NOT NULL,
    attributes TEXT DEFAULT '{}',
    created_at REAL,
    FOREIGN KEY (source_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES entities(id) ON DELETE CASCADE
);

CREATE INDEX idx_relations_source ON relations(source_id);
CREATE INDEX idx_relations_target ON relations(target_id);
```

**Columns:**

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | UUID primary key |
| `source_id` | TEXT | Source entity/event ID |
| `target_id` | TEXT | Target entity/event ID |
| `rel_type` | TEXT | Relationship type |
| `attributes` | TEXT | JSON metadata for relation |
| `created_at` | REAL | Creation timestamp |

**Common Relation Types:**

| Type | Description | Example |
|------|-------------|---------|
| `caused` | Causal relationship | Event A caused Event B |
| `involved` | Participation | Event involved Entity |
| `influenced` | Indirect effect | A influenced B |
| `located_at` | Spatial | Entity at Location |
| `member_of` | Membership | Character in Faction |
| `owns` | Ownership | Character owns Item |
| `parent_of` | Family | Parent of Child |

**Example Data:**

```json
{
  "id": "rel_789",
  "source_id": "evt_fall_of_empire",
  "target_id": "evt_civil_war",
  "rel_type": "caused",
  "attributes": {
    "certainty": "confirmed",
    "time_lag": 30.0
  }
}
```

---

## Supporting Tables

### Maps Table

Geographic maps with images.

```sql
CREATE TABLE maps (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    image_path TEXT,
    scale_pixels_per_km REAL,
    attributes TEXT DEFAULT '{}',
    created_at REAL,
    modified_at REAL
);
```

**Purpose**: Store map metadata and calibration.

---

### Markers Table

Points on maps.

```sql
CREATE TABLE markers (
    id TEXT PRIMARY KEY,
    map_id TEXT NOT NULL,
    entity_id TEXT,
    name TEXT,
    x REAL NOT NULL,
    y REAL NOT NULL,
    icon TEXT,
    color TEXT,
    attributes TEXT DEFAULT '{}',
    FOREIGN KEY (map_id) REFERENCES maps(id) ON DELETE CASCADE,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE SET NULL
);

CREATE INDEX idx_markers_map ON markers(map_id);
```

**Purpose**: Link entities to geographic locations on maps.

---

### Moving Features Table

Temporal trajectories on maps.

```sql
CREATE TABLE moving_features (
    id TEXT PRIMARY KEY,
    marker_id TEXT NOT NULL,
    name TEXT,
    keyframes TEXT,  -- JSON: [[time, x, y], ...]
    attributes TEXT DEFAULT '{}',
    FOREIGN KEY (marker_id) REFERENCES markers(id) ON DELETE CASCADE
);
```

**Purpose**: Track how markers move over time (4D mapping).

**Keyframe Format:**

```json
{
  "keyframes": [
    [0.0, 100.0, 200.0],     // At time 0, position (100, 200)
    [1000.0, 150.0, 250.0],  // At time 1000, position (150, 250)
    [2000.0, 200.0, 300.0]   // At time 2000, position (200, 300)
  ]
}
```

---

### Tags Tables

Normalized tag system.

```sql
CREATE TABLE tags (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    color TEXT DEFAULT '#888888',
    created_at REAL
);

CREATE TABLE event_tags (
    event_id TEXT NOT NULL,
    tag_id TEXT NOT NULL,
    PRIMARY KEY (event_id, tag_id),
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE TABLE entity_tags (
    entity_id TEXT NOT NULL,
    tag_id TEXT NOT NULL,
    PRIMARY KEY (entity_id, tag_id),
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);
```

**Purpose**: Many-to-many tagging with consistent tag definitions.

---

### Calendar Config Table

Custom calendar configurations.

```sql
CREATE TABLE calendar_config (
    id INTEGER PRIMARY KEY,
    config_json TEXT NOT NULL
);
```

**Purpose**: Store custom fantasy calendar definitions.

**Config Structure:**

```json
{
  "months": [
    {"name": "Coldmoon", "days": 30},
    {"name": "Springrise", "days": 28}
  ],
  "week_days": ["Moonday", "Starday", "Fireday"],
  "leap_years": {"interval": 5, "extra_day_month": 1}
}
```

---

### Image Attachments Table

Image links to entities/events.

```sql
CREATE TABLE image_attachments (
    id TEXT PRIMARY KEY,
    owner_type TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    thumbnail_path TEXT,
    created_at REAL
);

CREATE INDEX idx_attachments_owner ON image_attachments(owner_type, owner_id);
```

**Purpose**: Link images to any entity or event.

---

### Embeddings Table

Semantic search vectors.

```sql
CREATE TABLE embeddings (
    object_id TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    vector_dim INTEGER NOT NULL,
    vector_data BLOB NOT NULL,
    text_hash TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (object_id, embedding_model)
);

CREATE INDEX idx_embeddings_object ON embeddings(object_id);
CREATE INDEX idx_embeddings_model ON embeddings(embedding_model);
CREATE INDEX idx_embeddings_created_at ON embeddings(created_at);
```

**Purpose**: Store AI embedding vectors for semantic search.

---

### Command History Tables

Persistent undo/redo.

```sql
CREATE TABLE command_history (
    id TEXT PRIMARY KEY,
    world_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    command_type TEXT NOT NULL,
    command_data TEXT NOT NULL,
    is_aggregate INTEGER DEFAULT 0,
    created_at REAL NOT NULL
);

CREATE INDEX idx_ch_world_time ON command_history(world_id, created_at);
CREATE INDEX idx_ch_session ON command_history(session_id);
CREATE INDEX idx_ch_aggregate ON command_history(is_aggregate);

CREATE TABLE edit_sessions (
    id TEXT PRIMARY KEY,
    world_id TEXT NOT NULL,
    started_at REAL NOT NULL,
    ended_at REAL,
    app_version TEXT
);
```

**Purpose**: Persist command history across app restarts.

---

## JSON Attributes

All core tables use `attributes TEXT DEFAULT '{}'` for flexible custom properties.

### Why JSON Attributes?

1. **Flexibility**: World-specific properties without schema migrations
2. **Extension**: Users can add custom fields
3. **Backward Compatibility**: Old code ignores unknown fields

### Common Attribute Patterns

**Events:**

```json
{
  "severity": "high",
  "participants": ["ent_1", "ent_2"],
  "weather": "stormy",
  "custom_notes": "Additional context"
}
```

**Entities:**

```json
{
  "age": 32,
  "appearance": "Dark hair, green eyes",
  "skills": ["Magic", "Swordsmanship"],
  "inventory": ["item_1", "item_2"]
}
```

**Relations:**

```json
{
  "since": "Year 1234",
  "until": "Year 1240",
  "strength": "strong",
  "public": false
}
```

### Accessing Attributes

**In Python:**

```python
event = Event.from_dict(row)
severity = event.attributes.get("severity", "unknown")

entity.attributes["age"] = 33
repo.update(entity)
```

**In SQL (JSON functions):**

```sql
-- Filter by attribute
SELECT * FROM events 
WHERE json_extract(attributes, '$.severity') = 'high';

-- Update attribute
UPDATE events
SET attributes = json_set(attributes, '$.severity', 'critical')
WHERE id = 'evt_123';
```

---

## Relationships and Foreign Keys

### Foreign Key Cascade Rules

**ON DELETE CASCADE:**

- Deleting a map deletes all its markers
- Deleting an entity deletes all its tags
- Deleting an event deletes all its tags
- Deleting a marker deletes its moving features

**ON DELETE SET NULL:**

- Deleting an entity sets `entity_id` to NULL in markers (orphaned markers remain)

### Relationship Diagram

```
entities ←──────┐
    ↑           │
    │           │
    │      relations (many-to-many)
    │           │
    ↓           │
events ─────────┘

entities ←── entity_tags ──→ tags
events ←──── event_tags ───→ tags

maps ←─── markers ←─── moving_features
           ↓
        entities (optional link)
```

---

## Indexes

### Purpose of Each Index

| Index | Table | Purpose |
|-------|-------|---------|
| `idx_events_date` | events | Fast temporal queries |
| `idx_relations_source` | relations | Fast source → targets lookup |
| `idx_relations_target` | relations | Fast target → sources lookup |
| `idx_markers_map` | markers | List markers for a map |
| `idx_attachments_owner` | image_attachments | Find images for entity/event |
| `idx_embeddings_*` | embeddings | Fast vector search |
| `idx_ch_*` | command_history | Session and time-based queries |

### Query Optimization

**Good Query (uses index):**

```sql
SELECT * FROM events WHERE lore_date > 1000.0 ORDER BY lore_date;
-- Uses idx_events_date
```

**Bad Query (full table scan):**

```sql
SELECT * FROM events WHERE name LIKE '%battle%';
-- No index on name, full scan required
```

---

## Migrations

### Schema Versioning

Currently, ProjektKraken uses **schema initialization** rather than migrations:

1. On first run, full schema created
2. If schema exists, it's used as-is
3. No automated migrations between versions

### Future Migration Strategy

For schema changes in future versions:

1. **Add Schema Version Table**

   ```sql
   CREATE TABLE schema_version (
       version INTEGER PRIMARY KEY,
       applied_at REAL
   );
   ```

2. **Migration Scripts**

   ```python
   def migrate_v1_to_v2(db: DatabaseService):
       db.execute("ALTER TABLE events ADD COLUMN new_field TEXT")
       db.execute("INSERT INTO schema_version VALUES (2, ?)", (time.time(),))
   ```

3. **Apply Migrations on Startup**

   ```python
   current_version = get_schema_version(db)
   if current_version < 2:
       migrate_v1_to_v2(db)
   ```

### Backward Compatibility

**Best Practices:**

- **Additive Changes**: Add new tables/columns, don't remove
- **Optional Fields**: New columns should be nullable or have defaults
- **Preserve Data**: Never destructive migrations without user consent

---

## Next Steps

- **[API Reference](API_REFERENCE.md)** - Learn about data access APIs
- **[Development Guide](DEVELOPMENT.md)** - Contribute to the project
- **[Testing Guide](TESTING.md)** - Test database code

---

**Navigation:**  
[← Development](DEVELOPMENT.md) • [Back to Index](INDEX.md) • [API Reference →](API_REFERENCE.md)
