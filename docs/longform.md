# Longform Document Feature

## Overview

The Longform Document feature allows you to assemble Events and Entities into a single continuous narrative document. This feature provides:

- **Single Live Document**: All events and entities can participate in one unified document (identified by `doc_id = "default"`)
- **Flexible Ordering**: Reorder entries using float-based positions
- **Hierarchical Structure**: Create parent-child relationships with unlimited nesting depth
- **Title Overrides**: Customize headings without changing the underlying Event/Entity name
- **Canonical Editing**: Edit content directly, and changes update the source Event/Entity
- **Markdown Export**: Export the complete document to Markdown with ID traceability markers

## Attributes JSON Format

Longform metadata is stored in the `attributes` JSON column of both `events` and `entities` tables. The structure follows this format:

```json
{
  "longform": {
    "default": {
      "position": 100.0,
      "parent_id": "uuid-of-parent-or-null",
      "depth": 0,
      "title_override": "Optional custom heading"
    }
  },
  "other_metadata": "..."
}
```

### Metadata Fields

- **`position`** (float, required): Determines the order of items in the document. Uses gaps of 100.0 by default (100, 200, 300...). Items are sorted by position within their parent group.

- **`parent_id`** (string or null, required): The UUID of the parent item. `null` indicates a top-level item. Parent can be from either events or entities table.

- **`depth`** (integer, required): The nesting depth, starting at 0 for top-level items. Child items have `depth = parent_depth + 1`.

- **`title_override`** (string, optional): If provided, this text is used as the heading instead of the item's name. Useful for customizing section titles.

### Example Metadata

```json
{
  "longform": {
    "default": {
      "position": 150.0,
      "parent_id": "abc-123-parent-uuid",
      "depth": 2,
      "title_override": "Act II: The Confrontation"
    }
  }
}
```

## Usage

### Adding Items to Longform

To add an Event or Entity to the longform document, you need to add the longform metadata to its `attributes` JSON:

```python
from src.services import longform_builder

# Add an event to longform
longform_builder.insert_or_update_longform_meta(
    conn,
    table="events",
    row_id="event-uuid-here",
    position=100.0,
    parent_id=None,  # Top level
    depth=0
)

# Add as a child
longform_builder.insert_or_update_longform_meta(
    conn,
    table="entities",
    row_id="entity-uuid-here",
    position=150.0,
    parent_id="event-uuid-here",  # Parent
    depth=1
)
```

### Building the Document Sequence

To retrieve the ordered, hierarchical sequence for rendering:

```python
from src.services import longform_builder

sequence = longform_builder.build_longform_sequence(conn)

for item in sequence:
    print(f"{'#' * item['heading_level']} {item['name']}")
    print(item['content'])
```

### Reordering and Nesting

**Place between siblings:**
```python
longform_builder.place_between_siblings_and_set_parent(
    conn,
    target_table="events",
    target_id="item-to-move",
    prev_sibling=("events", "previous-item-id"),
    next_sibling=("events", "next-item-id"),
    parent_id="parent-id-or-none"
)
```

**Promote (reduce depth):**
```python
longform_builder.promote_item(conn, "events", "item-id")
```

**Demote (increase depth, make child of previous sibling):**
```python
longform_builder.demote_item(conn, "events", "item-id")
```

**Remove from longform:**
```python
longform_builder.remove_from_longform(conn, "events", "item-id")
```

### Reindexing Positions

After many insertions, float positions may become fragmented. Reindex to reset to clean 100, 200, 300... positions:

```python
longform_builder.reindex_document_positions(conn)
```

## CLI Export Tool

The longform export CLI tool generates a Markdown file from your longform document.

### Basic Usage

```bash
# Export to stdout
python -m src.cli.export_longform world.kraken

# Export to file
python -m src.cli.export_longform world.kraken longform_export.md

# Export with verbose logging
python -m src.cli.export_longform world.kraken output.md --verbose
```

### Markdown Format

The exported Markdown includes:

- Document title header
- HTML comment markers with ID and table information for traceability
- Hierarchical headings based on depth (# for depth 0, ## for depth 1, etc., capped at 6)
- Content from the `description` field

Example output:
```markdown
# Longform Document: default

<!-- PK-LONGFORM id=abc-123 table=events doc=default -->
# Chapter 1: The Beginning

Once upon a time, in a land far away...

<!-- PK-LONGFORM id=def-456 table=events doc=default -->
## Section 1.1: The Hero's Journey

The hero set out on a quest...
```

## Migration and Database Safety

### Running the Migration

Before using the longform feature, ensure the `attributes` column exists:

```bash
# IMPORTANT: Backup your database first!
cp world.kraken world.kraken.backup

# The migration is idempotent and safe to run
sqlite3 world.kraken < migrations/0003_add_attributes_columns_longform.sql
```

**Note:** The `DatabaseService._init_schema()` already creates the attributes column for new databases, so this migration is mainly for legacy databases.

### Migration Safety

The migration is designed to be **idempotent** (safe to run multiple times):

- If the `attributes` column already exists, the `ALTER TABLE` commands will fail harmlessly
- The migration includes defensive `UPDATE` statements to ensure no `NULL` values remain
- No data is deleted or modified beyond adding the column

### Safety Checklist

1. ✅ **Backup**: Always backup your `.kraken` file before running migrations
2. ✅ **Test First**: Run on a copy of your database before production
3. ✅ **Verify**: Use the sanity check script (see below) to validate JSON parsing
4. ✅ **Staged Rollout**: Test in a staging environment first

### Rollback Instructions

If you need to rollback the migration:

**Option 1: Restore from Backup** (Recommended)
```bash
# Stop the application
cp world.kraken.backup world.kraken
# Restart the application
```

**Option 2: Remove Longform Metadata Only**
```sql
-- This removes only longform data, keeping the attributes column
UPDATE events 
SET attributes = json_remove(attributes, '$.longform') 
WHERE json_extract(attributes, '$.longform') IS NOT NULL;

UPDATE entities 
SET attributes = json_remove(attributes, '$.longform') 
WHERE json_extract(attributes, '$.longform') IS NOT NULL;
```

**Option 3: Remove Column** (Not recommended - loses all attributes data)
```sql
-- WARNING: This removes ALL data in the attributes column, not just longform!
-- Only use if you have no other data in attributes
ALTER TABLE events DROP COLUMN attributes;
ALTER TABLE entities DROP COLUMN attributes;
```

### Sanity Check Script

Create a simple script to verify attributes JSON can be parsed:

```python
#!/usr/bin/env python3
"""Sanity check for attributes JSON parsing."""

import sqlite3
import json
import sys

def check_database(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    errors = []
    
    # Check events
    for row in conn.execute("SELECT id, attributes FROM events"):
        try:
            if row["attributes"]:
                json.loads(row["attributes"])
        except json.JSONDecodeError as e:
            errors.append(f"Event {row['id']}: {e}")
    
    # Check entities
    for row in conn.execute("SELECT id, attributes FROM entities"):
        try:
            if row["attributes"]:
                json.loads(row["attributes"])
        except json.JSONDecodeError as e:
            errors.append(f"Entity {row['id']}: {e}")
    
    conn.close()
    
    if errors:
        print("❌ JSON parsing errors found:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("✅ All attributes JSON valid")
        return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python sanity_check.py world.kraken")
        sys.exit(1)
    
    success = check_database(sys.argv[1])
    sys.exit(0 if success else 1)
```

Save as `sanity_check.py` and run:
```bash
python sanity_check.py world.kraken
```

## Command Pattern (Undo/Redo)

All longform operations that modify structure support undo/redo via command objects:

```python
from src.commands.longform_commands import (
    MoveLongformEntryCommand,
    PromoteLongformEntryCommand,
    DemoteLongformEntryCommand,
    RemoveLongformEntryCommand,
)

# Move command
old_meta = {"position": 100.0, "parent_id": None, "depth": 0}
new_meta = {"position": 200.0, "parent_id": None, "depth": 0}
cmd = MoveLongformEntryCommand("events", "event-id", old_meta, new_meta)
result = cmd.execute(db_service)

# Undo the move
cmd.undo(db_service)

# Promote command
cmd = PromoteLongformEntryCommand("events", "event-id", old_meta)
result = cmd.execute(db_service)
cmd.undo(db_service)
```

## Best Practices

### Position Management

- **Use large gaps**: Default gap of 100.0 allows many insertions without reindexing
- **Reindex periodically**: If you notice many fractional positions (e.g., 100.5, 100.25), run reindex
- **Place between siblings**: Use `place_between_siblings_and_set_parent()` for clean insertions

### Parent-Child Relationships

- **No circular detection**: Avoid creating circular parent relationships (A → B → A)
- **Orphaned parents**: If you delete a parent, children become orphaned. Update children before deleting parents
- **Cross-table parents**: Parents can be from events or entities table

### Performance

- **Modest scale**: Full scan of events/entities is fine for databases with < 10,000 items
- **Large databases**: Consider adding an index column or cache if you have > 50,000 items
- **Lazy loading**: For very large documents, consider loading/rendering sections on demand

## Troubleshooting

### "Row not found" errors

Ensure the Event/Entity exists in the database before adding longform metadata.

### Positions not in order

Run `reindex_document_positions()` to reset positions to clean values.

### JSON parsing errors

Run the sanity check script to identify malformed JSON in attributes column.

### Parent-child structure not rendering correctly

Verify that:
- Parent IDs are valid UUIDs of existing items
- Depth values are consistent (child depth = parent depth + 1)
- All items in the hierarchy have longform metadata

### Float exhaustion

After many insertions between the same two items, you may get very small or large position values. Run reindex to fix.

## Future Enhancements

Potential improvements for future versions:

- Multiple document support (custom `doc_id` values)
- Automatic circular parent detection
- Index column for faster querying on large databases
- Real-time collaborative editing
- Version history for longform changes
- GUI outline editor with drag-and-drop
- Export to other formats (PDF, HTML, EPUB)

## See Also

- `src/services/longform_builder.py` - Core service implementation
- `src/commands/longform_commands.py` - Command objects for undo/redo
- `src/cli/export_longform.py` - CLI export tool
- `migrations/0003_add_attributes_columns_longform.sql` - Database migration
- `tests/integration/test_longform_integration.py` - Integration test examples
