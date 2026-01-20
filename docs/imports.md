# JSON Import Documentation

ProjektKraken supports importing **Entities**, **Events**, and their **Relations** via structured JSON files. This feature allows for batch operations, data migration, and integration with external tools (including LLMs).

## Access

*   **Menu**: `File > Import Item...`
*   **CLI**: `python -m src.app.main import --file <path>` (Planned)

## Data Structure

## Deduplication & Matching

The system attempts to match incoming data to existing records to prevent duplicates. It follows this order of operations:

1.  **External ID**: If `external_id` (e.g., `"obsidian-123"`) is provided, it looks for an existing entity tagged with that ID from the same **Source Name**.
2.  **UUID**: If `id` (ProjektKraken UUID) is provided, it looks for an exact ID match.
3.  **Name**: If neither ID matches, it searches for an existing entity with the exact same name (case-insensitive normalized).

**Ambiguity**: If multiple entities share the same name (and no ID is provided), the importer flags the item as `AMBIGUOUS` and skips it to avoid incorrect merging.

## Import Configuration

When importing via the GUI, you can configure:

*   **Source Name**: A tag identifying where the data came from (e.g., `"obsidian"`, `"world_anvil"`). Defaults to `"manual_import"`. This scopes the `external_id` lookup.
*   **Import Mode**:
    *   **Update** (Default): Merges new data into the existing record. New values overwrite old ones; missing/null values in the input are ignored.
    *   **Overwrite**: Replaces the existing record's core fields (description, type, attributes) entirely with the new data.
    *   **Skip**: Ignores the incoming item if a match is found.
*   **Dry Run**: Simulates the import and reports what would happen (Create, Update, Skip, Ambiguous) without modifying the database.

## Data Structure

The import file should be a JSON object containing one or more of the following keys: `entities`, `events`, `relations`.

### 1. Entities

Entities represent characters, locations, factions, objects, etc.

```json
{
  "entities": [
    {
      "name": "King Alaric",
      "external_id": "wiki-alaric-01", 
      "type": "character",
      "description": "The first king of the North.",
      "attributes": {
        "age": 45,
        "_tags": ["royalty", "human"]
      },
      "relations": [
        {
          "target_name": "The Northern Kingdom",
          "rel_type": "rules"
        }
      ]
    }
  ]
}
```

**Fields:**
*   `name` (Required): Unique name for identification (fallback).
*   `external_id` (Optional): ID from the source system (Primary Match Key).
*   `type` (Optional): Category e.g., "character", "location". Default: "generic".
*   `description` (Optional): Textual description.
*   `attributes` (Optional): Dictionary of custom data.
    *   `_tags`: List of strings for tagging.
*   `relations` (Optional): List of outgoing relationships (see below).

### 2. Events

Events represent points or durations in time.

```json
{
  "events": [
    {
      "name": "The Coronation",
      "external_id": "evt-001",
      "lore_date": "Year 500",
      "lore_duration": 0.0,
      "type": "ceremony",
      "description": "Alaric is crowned king.",
      "relations": [
        {
          "target_name": "King Alaric",
          "rel_type": "involved"
        }
      ]
    }
  ]
}
```

**Fields:**
*   `name` (Required): Event title.
*   `external_id` (Optional): ID from source system.
*   `lore_date` (Required): Float ID or Date String.
    *   **Float**: Raw timestamp (e.g., `1050.5`).
    *   **String**: "Natural" date string (e.g., `"Year 500"`, `"15th of Harvest, Year 300"`). These are parsed using the active calendar configuration.
*   `lore_duration` (Optional): Duration in days. Default: 0.0.
*   `type` (Optional): e.g., "scene", "battle". Default: "generic".
*   `description` (Optional): Event details.
*   `attributes`, `relations`: Same as Entities.

### 3. Relations

Relations connect an Entity/Event to another Entity/Event. They can be defined:
1.  **Nested**: Inside an entity or event JSON object (as shown above).
2.  **Top-level**: In a `relations` list at the root of the JSON file.

```json
"relations": [
  {
    "source_name": "King Alaric",
    "target_name": "The Crown",
    "rel_type": "owns"
  }
]
```

**Fields:**
*   `target_name` (Required if nested): Exact name of the target item.
*   `source_name` (Required if top-level): Exact name of the source item.
*   `rel_type` (Optional): Type of relationship. Default: "related".
*   `attributes` (Optional): Metadata for the relationship.

## AI / LLM Extraction Prompt

You can use the following system prompt to instruct an LLM (like ChatGPT or Claude) to generate compatible JSON from text.

> **System Prompt:**
> You are a data extraction assistant. Extract entities, events, and their relationships from the user's text into a JSON object with the following structure.
>
> **JSON Schema:**
> ```json
> {
>   "entities": [
>     {
>       "name": "string (required)",
>       "external_id": "string (optional unique ID)",
>       "type": "string (e.g., character, location)",
>       "description": "string",
>       "attributes": { "_tags": ["tag1"], "key": "val" },
>       "relations": [
>         { "target_name": "exact name of target", "rel_type": "string" }
>       ]
>     }
>   ],
>   "events": [
>     {
>       "name": "string (required)",
>       "external_id": "string (optional unique ID)",
>       "lore_date": "float OR string (e.g., 'Year 100', '15th of Month 1, Year 500 14:30')",
>       "lore_duration": float (optional, 1.0 = 1 day),
>       "type": "string",
>       "attributes": { ... },
>       "relations": [
>         { "target_name": "exact name of target", "rel_type": "string" }
>       ]
>     }
>   ]
> }
> ```
> **Rules:**
> 1. Use `target_name` for relations. It must match the `name` of an existing or extracted item EXACTLY.
> 2. `lore_date` can be a raw number (float) OR a natural date string (e.g., "Year 500", "1st of Hammer, Year 1000 12:30 PM").
> 3. Nest relations inside their source item.
> 4. Output ONLY valid JSON.
