---
**Project:** ProjektKraken  
**Document:** Tag Normalization Migration Guide  
**Last Updated:** 2026-01-01  
**Commit:** `d9e3f83`  
---

# Tag Normalization Migration Guide

## Overview

ProjektKraken has been upgraded to use normalized database tables for tags, improving query performance and data consistency. Tags are now stored in dedicated tables (`tags`, `event_tags`, `entity_tags`) with proper indexes and foreign key constraints.

## What Changed

### Before (Denormalized)
- Tags were stored as JSON arrays in the `attributes` column:
  ```json
  {"_tags": ["important", "battle", "victory"]}
  ```
- No database-level constraints or indexes on tags
- Difficult to query events/entities by tag efficiently

### After (Normalized)
- Tags stored in dedicated `tags` table with unique constraint
- Associations stored in `event_tags` and `entity_tags` join tables
- Proper indexes for fast querying
- Foreign key constraints with CASCADE delete
- **Backward compatible**: JSON attributes still maintained for compatibility

## Database Schema

### Tags Table
```sql
CREATE TABLE tags (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at REAL NOT NULL
);
CREATE INDEX idx_tags_name ON tags(name);
```

### Event-Tag Association
```sql
CREATE TABLE event_tags (
    event_id TEXT NOT NULL,
    tag_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (event_id, tag_id),
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);
CREATE INDEX idx_event_tags_event ON event_tags(event_id);
CREATE INDEX idx_event_tags_tag ON event_tags(tag_id);
```

### Entity-Tag Association
```sql
CREATE TABLE entity_tags (
    entity_id TEXT NOT NULL,
    tag_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (entity_id, tag_id),
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);
CREATE INDEX idx_entity_tags_entity ON entity_tags(entity_id);
CREATE INDEX idx_entity_tags_tag ON entity_tags(tag_id);
```

## Migration Process

### For New Databases
No action required! The normalized tables are created automatically when you create a new world.

### For Existing Databases

#### Step 1: Backup Your Database
**CRITICAL**: Always backup your `.kraken` file before running migrations!

```bash
# Copy your world.kraken file
cp ~/.local/share/ProjektKraken/world.kraken ~/.local/share/ProjektKraken/world.kraken.backup
```

#### Step 2: Run the Migration Script

```bash
# Migrate with user data directory (default location)
python migrate_tags.py

# Or specify a custom database path
python migrate_tags.py --db-path /path/to/your/world.kraken

# Dry run to preview changes without committing
python migrate_tags.py --dry-run
```

#### Step 3: Verify Migration

The migration script will:
1. Extract all tags from events and entities
2. Create unique tag entries
3. Create event-tag and entity-tag associations
4. Verify data integrity
5. Display migration statistics

Example output:
```
INFO: Extracting tags from events...
INFO: Extracted tags from 150 events
INFO: Extracting tags from entities...
INFO: Extracted tags from 75 entities
INFO: Found 45 unique tags
INFO: Inserting 45 tags into tags table...
INFO: Creating event-tag associations...
INFO: Created 200 event-tag associations
INFO: Creating entity-tag associations...
INFO: Created 100 entity-tag associations
INFO: Migration verification passed!
============================================================
MIGRATION STATISTICS:
  Events processed: 150
  Entities processed: 75
  Unique tags: 45
  Event-tag associations: 200
  Entity-tag associations: 100
============================================================
```

### Migration Features

- **Idempotent**: Can be run multiple times safely
- **Automatic Deduplication**: Handles duplicate tags within items
- **Whitespace Normalization**: Trims leading/trailing whitespace
- **Case-Sensitive**: Preserves tag name case
- **Backward Compatible**: JSON attributes retained

## Rollback Plan

If you need to rollback:

### Option 1: Restore from Backup (Recommended)
```bash
cp ~/.local/share/ProjektKraken/world.kraken.backup ~/.local/share/ProjektKraken/world.kraken
```

### Option 2: Drop Normalized Tables
If you want to keep your database but remove normalized tables:

```sql
-- Connect to your database with sqlite3
sqlite3 ~/.local/share/ProjektKraken/world.kraken

-- Drop the normalized tables
DROP TABLE IF EXISTS event_tags;
DROP TABLE IF EXISTS entity_tags;
DROP TABLE IF EXISTS tags;
```

**Note**: The application will continue to work after rollback because tags remain in JSON attributes.

## API Changes

### New DatabaseService Methods

```python
# Get all tags
tags = db_service.get_all_tags()
# Returns: [{"id": "uuid", "name": "tag-name", "created_at": timestamp}, ...]

# Create a tag
tag_id = db_service.create_tag("important")

# Assign tag to event
db_service.assign_tag_to_event(event_id, "important")

# Assign tag to entity
db_service.assign_tag_to_entity(entity_id, "protagonist")

# Get tags for an event
tags = db_service.get_tags_for_event(event_id)

# Get tags for an entity
tags = db_service.get_tags_for_entity(entity_id)

# Remove tag from event
db_service.remove_tag_from_event(event_id, "important")

# Remove tag from entity
db_service.remove_tag_from_entity(entity_id, "protagonist")

# Delete a tag (removes all associations)
db_service.delete_tag("obsolete-tag")

# Query by tag
events = db_service.get_events_by_tag("important")
entities = db_service.get_entities_by_tag("protagonist")
```

### Command Behavior

Event and Entity commands now automatically sync tags to normalized tables:

```python
# Creating event with tags
event_data = {
    "name": "Battle of...",
    "lore_date": 1000.0,
    "attributes": {"_tags": ["important", "battle"]}
}
cmd = CreateEventCommand(event_data)
cmd.execute(db_service)
# Tags are automatically synced to normalized tables

# Updating event tags
update_data = {
    "attributes": {"_tags": ["important", "victory"]}  # "battle" removed, "victory" added
}
cmd = UpdateEventCommand(event_id, update_data)
cmd.execute(db_service)
# Changes are automatically synced
```

## Performance Benefits

1. **Fast Tag Queries**: Indexed lookups instead of JSON parsing
2. **Efficient Filtering**: Use JOINs for multi-tag queries
3. **Data Integrity**: Foreign key constraints ensure consistency
4. **Deduplication**: Single source of truth for tag names

## Backward Compatibility

- Event.tags and Entity.tags properties still work
- GUI components continue to use existing interfaces
- JSON attributes retained for compatibility
- Gradual migration - both systems work together

## Testing

Comprehensive test suite ensures reliability:
- 20 unit tests for tag CRUD operations
- 11 unit tests for migration logic
- 9 integration tests for end-to-end flows
- All 759 existing tests pass

## Troubleshooting

### Migration fails with "database is locked"
- Close ProjektKraken application
- Ensure no other processes are accessing the database

### Tags disappear after migration
- Check migration statistics for processed counts
- Verify JSON attributes still contain tags: `SELECT attributes FROM events WHERE id = 'event-id'`
- Restore from backup if needed

### Performance issues
- Run `VACUUM;` to optimize database
- Ensure indexes exist: `SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%tags%'`

## Support

For issues or questions:
1. Check migration statistics output
2. Verify backup exists before attempting fixes
3. Report issues with migration log output

## Future Plans

- Gradual deprecation of JSON tag storage
- Enhanced tag filtering in GUI
- Tag usage statistics
- Bulk tag operations
- Tag renaming with automatic cascade

---

**Version**: 1.0.0  
**Date**: December 2025  
**Backward Compatible**: Yes  
**Migration Required**: For existing databases only
