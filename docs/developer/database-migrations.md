# World migrations and recovery

World schema versions are independent of app releases and `world.json.version`.
The authoritative version is `system_meta` key `schema_version`. The
`migration_history` table records version, stable migration ID, application
version, completion time, and whether the database was created or upgraded.

## Inspecting a world

Use a read-only SQLite connection and `inspect_database(connection)` from
`src.services.migrations`. Its serializable result contains `detected_version`,
`target_version`, `pending_steps`, and `completed_entries`. Empty files report
`empty: true` and no detected version. Recognized pre-ledger worlds report version
0; unsupported layouts or contradictory ledgers raise `MigrationError`.

```python
import sqlite3
from contextlib import closing
from pathlib import Path
from src.services.migrations import inspect_database

database = Path("worlds/My World/My World.kraken").resolve()
with closing(sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)) as connection:
    status = inspect_database(connection)
```

The first three migration IDs are `001_structural_compatibility`,
`002_mfjson_trajectories`, and `003_canonical_relations`. Legacy compatibility
covers the core event/entity/relation schema and supported optional tables,
including tags without color, history without timestamp, and markers without
geometry/style fields. Frozen SQL fixtures under `tests/fixtures/migrations/`
identify the historical commits used to verify those contracts.

## Upgrade guarantees

`DatabaseService.connect()` delegates to the subsystem before binding repositories.
New empty databases receive the complete current schema and a `created_current`
ledger entry in one transaction. Existing versioned databases are never adopted
by guessing their table shape. Future versions, missing integrity objects, and
inconsistent ledgers block writable startup rather than triggering repairs.

Upgrades reserve SQLite's writer lock with `BEGIN IMMEDIATE`. This excludes other
writers while allowing a separate read connection for the backup API in both WAL
and rollback-journal modes. Inspection is repeated under that reservation. All
pending migration steps and ledger updates commit together; any exception rolls
back the entire upgrade. Readers may continue using the original snapshot; a
reader that prevents commit causes a safe failure instead of a partial upgrade.

Trajectory conversion preserves row IDs, properties, and keyframe order. Invalid
JSON, malformed coordinates, nonfinite numbers, or duplicate/reversed times block
conversion with record IDs. The relation step keeps established endpoint cleanup,
duplicate removal, and derived-mention rebuilding. Ambiguous endpoint names and
malformed manual relation attributes block the upgrade.

Only an unnormalized relation schema resets old command history and edit sessions.
Worlds already marked `wikilink_relations_schema_version = 2` preserve their history.
External command artifacts are never deleted by migrations. When existing history
is reset, startup tells the user where it was archived.

Read-only opens inspect without creating schema, stamping a ledger, changing
journal mode, or producing backups. Reopening a current world validates it without
running migration DDL or creating another recovery bundle.

## Recovery bundles

Before modifying an existing file-backed world, Kraken writes a unique directory
under the application backup directory's `migrations/` subdirectory. This directory
is outside automatic backup retention. It contains:

- `database.kraken`: a SQLite backup including committed WAL contents.
- `command_artifacts/`: verified copies of `assets/.history`, when present.
- `trashed_assets/`: deleted images needed by attachment undo, when present.
- `world.json`: the manifest, when available.
- `recovery.json`: original database/world paths, original schema status,
  SHA-256 checksums, and restoration instructions.

Database integrity, artifact checksums, and referenced undo artifact completeness
are checked before upgrading. Files are flushed before `recovery.json` is finalized.
A directory without `recovery.json` is incomplete and must not be used for recovery.
If backups cannot be verified, the world is not upgraded. In-memory test worlds
use the same transactions but require no filesystem backup.

On failure, the worker closes and clears its services and reports the failed step,
affected records, database path, and recovery location. No further world loading
or command execution proceeds. Kraken never restores over a database automatically.

To restore, close Kraken and all other clients, preserve a copy of the failed
world, and follow `recovery.json`. Restore `database.kraken` to the recorded path;
remove only that database's stale `-wal` and `-shm` sidecars while all clients are
closed. Restore command artifacts to the recorded world root's `assets/.history`.
Open the restored world with the previous compatible Kraken version. Live assets
and attachment files are not changed by these migrations. An external database's
recovery metadata records its actual path separately from its manifest/assets root.

If `trashed_assets/` is present, also restore it to the recorded world root's
`assets/.trash`. The bundle verifies attachment undo's saved trash references as
well as command artifact manifests.

## Adding a migration

Append a stable numbered ID and step; never renumber or rewrite shipped steps.
Update the canonical schema for new worlds and add the version's validation.
Step functions accept the worker-owned connection and must not commit, roll back,
use `executescript()`, delete files, or construct UI. The runner alone owns locking,
backups, transactions, and ledger advancement.

Update inspection to recognize all supported starting versions, including worlds
created directly at earlier versioned schemas. Add deterministic historical
fixtures, preservation assertions, fault injection after partial mutation, and
restart tests. Regenerate `docs/reference/database-schema.md`. Run migration,
history/map, read-only, startup, packaging, lint, and typing checks before release.
