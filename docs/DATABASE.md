# Database Schema Reference

This document describes ProjektKraken's database schema, data model, and access patterns.

## Table of Contents

1. [Overview](#overview)
2. [Schema Design](#schema-design)
3. [Tables](#tables)
4. [Hybrid Schema Approach](#hybrid-schema-approach)
5. [Repositories](#repositories)
6. [Performance Optimizations](#performance-optimizations)
7. [Migration Strategy](#migration-strategy)
8. [Best Practices](#best-practices)

---

## Overview

ProjektKraken uses **SQLite** as its embedded database, stored in a single `.kraken` file.

### Key Characteristics

- **Single-file database:** Portable, easy to backup
- **WAL mode:** Write-Ahead Logging for concurrent reads
- **JSON columns:** Flexible attributes alongside strict schema
- **Time representation:** Float values (1.0 = 1 day)
- **Repository pattern:** Abstracted CRUD operations

### Database Location

- **User data:** `~/.local/share/ProjektKraken/worlds/MyWorld.kraken`
- **Test data:** `:memory:` (in-memory database for tests)

---

## Schema Design

### Hybrid Schema Philosophy

ProjektKraken uses a **Hybrid Schema** approach:

1. **Strict SQL columns** for searchable/sortable data (IDs, names, dates)
2. **JSON attributes** for flexible, world-specific data

This provides:
- ✅ Fast queries on core fields (SQL indexes)
- ✅ Flexibility for custom attributes (no schema migrations for new fields)
- ✅ Type safety for critical data
- ✅ Extensibility for user-defined properties

### Example: Events Table

```sql
CREATE TABLE events (
    id TEXT PRIMARY KEY,           -- Searchable
    name TEXT NOT NULL,            -- Searchable
    lore_date REAL NOT NULL,       -- Indexed for sorting
    lore_duration REAL DEFAULT 0.0,
    type TEXT NOT NULL,
    description TEXT,
    attributes JSON DEFAULT '{}',  -- Flexible attributes
    created_at REAL,
    modified_at REAL
);
```

A flexible attribute example in JSON:

```json
{
  "_tags": ["battle", "war"],
  "casualties": 5000,
  "weather": "stormy",
  "custom_field": "any value"
}
```

---

## Tables

### System Tables

#### `system_meta`

Stores system-level metadata and settings.

```sql
CREATE TABLE system_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
```

**Common keys:**
- `schema_version` - Database schema version
- `app_version` - Application version that created the database
- `world_name` - Name of the world/project

---

### Core Data Tables

#### `events`

Represents points or spans in time.

```sql
CREATE TABLE events (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    lore_date REAL NOT NULL,
    lore_duration REAL DEFAULT 0.0,
    description TEXT,
    attributes JSON DEFAULT '{}',
    created_at REAL,
    modified_at REAL
);

CREATE INDEX idx_events_date ON events(lore_date);
```

**Columns:**
- `id` - UUID primary key
- `type` - Event category (generic, battle, founding, etc.)
- `name` - Display name
- `lore_date` - Timeline position (1.0 = 1 day)
- `lore_duration` - Event span (0.0 for instant events)
- `description` - Rich text description
- `attributes` - JSON object for custom fields
- `created_at` - Unix timestamp of creation
- `modified_at` - Unix timestamp of last modification

**Attributes JSON:**
- `_tags` - Array of tag strings
- User-defined fields (any JSON-serializable data)

**Example row:**

```python
{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "type": "battle",
    "name": "Battle of Five Armies",
    "lore_date": 2941.0,  # Year 2941
    "lore_duration": 0.1,  # ~2.4 hours
    "description": "The climactic battle in the north...",
    "attributes": {
        "_tags": ["battle", "war"],
        "casualties": 5000,
        "victor": "Free Peoples"
    },
    "created_at": 1699564800.0,
    "modified_at": 1699564800.0
}
```

---

#### `entities`

Represents people, places, organizations, and artifacts.

```sql
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    attributes JSON DEFAULT '{}',
    created_at REAL,
    modified_at REAL
);
```

**Columns:**
- `id` - UUID primary key
- `type` - Entity category (person, place, organization, artifact, etc.)
- `name` - Display name
- `description` - Rich text description
- `attributes` - JSON object for custom fields
- `created_at` - Unix timestamp
- `modified_at` - Unix timestamp

**Common attribute keys:**
- `_tags` - Array of tag strings
- `birth_date` - (for persons) Lore date of birth
- `death_date` - (for persons) Lore date of death
- `location` - (for places) Coordinates or parent location
- `aliases` - Array of alternate names

**Example row:**

```python
{
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "type": "person",
    "name": "Gandalf",
    "description": "Istari wizard sent to Middle-earth...",
    "attributes": {
        "_tags": ["wizard", "istari"],
        "aliases": ["Mithrandir", "The Grey"],
        "race": "Maiar",
        "arrival_date": 1000.0
    },
    "created_at": 1699564800.0,
    "modified_at": 1699564800.0
}
```

---

#### `relations`

Generic relationship table linking events and entities.

```sql
CREATE TABLE relations (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    rel_type TEXT NOT NULL,
    attributes JSON DEFAULT '{}',
    created_at REAL
);

CREATE INDEX idx_relations_source ON relations(source_id);
CREATE INDEX idx_relations_target ON relations(target_id);
```

**Columns:**
- `id` - UUID primary key
- `source_id` - UUID of source object (event or entity)
- `target_id` - UUID of target object (event or entity)
- `rel_type` - Relationship type (caused_by, located_in, participated_in, etc.)
- `attributes` - JSON object for relation metadata
- `created_at` - Unix timestamp

**Common relation types:**
- `caused_by` - Event caused by event/entity
- `located_in` - Entity/event located in place
- `participated_in` - Entity participated in event
- `allied_with` - Entity allied with entity
- `parent_child` - Entity parent/child relationship

**Example row:**

```python
{
    "id": "789e0123-e45b-67d8-a901-234567890abc",
    "source_id": "event-id",  # Battle of Five Armies
    "target_id": "entity-id",  # Gandalf
    "rel_type": "participated_in",
    "attributes": {
        "role": "commander",
        "side": "Free Peoples"
    },
    "created_at": 1699564800.0
}
```

---

#### `calendar_config`

Stores custom calendar configurations.

```sql
CREATE TABLE calendar_config (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    config_json TEXT NOT NULL,
    is_active INTEGER DEFAULT 0,
    created_at REAL,
    modified_at REAL
);
```

**Columns:**
- `id` - UUID primary key
- `name` - Calendar name (e.g., "Gregorian", "Middle Earth Reckoning")
- `config_json` - JSON serialized CalendarConfig
- `is_active` - 1 if currently active, 0 otherwise (only one active at a time)
- `created_at` - Unix timestamp
- `modified_at` - Unix timestamp

**Config JSON structure:**

```json
{
    "name": "Gregorian",
    "epoch_name": "Year 1",
    "epoch_offset": 0.0,
    "day_zero": 0.0,
    "ticks_per_day": 86400,
    "months": [
        {"name": "January", "days": 31},
        {"name": "February", "days": 28},
        ...
    ],
    "week_days": ["Monday", "Tuesday", ...],
    "leap_year_rule": "gregorian"
}
```

---

### Map and Spatial Tables

#### `maps`

Geographic or conceptual maps.

```sql
CREATE TABLE maps (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    image_path TEXT NOT NULL,
    description TEXT,
    attributes JSON DEFAULT '{}',
    created_at REAL,
    modified_at REAL
);
```

**Columns:**
- `id` - UUID primary key
- `name` - Map name
- `image_path` - Path to map image file (relative or absolute)
- `description` - Map description
- `attributes` - JSON for scale, projection, etc.
- `created_at` - Unix timestamp
- `modified_at` - Unix timestamp

---

#### `markers`

Points of interest on maps.

```sql
CREATE TABLE markers (
    id TEXT PRIMARY KEY,
    map_id TEXT NOT NULL,
    object_id TEXT NOT NULL,
    object_type TEXT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    label TEXT,
    attributes JSON DEFAULT '{}',
    created_at REAL,
    modified_at REAL,
    UNIQUE(map_id, object_id, object_type),
    FOREIGN KEY(map_id) REFERENCES maps(id) ON DELETE CASCADE
);

CREATE INDEX idx_markers_map ON markers(map_id);
CREATE INDEX idx_markers_object ON markers(object_id, object_type);
```

**Columns:**
- `id` - UUID primary key
- `map_id` - Reference to maps table
- `object_id` - UUID of linked event/entity
- `object_type` - "event" or "entity"
- `x` - X coordinate (0.0-1.0, normalized)
- `y` - Y coordinate (0.0-1.0, normalized)
- `label` - Optional label text
- `attributes` - JSON for marker styling
- `created_at` - Unix timestamp
- `modified_at` - Unix timestamp

**Unique constraint:** One marker per object per map

**Cascade delete:** Markers deleted when map is deleted

---

#### `moving_features`

Temporal trajectories for animated markers.

```sql
CREATE TABLE moving_features (
    id TEXT PRIMARY KEY,
    marker_id TEXT NOT NULL,
    t_start REAL NOT NULL,
    t_end REAL NOT NULL,
    trajectory JSON NOT NULL,
    properties JSON DEFAULT '{}',
    created_at REAL,
    FOREIGN KEY(marker_id) REFERENCES markers(id) ON DELETE CASCADE
);

CREATE INDEX idx_moving_features_marker ON moving_features(marker_id);
CREATE INDEX idx_moving_features_time ON moving_features(t_start, t_end);
```

**Columns:**
- `id` - UUID primary key
- `marker_id` - Reference to markers table
- `t_start` - Start time (lore_date)
- `t_end` - End time (lore_date)
- `trajectory` - JSON array of [time, x, y] keyframes
- `properties` - JSON for animated properties (color, size, etc.)
- `created_at` - Unix timestamp

**Trajectory JSON structure:**

```json
[
    [2941.0, 0.1, 0.2],  // [time, x, y]
    [2941.5, 0.15, 0.25],
    [2942.0, 0.2, 0.3]
]
```

---

## Hybrid Schema Approach

### When to Use SQL Columns vs JSON Attributes

| Use SQL Column | Use JSON Attribute |
|----------------|-------------------|
| Always queried or sorted | Rarely queried |
| Core to data model | User-defined or optional |
| Fixed schema | Variable schema |
| Needs indexing | No indexing needed |
| Cross-world consistency | World-specific |

### Examples

**SQL Column:**
- Event `lore_date` - Always queried for timeline display
- Entity `name` - Always displayed, searched, sorted
- Relation `rel_type` - Filtered and grouped

**JSON Attribute:**
- Event `weather` - World-specific, not always present
- Entity `magic_affinity` - Custom field for fantasy worlds
- Relation `role` - Context-specific metadata

### Querying JSON in SQLite

SQLite supports JSON functions for queries:

```sql
-- Get events with a specific tag
SELECT * FROM events
WHERE JSON_EXTRACT(attributes, '$._tags') LIKE '%battle%';

-- Get entities by custom attribute
SELECT * FROM entities
WHERE JSON_EXTRACT(attributes, '$.race') = 'Elf';

-- Update JSON attribute
UPDATE events
SET attributes = JSON_SET(attributes, '$.status', 'resolved')
WHERE id = '...';
```

---

## Repositories

ProjektKraken uses the **Repository Pattern** to abstract database operations.

### Repository Structure

```
src/services/repositories/
├── base_repository.py          # Abstract base class
├── event_repository.py         # Event CRUD
├── entity_repository.py        # Entity CRUD
├── relation_repository.py      # Relation CRUD
├── calendar_repository.py      # Calendar CRUD
├── map_repository.py           # Map CRUD
└── trajectory_repository.py    # Moving features CRUD
```

### Using Repositories

```python
from src.services.db_service import DatabaseService

# Initialize database service
db_service = DatabaseService("myworld.kraken")
db_service.connect()

# Access repositories
event_repo = db_service.event_repo
entity_repo = db_service.entity_repo
relation_repo = db_service.relation_repo

# CRUD operations
from src.core.events import Event

# Create
event = Event(name="New Event", lore_date=100.0)
event_repo.insert(event)

# Read
event = event_repo.get_by_id("event-id")
all_events = event_repo.get_all()
sorted_events = event_repo.get_sorted_by_date()

# Update
event.name = "Updated Name"
event_repo.update(event)

# Delete
event_repo.delete("event-id")
```

### Repository Methods

#### Common Methods (All Repositories)

```python
insert(obj: T) -> None
update(obj: T) -> None
delete(id: str) -> None
get_by_id(id: str) -> Optional[T]
get_all() -> List[T]
exists(id: str) -> bool
```

#### EventRepository

```python
get_sorted_by_date() -> List[Event]
get_in_range(start: float, end: float) -> List[Event]
get_by_type(event_type: str) -> List[Event]
```

#### EntityRepository

```python
get_by_type(entity_type: str) -> List[Entity]
search_by_name(query: str) -> List[Entity]
```

#### RelationRepository

```python
get_by_source(source_id: str) -> List[Relation]
get_by_target(target_id: str) -> List[Relation]
get_by_type(rel_type: str) -> List[Relation]
delete_by_source(source_id: str) -> None
delete_by_target(target_id: str) -> None
```

---

## Performance Optimizations

### Indexes

ProjektKraken uses strategic indexes for fast queries:

```sql
-- Timeline queries
CREATE INDEX idx_events_date ON events(lore_date);

-- Relation lookups
CREATE INDEX idx_relations_source ON relations(source_id);
CREATE INDEX idx_relations_target ON relations(target_id);

-- Map queries
CREATE INDEX idx_markers_map ON markers(map_id);
CREATE INDEX idx_markers_object ON markers(object_id, object_type);

-- Temporal queries
CREATE INDEX idx_moving_features_marker ON moving_features(marker_id);
CREATE INDEX idx_moving_features_time ON moving_features(t_start, t_end);
```

### Write-Ahead Logging (WAL)

ProjektKraken enables WAL mode for concurrent reads:

```python
db_service.execute_sql("PRAGMA journal_mode=WAL;")
```

**Benefits:**
- Multiple readers don't block each other
- Writers don't block readers (usually)
- Better performance for write-heavy workloads
- Automatic checkpointing

### Transactions

Use transactions for multi-step operations:

```python
with db_service.transaction():
    event_repo.insert(event)
    for entity_id in participant_ids:
        relation = Relation(
            source_id=event.id,
            target_id=entity_id,
            rel_type="participated_in"
        )
        relation_repo.insert(relation)
```

**Benefits:**
- Atomic operations (all or nothing)
- Better performance (single commit)
- Data consistency

### Query Optimization Tips

1. **Use indexed columns in WHERE clauses:**
   ```sql
   -- Good (uses index)
   SELECT * FROM events WHERE lore_date BETWEEN 100 AND 200;
   
   -- Bad (no index on attributes)
   SELECT * FROM events WHERE JSON_EXTRACT(attributes, '$.status') = 'active';
   ```

2. **Limit result sets:**
   ```python
   # Get only visible events
   events = event_repo.get_in_range(view_start, view_end)
   ```

3. **Batch operations:**
   ```python
   with db_service.transaction():
       for event in events:
           event_repo.update(event)
   ```

4. **Lazy loading:**
   ```python
   # Don't load all relations upfront
   relations = relation_repo.get_by_source(event.id)  # Load on demand
   ```

---

## Migration Strategy

### Schema Versioning

ProjektKraken tracks schema version in `system_meta`:

```sql
INSERT INTO system_meta (key, value) VALUES ('schema_version', '1.0');
```

### Migration Scripts

Located in `scripts/migrate_data.py`:

```python
def migrate_v1_to_v2(db_service: DatabaseService) -> None:
    """Migrate from schema v1 to v2."""
    # Add new column
    db_service.execute_sql(
        "ALTER TABLE events ADD COLUMN lore_duration REAL DEFAULT 0.0"
    )
    # Update schema version
    db_service.execute_sql(
        "UPDATE system_meta SET value = '2.0' WHERE key = 'schema_version'"
    )
```

### Running Migrations

Migrations run automatically on database open:

```python
class DatabaseService:
    def connect(self) -> None:
        self.conn = sqlite3.connect(self.db_path)
        self._init_schema()  # Creates tables if missing
        self._run_migrations()  # Upgrades schema if needed
```

### Backward Compatibility

- **Additive changes:** New columns with defaults (safe)
- **Breaking changes:** Require data transformation and version bump
- **JSON attributes:** Always backward compatible (optional fields)

---

## Best Practices

### 1. Always Use Repositories

```python
# Good
event_repo.insert(event)

# Bad
db_service.execute_sql("INSERT INTO events VALUES (...)")
```

### 2. Use Transactions for Multi-Step Operations

```python
with db_service.transaction():
    event_repo.update(event)
    relation_repo.delete_by_source(event.id)
```

### 3. Handle None Returns

```python
event = event_repo.get_by_id(event_id)
if event is None:
    logger.warning(f"Event not found: {event_id}")
    return
```

### 4. Close Database Connections

```python
db_service = DatabaseService("myworld.kraken")
try:
    db_service.connect()
    # Do work
finally:
    db_service.close()
```

### 5. Use Context Managers

```python
@contextmanager
def db_transaction(db_service: DatabaseService):
    try:
        yield db_service
        db_service.commit()
    except Exception:
        db_service.rollback()
        raise
```

### 6. Validate Before Insert/Update

```python
def validate_event(event: Event) -> List[str]:
    errors = []
    if not event.name:
        errors.append("Name is required")
    if event.lore_duration < 0:
        errors.append("Duration cannot be negative")
    return errors
```

### 7. Use Prepared Statements (Security)

Repositories use parameterized queries automatically:

```python
# Good (repository uses parameters)
event_repo.get_by_id(user_input)

# Bad (SQL injection risk)
db_service.execute_sql(f"SELECT * FROM events WHERE id = '{user_input}'")
```

---

## Testing

### Test Database Setup

```python
@pytest.fixture
def db_service():
    """Provides a fresh in-memory database for each test."""
    from src.services.db_service import DatabaseService
    
    service = DatabaseService(":memory:")
    service.connect()
    yield service
    service.close()
```

### Test Data Creation

```python
def test_event_crud(db_service):
    """Test event CRUD operations."""
    from src.core.events import Event
    
    # Create
    event = Event(name="Test", lore_date=100.0)
    db_service.event_repo.insert(event)
    
    # Read
    loaded = db_service.event_repo.get_by_id(event.id)
    assert loaded.name == "Test"
    
    # Update
    loaded.name = "Updated"
    db_service.event_repo.update(loaded)
    
    # Delete
    db_service.event_repo.delete(event.id)
    assert db_service.event_repo.get_by_id(event.id) is None
```

---

## Tools and Utilities

### Database Verification

```bash
python scripts/verify_db.py myworld.kraken
```

Checks for:
- Schema integrity
- Orphaned relations
- Missing indexes
- Data consistency

### Schema Documentation Generator

```bash
python docs/generate_schema_docs.py
```

Generates HTML documentation from schema.

### Database Browser

Use SQLite browser tools:
- **DB Browser for SQLite** (GUI)
- **sqlite3 CLI** (command line)

```bash
sqlite3 myworld.kraken
sqlite> .schema
sqlite> SELECT * FROM events LIMIT 10;
```

---

## Additional Resources

- [Architecture Guide](ARCHITECTURE.md) - System design
- [Development Guide](DEVELOPMENT.md) - Setup and coding standards
- [API Reference](API.md) - Code API documentation
- [SQLite Documentation](https://www.sqlite.org/docs.html) - SQLite reference

---

## Questions?

- **Issues:** https://github.com/yourusername/ProjektKraken/issues
- **Discussions:** https://github.com/yourusername/ProjektKraken/discussions
