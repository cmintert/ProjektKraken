"""Checkpoint and apply an exact, world-local relation identifier migration."""

import hashlib
import json
from pathlib import Path
from sqlite3 import Connection
from time import time
from typing import Any
from uuid import uuid4

from src.core.lifecycle import CHARACTER_TRANSITIONS
from src.core.relation_vocabulary import VOCABULARY_KEY, load_document
from src.services.database_restore_service import snapshot_database
from src.services.db_service import DatabaseService
from src.services.history_store import HistoryStore
from src.services.repositories.settings_repository import META_KEYS, SettingsRepository
from src.services.transfer_files import staged_output

MIGRATION_LOG = "relation_identifier_migrations"
_LEXICON = META_KEYS["world.lexicon"]
# Includes compatibility captions, authoring defaults and semantic consumers.
_PROTECTED = CHARACTER_TRANSITIONS | {
    "mentions",
    "related",
    "member_of",
    "involved",
    "participated_in",
    "located_at",
    "parent_of",
    "owns",
    "caused",
    "changes_state",
}
_KEY_FIELDS = {"rel_type", "relation_type", "predicate", "rel_types", "relation_types"}


def _normalized(key: str) -> str:
    return key.strip().casefold()


def is_custom_key(key: str) -> bool:
    """Allow migration only for nonblank keys outside built-in consumers."""
    return bool(key.strip()) and _normalized(key) not in _PROTECTED


def _mentions_key(value: Any, keys: set[str], *, key_field: bool = False) -> bool:
    """Detect unsupported typed settings without treating prose as a key reference."""
    if isinstance(value, dict):
        return any(
            (key_field and _normalized(field) in keys)
            or _mentions_key(child, keys, key_field=key_field or field in _KEY_FIELDS)
            for field, child in value.items()
        )
    if isinstance(value, list):
        return any(_mentions_key(child, keys, key_field=key_field) for child in value)
    return key_field and isinstance(value, str) and _normalized(value) in keys


def preview_migration(
    connection: Connection, world_id: str, old: str, new: str
) -> dict[str, Any]:
    """Read exact impact and evidence for the worker's later comparison."""
    if not old.strip() or not new.strip() or new.strip() != new or new == old:
        raise ValueError("Enter a different key without leading or trailing spaces.")
    normalized = {_normalized(old), _normalized(new)}
    if normalized & _PROTECTED:
        raise ValueError("Kraken uses one of these keys for built-in behavior.")
    repository = SettingsRepository(connection)
    vocabulary = repository.raw(VOCABULARY_KEY)
    document = load_document(vocabulary)
    definitions = {entry["key"] for entry in document["definitions"]}
    lexicon = repository.raw(_LEXICON)
    config = json.loads(lexicon) if lexicon is not None else {}
    edges = config.get("edges", {}) if isinstance(config, dict) else None
    if not isinstance(edges, dict):
        raise ValueError("The GraphView lexicon could not be reviewed.")
    occupied = (
        definitions
        | set(edges)
        | {
            row[0]
            for row in connection.execute("SELECT DISTINCT rel_type FROM relations")
        }
    )
    if any(_normalized(key) in normalized for key in occupied - {old}):
        raise ValueError(
            "A connection, definition or graph style already uses a conflicting key."
        )
    for metadata_key, raw in connection.execute("SELECT key, value FROM system_meta"):
        if metadata_key in {VOCABULARY_KEY, _LEXICON, MIGRATION_LOG}:
            continue
        if isinstance(raw, str) and raw.lstrip().startswith(("{", "[")):
            try:
                value = json.loads(raw)
            except ValueError:
                continue
            if _mentions_key(value, normalized):
                raise ValueError(
                    f"An unsupported setting references this key: {metadata_key}"
                )
    rows = connection.execute(
        "SELECT * FROM relations WHERE rel_type = ? COLLATE BINARY ORDER BY id", (old,)
    )
    digest = hashlib.sha256()
    count = 0
    for row in rows:
        digest.update(json.dumps(tuple(row), ensure_ascii=True).encode())
        count += 1
    if not count and old not in definitions:
        raise ValueError("The source key no longer has a definition or connections.")
    store = HistoryStore(connection, world_id)
    state = store.read()
    store.rows()
    return {
        "count": count,
        "definition": old in definitions,
        "graph_style": old in edges,
        "relations": digest.hexdigest(),
        "vocabulary": vocabulary,
        "lexicon": lexicon,
        "history": state,
    }


def _write_migration(
    connection: Connection, old: str, new: str, review: dict[str, Any], checkpoint: Path
) -> None:
    repository = SettingsRepository(connection)
    if review["definition"]:
        document = load_document(review["vocabulary"])
        for entry in document["definitions"]:
            if entry["key"] == old:
                entry["key"] = new
        repository.restore(VOCABULARY_KEY, json.dumps(document, ensure_ascii=True))
    if review["graph_style"]:
        lexicon = json.loads(review["lexicon"])
        lexicon["edges"][new] = lexicon["edges"].pop(old)
        repository.restore(_LEXICON, json.dumps(lexicon, ensure_ascii=True))
    connection.execute(
        "UPDATE relations SET rel_type = ? WHERE rel_type = ? COLLATE BINARY",
        (new, old),
    )
    log = json.loads(repository.raw(MIGRATION_LOG) or "[]")
    if not isinstance(log, list):
        raise ValueError("The existing migration log could not be read.")
    log.append(
        {"old": old, "new": new, "timestamp": time(), "checkpoint": checkpoint.name}
    )
    connection.execute(
        "INSERT INTO system_meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (MIGRATION_LOG, json.dumps(log, ensure_ascii=True)),
    )


def migrate_identifier(
    database: DatabaseService,
    world_id: str,
    old: str,
    new: str,
    review: dict[str, Any],
    backup_directory: Path,
) -> Path:
    """Publish a verified checkpoint before atomically applying the reviewed rename."""
    if database.read_only or not world_id:
        raise ValueError("The originating world is unavailable for migration.")
    connection = database.require_connection()
    if connection.in_transaction:
        raise ValueError("Wait for the current world operation to finish.")
    if preview_migration(connection, world_id, old, new) != review:
        raise ValueError("The impact changed. Review the migration again.")
    revision = connection.execute("PRAGMA data_version").fetchone()[0]
    target = (
        backup_directory
        / "identifier-migrations"
        / f"before-migration-{uuid4().hex}.kraken"
    )
    with staged_output(target) as staged:
        snapshot_database(Path(database.db_path), staged)
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        if (
            connection.execute("PRAGMA data_version").fetchone()[0] != revision
            or preview_migration(connection, world_id, old, new) != review
        ):
            raise ValueError(
                "The world changed during the checkpoint. Review the migration again."
            )
        _write_migration(connection, old, new, review, target)
        HistoryStore(connection, world_id).boundary()
    return target
