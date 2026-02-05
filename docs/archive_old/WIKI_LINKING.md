---
**Project:** ProjektKraken  
**Document:** ID-Based Wiki Linking Guide  
**Last Updated:** 2026-01-01  
**Commit:** `d9e3f83`  
---

# ID-Based Wiki Linking Implementation Guide

## Overview

ProjektKraken now supports robust, ID-based wiki-style linking that ensures links remain valid even when entity or event names change. This document describes the implementation, usage, and technical details.

## Features

### 1. ID-Based Link Format

Links now use stable UUIDs internally while displaying human-readable names:

```
Format: [[id:UUID|DisplayName]]
Example: [[id:550e8400-e29b-41d4-a716-446655440000|Gandalf the Grey]]
```

### 2. Backward Compatibility

Legacy name-based links continue to work:

```
Legacy: [[EntityName]]
Legacy with Label: [[EntityName|Custom Label]]
```

The system automatically handles both formats, making migration seamless.

### 3. Smart Autocomplete

When typing `[[` in any description field:
- Autocomplete popup shows all entities and events
- Selecting an item inserts an ID-based link automatically
- Format: `[[id:UUID|Name]]`

### 4. Broken Link Detection

Broken links (where the target has been deleted) are visually indicated:
- **Red text color**
- **Strikethrough styling**
- Hover tooltip shows the broken ID

### 5. Name Change Propagation

When you rename an entity or event:
- All ID-based links automatically show the new name
- No manual updates needed
- Cache invalidation ensures real-time updates

### 6. Link Navigation

Ctrl+Click on any wiki link to navigate:
- ID-based links: Jumps directly to target by UUID
- Name-based links: Searches by name (case-insensitive)
- Works for both entities and events

## Architecture

### Components

#### 1. WikiLinkParser (`src/services/text_parser.py`)

Parses wiki links from text content.

**Key Methods:**
- `extract_links(text)` - Parses all links in text
- `format_id_link(uuid, name)` - Creates ID-based link string
- `format_name_link(name, label)` - Creates name-based link string

**Link Candidate Structure:**
```python
@dataclass
class LinkCandidate:
    raw_text: str           # Full [[...]] text
    name: Optional[str]     # Target name (if name-based)
    modifier: Optional[str] # Display label
    span: Tuple[int, int]   # Position in text
    target_id: Optional[str] # UUID (if ID-based)
    is_id_based: bool       # Format flag
```

#### 2. LinkResolver (`src/services/link_resolver.py`)

Resolves UUIDs to current entity/event names.

**Key Methods:**
- `resolve(uuid)` - Returns (name, type) for given UUID
- `get_display_name(uuid, fallback)` - Gets display name with fallback
- `find_broken_links(text)` - Finds all broken links in text
- `invalidate_cache(uuid)` - Clears cache for updated item

**Caching:**
- In-memory cache for performance
- Automatic invalidation on updates
- Supports both entities and events

#### 3. WikiTextEdit (`src/gui/widgets/wiki_text_edit.py`)

Enhanced text editor with wiki link support.

**Key Features:**
- Smart autocomplete for entities/events
- ID-based link insertion
- Ctrl+Click navigation
- Syntax highlighting integration

**Usage:**
```python
editor = WikiTextEdit()

# Set up autocomplete with IDs
items = [(entity.id, entity.name, "entity") for entity in entities]
editor.set_completer(items=items)

# Set link resolver for broken link detection
resolver = LinkResolver(db_service)
editor.set_link_resolver(resolver)

# Connect navigation signal
editor.link_clicked.connect(navigate_handler)
```

#### 4. WikiSyntaxHighlighter (`src/gui/utils/wiki_highlighter.py`)

Highlights wiki links with different styles.

**Styles:**
- Valid links: Blue, bold, underlined
- Broken links: Red, bold, strikethrough

**Usage:**
```python
highlighter = WikiSyntaxHighlighter(document)
highlighter.set_link_resolver(resolver)
```

#### 5. ProcessWikiLinksCommand (`src/commands/wiki_commands.py`)

Command pattern for processing wiki links into relations.

**Behavior:**
- Parses both ID-based and name-based links
- Creates "mentions" relations in database
- Stores metadata (snippet, offsets, is_id_based flag)
- Supports undo/redo

**Usage:**
```python
cmd = ProcessWikiLinksCommand(
    source_id=entity.id,
    text_content=entity.description,
    field="description"
)
result = cmd.execute(db_service)
```

## Usage Examples

### Creating ID-Based Links in Code

```python
from src.services.text_parser import WikiLinkParser

# Create an ID-based link
link = WikiLinkParser.format_id_link(
    target_id="550e8400-e29b-41d4-a716-446655440000",
    display_name="Gandalf the Grey"
)
# Result: [[id:550e8400-e29b-41d4-a716-446655440000|Gandalf the Grey]]
```

### Parsing Links from Text

```python
from src.services.text_parser import WikiLinkParser

text = """
The wizard [[id:550e8400-e29b-41d4-a716-446655440000|Gandalf]] 
met [[Frodo]] in [[The Shire]].
"""

links = WikiLinkParser.extract_links(text)
for link in links:
    if link.is_id_based:
        print(f"ID-based: {link.target_id} -> {link.modifier}")
    else:
        print(f"Name-based: {link.name}")
```

### Resolving Links

```python
from src.services.link_resolver import LinkResolver

resolver = LinkResolver(db_service)

# Resolve by ID
result = resolver.resolve("550e8400-e29b-41d4-a716-446655440000")
if result:
    name, type_ = result
    print(f"Found {type_}: {name}")
else:
    print("Broken link")

# Get display name with fallback
display = resolver.get_display_name(
    "550e8400-e29b-41d4-a716-446655440000",
    fallback_name="Deleted Entity"
)
```

### Finding Broken Links

```python
from src.services.link_resolver import LinkResolver

resolver = LinkResolver(db_service)

text = entity.description
broken = resolver.find_broken_links(text)

if broken:
    print(f"Found {len(broken)} broken links:")
    for uuid in broken:
        print(f"  - {uuid}")
```

## Migration from Name-Based Links

While ID-based links are preferred, migration is not required due to backward compatibility:

### Automatic Migration (Future Enhancement)

A migration tool can be implemented to convert all name-based links to ID-based:

```python
# Pseudo-code for future migration tool
def migrate_links(db_service):
    for entity in db_service.get_all_entities():
        text = entity.description
        links = WikiLinkParser.extract_links(text)
        
        for link in links:
            if not link.is_id_based:
                # Find matching entity
                target = find_entity_by_name(link.name)
                if target:
                    # Replace with ID-based link
                    new_link = WikiLinkParser.format_id_link(
                        target.id, link.name
                    )
                    text = text.replace(link.raw_text, new_link)
        
        entity.description = text
        db_service.insert_entity(entity)
```

### Manual Migration

Users can manually convert links:
1. Edit the entity/event description
2. Delete old link: `[[Name]]`
3. Type `[[` and select from autocomplete
4. New ID-based link is inserted automatically

## Quick Start Demo

### 1. Generate Sample Data

Create a test database with Middle Earth data to explore wiki linking features:

```bash
python tests/populate_middle_earth.py /tmp/middle_earth.kraken
```

This creates:
- 8 entities (Gandalf, Frodo, Aragorn, Sauron, locations, artifacts)
- 3 events (Council of Elrond, Fellowship formation, Fall of Sauron)
- 15 relations with ID-based wiki links

### 2. Explore Key Features

**ID-Based Links Example:**
```
Gandalf's description contains:
"He played a crucial role in defeating [[id:UUID|Sauron]] during the War of the Ring."
```

**Key Features to Try:**

1. **Autocomplete**: Type `[[` in any description field
   - Shows all entities and events
   - Selecting inserts `[[id:UUID|Name]]` automatically

2. **Broken Link Detection**: Links to deleted items show as red strikethrough

3. **Navigation**: Ctrl+Click any link to jump to target

4. **Name Changes**: Rename an entity - all ID-based links update automatically

### 3. Link Format Comparison

**Legacy Name-Based:**
```
[[Gandalf]] met [[Frodo]] in [[The Shire]].
```

**New ID-Based:**
```
[[id:550e8400-e29b-41d4-a716-446655440000|Gandalf]] met 
[[id:a1b2c3d4-e5f6-4789-0abc-def123456789|Frodo]] in 
[[id:9876543a-bcde-f012-3456-789abcdef012|The Shire]].
```

**Benefits of ID-Based:**
- ✅ Survives name changes
- ✅ Unambiguous references
- ✅ Broken link detection
- ✅ Auto-inserted by autocomplete

## Testing

### Unit Tests

Run parser and resolver tests:
```bash
pytest tests/unit/test_id_based_links.py
pytest tests/unit/test_link_resolver.py
pytest tests/unit/test_text_parser.py
```

### Integration Tests

Run full workflow tests:
```bash
pytest tests/integration/test_id_based_wiki_commands.py
pytest tests/integration/test_link_resolver_integration.py
```

### All Wiki Tests

```bash
pytest tests/ -k "wiki or link or text_parser"
```

Expected: **74 tests passing** ✅

## Database Schema

### Relations Table

Relations created by `ProcessWikiLinksCommand` include:

```json
{
    "id": "relation-uuid",
    "source_id": "source-entity-uuid",
    "target_id": "target-entity-uuid",
    "rel_type": "mentions",
    "attributes": {
        "field": "description",
        "snippet": "...[[link text]]...",
        "start_offset": 123,
        "end_offset": 145,
        "is_id_based": true,
        "created_by": "ProcessWikiLinksCommand",
        "created_at": 1234567890.0
    }
}
```

## Performance Considerations

### Caching

LinkResolver uses an in-memory cache:
- First resolution: Database query
- Subsequent: Cache hit (O(1))
- Cache invalidation: On entity/event updates

### Best Practices

1. **Share LinkResolver instances** - Don't create multiple resolvers
2. **Invalidate cache on updates** - Call `invalidate_cache(uuid)` after renaming
3. **Use ID-based links** - Preferred for new content
4. **Batch operations** - Process multiple links in one command

## Troubleshooting

### Links Not Highlighting

Check that highlighter has resolver set:
```python
editor.highlighter.set_link_resolver(resolver)
```

### Autocomplete Not Working

Verify completer is configured:
```python
items = [(id, name, type) for ...]
editor.set_completer(items=items)
```

### Broken Links Not Showing

1. Check LinkResolver is set on editor
2. Verify target entity/event exists in database
3. Clear cache: `resolver.invalidate_cache()`

### Navigation Not Working

Ensure signal is connected:
```python
editor.link_clicked.connect(main_window.navigate_to_entity)
```

## Future Enhancements

### Phase 4: Link Integrity Tools

Planned features for future releases:

1. **Link Integrity Checker**
   - Scan all entities/events for broken links
   - Generate report with statistics
   - Show link targets and sources

2. **Link Manager UI**
   - Dialog showing all broken links
   - Bulk fixing/relinking capabilities
   - Search and replace functionality

3. **Automatic Migration Tool**
   - Convert all name-based links to ID-based
   - Handle ambiguous name matches
   - Preview before applying

4. **Link Analytics**
   - Most-linked entities
   - Orphaned entities (no incoming links)
   - Link graph visualization

## API Reference

See inline docstrings for detailed API documentation:

- `src/services/text_parser.py` - Link parsing
- `src/services/link_resolver.py` - Link resolution
- `src/gui/widgets/wiki_text_edit.py` - Editor widget
- `src/gui/utils/wiki_highlighter.py` - Syntax highlighting
- `src/commands/wiki_commands.py` - Link processing command

## Contributing

When modifying the wiki linking system:

1. **Add tests** - Both unit and integration tests
2. **Update docs** - Keep this guide current
3. **Maintain compatibility** - Support legacy format
4. **Test thoroughly** - Run full test suite
5. **Consider performance** - Use caching appropriately

## License

This implementation follows the ProjektKraken project license.
