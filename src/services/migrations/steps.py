"""Ordered, transaction-free world migration steps."""

import json
import math
import sqlite3
from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from src.services.migrations.errors import MigrationError
from src.services.migrations.relations import install_relation_integrity
from src.services.migrations.schema import SCHEMA_SQL

MIGRATION_IDS = (
    "001_structural_compatibility",
    "002_mfjson_trajectories",
    "003_canonical_relations",
)
CURRENT_VERSION = len(MIGRATION_IDS)
STRUCTURAL_VERSION = 1
TRAJECTORY_VERSION = 2
RELATION_VERSION = 3
LEGACY_POINT_FIELDS = 3
COORDINATE_FIELDS = 2
LEGACY_FOREIGN_KEY_TABLES = ("markers", "event_tags", "entity_tags")
LEGACY_ADDITIONS = {
    "tags": {"color": "TEXT"},
    "command_history": {"timestamp": "REAL NOT NULL DEFAULT 0.0"},
    "markers": {
        "feature_type": "TEXT DEFAULT 'point'",
        "geometry": "TEXT",
        "style": "TEXT",
    },
}


def schema_statements() -> Iterator[str]:
    """Split schema SQL without implicitly committing an active transaction."""
    statement = ""
    for line in SCHEMA_SQL.splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            yield statement
            statement = ""
    if statement.strip():
        raise ValueError("Incomplete canonical schema statement")


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Return column names for a trusted schema table name."""
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')}


@lru_cache(maxsize=1)
def reference_schema() -> tuple[dict[str, set[str]], dict[str, str]]:
    """Build expected table columns and integrity objects from canonical SQL."""
    conn = sqlite3.connect(":memory:")
    try:
        for statement in schema_statements():
            conn.execute(statement)
        install_relation_integrity(conn)
        tables = {
            str(row[0]): columns(conn, str(row[0]))
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
        }
        objects = {
            str(row[0]): str(row[1])
            for row in conn.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE type IN ('index', 'trigger') AND sql IS NOT NULL"
            )
        }
        return tables, objects
    finally:
        conn.close()


def _table_contract(conn: sqlite3.Connection, table: str) -> dict[str, Any]:
    info = {
        str(row[1]): (str(row[2]).upper(), row[3], row[5])
        for row in conn.execute(f'PRAGMA table_info("{table}")')
    }
    foreign_keys = {
        tuple(row[2:]) for row in conn.execute(f'PRAGMA foreign_key_list("{table}")')
    }
    unique_keys = {
        tuple(
            str(col[2])
            for col in conn.execute(
                "SELECT * FROM pragma_index_info(?) ORDER BY seqno", (row[1],)
            )
        )
        for row in conn.execute(f'PRAGMA index_list("{table}")')
        if row[2] and row[3] in ("u", "pk")
    }
    return {"columns": info, "foreign_keys": foreign_keys, "unique_keys": unique_keys}


@lru_cache(maxsize=1)
def reference_contracts() -> dict[str, dict[str, Any]]:
    """Cache stable column, foreign-key and uniqueness contracts."""
    conn = sqlite3.connect(":memory:")
    try:
        for statement in schema_statements():
            conn.execute(statement)
        return {table: _table_contract(conn, table) for table in reference_schema()[0]}
    finally:
        conn.close()


def validate_structure(conn: sqlite3.Connection, *, legacy: bool) -> None:
    """Reject unsupported layouts rather than silently repairing arbitrary files."""
    expected, _ = reference_schema()
    actual = {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'"
        )
    }
    if legacy and not {"system_meta", "events", "entities", "relations"} <= actual:
        raise MigrationError("This is not a recognized Kraken world database.")
    unexpected = actual - expected.keys() - {"migration_history"}
    if unexpected:
        raise MigrationError(f"Unsupported world tables: {sorted(unexpected)}")
    for table, names in expected.items():
        if table not in actual:
            if legacy:
                continue
            raise MigrationError(f"Required table is missing: {table}")
        missing = names - columns(conn, table)
        if legacy:
            missing -= LEGACY_ADDITIONS.get(table, {}).keys()
        if missing:
            raise MigrationError(
                f"Unsupported {table} layout; missing columns: {sorted(missing)}"
            )
        contract = _table_contract(conn, table)
        reference = reference_contracts()[table]
        if (
            any(
                column not in names or details != reference["columns"][column]
                for column, details in contract["columns"].items()
            )
            or (
                contract["foreign_keys"] != reference["foreign_keys"]
                and not (
                    legacy
                    and table in LEGACY_FOREIGN_KEY_TABLES
                    and not contract["foreign_keys"]
                )
            )
            or contract["unique_keys"] != reference["unique_keys"]
        ):
            raise MigrationError(f"Unsupported column or constraint layout: {table}")


def legacy_foreign_key_tables(conn: sqlite3.Connection) -> list[str]:
    """Identify supported legacy tables requiring a constraint rebuild."""
    return [
        table
        for table in LEGACY_FOREIGN_KEY_TABLES
        if columns(conn, table) and not _table_contract(conn, table)["foreign_keys"]
    ]


def _restore_legacy_foreign_keys(conn: sqlite3.Connection) -> None:
    """Rebuild known legacy tables inside the caller's backed-up transaction.

    Foreign-key enforcement must be disabled before the transaction so dropping
    markers cannot cascade into existing trajectories or dated geometry.
    """
    for table in legacy_foreign_key_tables(conn):
        if conn.execute("PRAGMA foreign_keys").fetchone()[0]:
            raise MigrationError("Constraint rebuild requires migration isolation")
        for target, column, key, *_ in reference_contracts()[table]["foreign_keys"]:
            if conn.execute(
                f'SELECT 1 FROM "{table}" AS child WHERE NOT EXISTS '
                f'(SELECT 1 FROM "{target}" WHERE "{key}"=child."{column}") '
                "LIMIT 1"
            ).fetchone():
                raise MigrationError(
                    f"Legacy {table} contains orphan {column} references"
                )
        objects = conn.execute(
            "SELECT sql FROM sqlite_master WHERE tbl_name=? "
            "AND type IN ('index','trigger') AND sql IS NOT NULL",
            (table,),
        ).fetchall()
        statement = next(
            sql
            for sql in schema_statements()
            if f"CREATE TABLE IF NOT EXISTS {table} (" in sql
        )
        temporary = f"_migration_{table}"
        conn.execute(
            statement.replace(
                f"CREATE TABLE IF NOT EXISTS {table} (",
                f'CREATE TABLE "{temporary}" (',
            )
        )
        names = ", ".join(
            f'"{name}"' for name in _table_contract(conn, table)["columns"]
        )
        conn.execute(
            f'INSERT INTO "{temporary}" ({names}) SELECT {names} FROM "{table}"'
        )
        conn.execute(f'DROP TABLE "{table}"')
        conn.execute(f'ALTER TABLE "{temporary}" RENAME TO "{table}"')
        for row in objects:
            conn.execute(row[0])


def structural_compatibility(conn: sqlite3.Connection) -> None:
    """Create missing tables, add supported columns, then install indexes."""
    statements = list(schema_statements())
    for statement in statements:
        if "CREATE TABLE" in statement:
            conn.execute(statement)
    for table, additions in LEGACY_ADDITIONS.items():
        existing = columns(conn, table)
        for name, definition in additions.items():
            if name not in existing:
                conn.execute(f'ALTER TABLE "{table}" ADD COLUMN {name} {definition}')
    _restore_legacy_foreign_keys(conn)
    for statement in statements:
        if "CREATE TABLE" not in statement:
            conn.execute(statement)
    validate_structure(conn, legacy=False)


def _finite(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def trajectory_value(raw: str, record_id: str) -> tuple[dict[str, Any], bool]:
    """Validate a trajectory without guessing, sorting, or losing extensions."""
    try:
        data = json.loads(raw)
        converted = isinstance(data, list)
        if converted:
            if not data or any(
                not isinstance(point, list) or len(point) != LEGACY_POINT_FIELDS
                for point in data
            ):
                raise ValueError("Expected nonempty [time, x, y] keyframes")
            data = {
                "type": "MovingPoint",
                "coordinates": [[point[1], point[2]] for point in data],
                "datetimes": [point[0] for point in data],
            }
        if not isinstance(data, dict) or data.get("type") != "MovingPoint":
            raise ValueError("Expected MF-JSON MovingPoint")
        coords, times = data.get("coordinates"), data.get("datetimes")
        if (
            not isinstance(coords, list)
            or not isinstance(times, list)
            or not times
            or len(coords) != len(times)
            or any(not _finite(t) for t in times)
            or any(
                not isinstance(c, list)
                or len(c) != COORDINATE_FIELDS
                or not all(_finite(v) for v in c)
                for c in coords
            )
            or any(a >= b for a, b in zip(times, times[1:]))
        ):
            raise ValueError("Invalid coordinates, times, or keyframe order")
        return data, converted
    except (ValueError, TypeError, OverflowError) as exc:
        raise MigrationError(
            f"Trajectory {record_id} cannot be converted safely: {exc}",
            record_ids=[record_id],
        ) from exc


def validate_trajectories(conn: sqlite3.Connection, *, convert: bool) -> None:
    """Convert valid legacy rows or verify that all rows are already canonical."""
    for row in conn.execute(
        "SELECT id, trajectory, t_start, t_end FROM moving_features"
    ).fetchall():
        data, converted = trajectory_value(row[1], str(row[0]))
        if row[2] != data["datetimes"][0] or row[3] != data["datetimes"][-1]:
            raise MigrationError(
                "Trajectory bounds disagree with its keyframes.",
                record_ids=[str(row[0])],
            )
        if converted:
            if not convert:
                raise MigrationError(
                    "Versioned world contains a legacy trajectory.",
                    record_ids=[str(row[0])],
                )
            conn.execute(
                "UPDATE moving_features SET trajectory=? WHERE id=?",
                (json.dumps(data), row[0]),
            )


def validate_integrity(conn: sqlite3.Connection) -> None:
    """Verify persisted integrity and schema objects without repairing anything."""
    if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        raise MigrationError("Database integrity verification failed.")
    if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise MigrationError("Database contains broken foreign-key references.")
    _, expected = reference_schema()
    actual = dict(
        conn.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type IN ('index', 'trigger') AND sql IS NOT NULL"
        )
    )
    for name, sql in expected.items():
        if name not in actual or " ".join(actual[name].split()) != " ".join(
            sql.split()
        ):
            raise MigrationError(f"Missing or incompatible integrity object: {name}")
    if conn.execute(
        "SELECT id FROM relations WHERE "
        "(source_id NOT IN (SELECT id FROM entities UNION SELECT id FROM events)) "
        "OR (target_id NOT IN (SELECT id FROM entities UNION SELECT id FROM events))"
    ).fetchone():
        raise MigrationError("Database contains unresolved relation endpoints.")
    invalid = conn.execute(
        "SELECT id FROM relations WHERE rel_type='mentions' AND CASE "
        "WHEN json_valid(attributes)=0 THEN 1 "
        "WHEN json_extract(attributes,'$.is_auto_generated') IS NOT 1 THEN 1 "
        "WHEN json_extract(attributes,'$.generator') IS NOT 'wikilink' THEN 1 "
        "WHEN json_type(attributes,'$.occurrences') IS NOT 'array' THEN 1 "
        "ELSE 0 END=1"
    ).fetchall()
    if invalid:
        raise MigrationError(
            "Database contains invalid generated mentions.",
            record_ids=[str(row[0]) for row in invalid],
        )
