# Wiki-Style Linking Demo

## Quick Start

To see the ID-based wiki linking system in action, follow these steps:

### 1. Generate Sample Data

```bash
cd /home/runner/work/ProjektKraken/ProjektKraken
python tests/populate_middle_earth.py /tmp/middle_earth.kraken
```

This creates a database with:
- 8 entities (Gandalf, Frodo, Aragorn, Sauron, locations, artifacts)
- 3 events (Council of Elrond, Fellowship formation, Fall of Sauron)
- 15 relations with ID-based wiki links

### 2. Explore the Features

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

### 3. Test Data Details

**Sample Entity (Gandalf):**
```json
{
  "name": "Gandalf",
  "type": "character",
  "description": "A powerful wizard who arrived in Middle-earth around TA 1000. He played a crucial role in defeating [[id:UUID|Sauron]] during the War of the Ring. He was close friends with [[id:UUID|Aragorn]] and mentored [[id:UUID|Frodo]].",
  "attributes": {
    "race": "Maia",
    "aliases": ["Mithrandir", "Gandalf the Grey", "Gandalf the White"]
  }
}
```

**Sample Event (Council of Elrond):**
```json
{
  "name": "Council of Elrond",
  "lore_date": 3018.0,
  "description": "A great council held at [[id:UUID|Rivendell]] where the fate of [[id:UUID|the One Ring]] was decided. [[id:UUID|Frodo]] volunteered to carry the Ring to [[id:UUID|Mordor]].",
  "type": "council"
}
```

### 4. Link Format Comparison

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

### 5. Verify Test Results

Run the comprehensive test suite:

```bash
# All wiki-related tests
pytest tests/ -k "wiki or link or text_parser" -v

# Just ID-based link tests
pytest tests/unit/test_id_based_links.py -v

# Integration tests
pytest tests/integration/test_id_based_wiki_commands.py -v
```

Expected: **74 tests passing** ✅

### 6. View Sample Relations

The ProcessWikiLinksCommand creates "mentions" relations:

```python
{
    "source_id": "council-of-elrond-uuid",
    "target_id": "gandalf-uuid",
    "rel_type": "mentions",
    "attributes": {
        "field": "description",
        "snippet": "...[[id:UUID|Gandalf]] met...",
        "start_offset": 42,
        "end_offset": 95,
        "is_id_based": true
    }
}
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                     User Interface                      │
│  ┌───────────────────┐  ┌──────────────────────────┐   │
│  │  WikiTextEdit     │  │  WikiSyntaxHighlighter   │   │
│  │  - Autocomplete   │  │  - Valid: Blue/Bold      │   │
│  │  - Insert Links   │  │  - Broken: Red/Strike    │   │
│  └─────────┬─────────┘  └──────────┬───────────────┘   │
└───────────┼────────────────────────┼───────────────────┘
            │                        │
            ▼                        ▼
┌───────────────────────────────────────────────────────┐
│                  Service Layer                        │
│  ┌──────────────────┐     ┌────────────────────────┐ │
│  │  WikiLinkParser  │     │   LinkResolver         │ │
│  │  - Parse Links   │     │   - Resolve IDs        │ │
│  │  - Format Links  │     │   - Detect Broken      │ │
│  └──────────────────┘     │   - Cache Results      │ │
│                           └────────────────────────┘ │
└───────────────────────────────────────────────────────┘
            │                        │
            ▼                        ▼
┌───────────────────────────────────────────────────────┐
│              Command & Persistence Layer              │
│  ┌─────────────────────────┐  ┌──────────────────┐   │
│  │ ProcessWikiLinksCommand │  │  DatabaseService │   │
│  │ - Create Relations      │  │  - SQLite Store  │   │
│  │ - Undo/Redo Support     │  │  - Hybrid Schema │   │
│  └─────────────────────────┘  └──────────────────┘   │
└───────────────────────────────────────────────────────┘
```

## Next Steps

1. **Explore the Code**: See `docs/WIKI_LINKING.md` for full documentation
2. **Run Tests**: Verify everything works on your system
3. **Create Content**: Try adding entities/events with wiki links
4. **Test Renaming**: Change an entity name and see links update
5. **Break Links**: Delete an entity and see broken link indicators

## Troubleshooting

**Issue**: Links not highlighting  
**Fix**: Ensure LinkResolver is set: `editor.set_link_resolver(resolver)`

**Issue**: Autocomplete not showing  
**Fix**: Set items: `editor.set_completer(items=[(id, name, type), ...])`

**Issue**: Broken links not red  
**Fix**: Check that highlighter has resolver

**Issue**: Can't navigate links  
**Fix**: Connect signal: `editor.link_clicked.connect(handler)`

## Resources

- User Guide: `docs/WIKI_LINKING.md`
- Implementation Summary: `IMPLEMENTATION_SUMMARY.md`
- Sample Data Script: `tests/populate_middle_earth.py`
- Test Suite: `tests/unit/test_id_based_links.py` and others
