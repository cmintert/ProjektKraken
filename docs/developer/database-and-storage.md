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

The complete folder is the supported storage unit and may be registered from a
local drive, removable drive, mapped drive, UNC share, or synchronized folder.
Self-contained manifest database paths must be relative, end in `.kraken`, and
resolve inside the world folder. Absolute paths, drive paths, UNC paths, `..`, and
symlink escapes are rejected in this mode.

## Advanced external database mode

An existing `.kraken` file outside the world folder can be linked through World
Manager. The manifest records `storage_mode: external_database`, but that field is
not authorization. ProjektKraken binds approval of the fully resolved database path
to the manifest folder in local `QSettings`. A copied manifest therefore cannot
carry trust to another installation or folder.

External approvals can be revoked in World Manager. Missing external databases are
reported and never opened through SQLite's create-if-missing behavior. External
storage reduces portability, separates asset and database backup concerns, and is
unsafe for simultaneous multi-user SQLite editing. Synchronization tools can also
produce conflicting database copies.

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
