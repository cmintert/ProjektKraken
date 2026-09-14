"""Bounded snapshots and reversible row changes for lore transfers."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

TABLE_KEYS = {
    "entities": ("id",),
    "events": ("id",),
    "tags": ("id",),
    "relations": ("id",),
    "entity_tags": ("entity_id", "tag_id"),
    "event_tags": ("event_id", "tag_id"),
}


def snapshot(connection: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    """Read the complete bounded lore state in deterministic order."""
    result = {}
    for table, keys in TABLE_KEYS.items():
        cursor = connection.execute(f"SELECT * FROM {table} ORDER BY {', '.join(keys)}")
        names = [item[0] for item in cursor.description]
        result[table] = [dict(zip(names, row, strict=True)) for row in cursor]
    return result


def revision(state: dict[str, Any]) -> str:
    """Identify the exact state reviewed by the user."""
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()


def changes(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    """Calculate only affected rows, retaining both sides for persistent undo."""
    result = []
    for table, keys in TABLE_KEYS.items():
        old = {tuple(row[key] for key in keys): row for row in before[table]}
        new = {tuple(row[key] for key in keys): row for row in after[table]}
        for key in sorted(old.keys() | new.keys()):
            if old.get(key) != new.get(key):
                result.append(
                    {"table": table, "before": old.get(key), "after": new.get(key)}
                )
    return result


def apply_changes(
    connection: sqlite3.Connection,
    delta: list[dict[str, Any]],
    *,
    reverse: bool = False,
) -> None:
    """Apply validated deltas without REPLACE cascades; caller owns the transaction."""
    old_side, new_side = ("after", "before") if reverse else ("before", "after")
    # Check every precondition before the first write, including undo/redo.
    for item in delta:
        table = item["table"]
        if table not in TABLE_KEYS:
            raise ValueError("Unsupported transfer table")
        row = item[old_side] or item[new_side]
        keys = TABLE_KEYS[table]
        where = " AND ".join(f"{key} = ?" for key in keys)
        cursor = connection.execute(
            f"SELECT * FROM {table} WHERE {where}", tuple(row[key] for key in keys)
        )
        found = cursor.fetchone()
        current = (
            dict(zip((c[0] for c in cursor.description), found, strict=True))
            if found is not None
            else None
        )
        if current != item[old_side]:
            raise ValueError("World data changed. Review the import again.")
    # Delete dependents first; insert parents first.
    order = list(TABLE_KEYS)
    for table in reversed(order):
        for item in delta:
            if item["table"] == table and item[new_side] is None:
                keys = TABLE_KEYS[table]
                where = " AND ".join(f"{key} = ?" for key in keys)
                connection.execute(
                    f"DELETE FROM {table} WHERE {where}",
                    tuple(item[old_side][key] for key in keys),
                )
    for table in order:
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        for item in delta:
            row = item[new_side]
            if item["table"] != table or row is None:
                continue
            if set(row) != columns:
                raise ValueError("Transfer schema no longer matches this database.")
            fields = list(row)
            keys = TABLE_KEYS[table]
            updates = ", ".join(
                f"{field}=excluded.{field}" for field in fields if field not in keys
            )
            sql = (
                f"INSERT INTO {table} ({', '.join(fields)}) VALUES "
                f"({', '.join('?' for _ in fields)}) ON CONFLICT "
                f"({', '.join(keys)}) DO UPDATE SET {updates}"
            )
            connection.execute(sql, tuple(row[field] for field in fields))


def lore_data(state: dict[str, Any]) -> dict[str, Any]:
    """Convert storage rows to the exchange shape."""
    result: dict[str, Any] = {}
    for kind in ("entities", "events", "relations"):
        result[kind] = []
        for stored in state[kind]:
            row = dict(stored)
            row["attributes"] = json.loads(row.get("attributes") or "{}")
            result[kind].append(row)
    return result
