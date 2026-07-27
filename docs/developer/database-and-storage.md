# Database and Storage

## Portable worlds

Each world contains:

```text
worlds/<World Name>/
├── world.json
├── <World Name>.kraken
└── assets/
```

The SQLite database uses strict columns for stable fields and JSON attributes
for extensible feature data.

## Data conventions

- IDs are `str(uuid.uuid4())`.
- Timestamps are floats.
- Lore time is stored as float days.
- Domain models remain dataclasses with `to_dict()` and `from_dict()`.

## Access rules

All runtime database access occurs through the worker-owned
`DatabaseService`. Repositories organize table-specific access but do not
change the thread-ownership rule.

Use transactions for multi-part mutations. Database state is canonical; the UI
renders snapshots derived from it.

## Schema reference

The generated [database schema](../reference/database-schema.md) is extracted
from `DatabaseService._init_schema()`. Regenerate it after changing the schema:

```text
python docs/generate_schema_docs.py
```

