"""Inspect, back up, and atomically upgrade persistent world databases."""

import math
import sqlite3
import time
from pathlib import Path
from typing import Any

from src.core.version import VERSION
from src.services.migrations import relations, steps
from src.services.migrations.errors import MigrationError
from src.services.migrations.recovery import create_recovery_bundle
from src.services.migrations.schema import LEDGER_SQL


def inspect_database(conn: sqlite3.Connection) -> dict[str, Any]:
    """Inspect within one read snapshot without changing persistent state."""
    owns_snapshot = not conn.in_transaction
    if owns_snapshot:
        conn.execute("BEGIN")
    try:
        return _inspect_database(conn)
    finally:
        if owns_snapshot:
            conn.rollback()


def _inspect_database(conn: sqlite3.Connection) -> dict[str, Any]:
    objects = {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
        )
    }
    if not objects:
        return {
            "detected_version": None,
            "target_version": steps.CURRENT_VERSION,
            "pending_steps": [],
            "completed_entries": [],
            "empty": True,
        }
    if "system_meta" not in objects:
        raise MigrationError("This is not a recognized Kraken world database.")
    if steps.columns(conn, "system_meta") != {"key", "value"}:
        raise MigrationError("Unsupported world metadata layout")
    raw = conn.execute(
        "SELECT value FROM system_meta WHERE key='schema_version'"
    ).fetchone()
    version = 0
    entries: list[dict[str, Any]] = []
    if raw is not None:
        if not isinstance(raw[0], str) or not raw[0].isdigit():
            raise MigrationError("Invalid authoritative schema version")
        version = int(raw[0])
        if not 1 <= version <= steps.CURRENT_VERSION:
            raise MigrationError(
                f"World schema version {version} is not supported. "
                "Use a compatible Kraken version; do not downgrade this database."
            )
        if "migration_history" not in objects:
            raise MigrationError("Versioned world is missing its migration ledger")
        rows = conn.execute(
            "SELECT version, migration_id, app_version, completed_at, origin "
            "FROM migration_history ORDER BY version"
        ).fetchall()
        entries = [
            dict(
                zip(
                    (
                        "version",
                        "migration_id",
                        "app_version",
                        "completed_at",
                        "origin",
                    ),
                    row,
                )
            )
            for row in rows
        ]
        created = False
        if rows and rows[0][1] == "created_current" and rows[0][4] == "created":
            initial_version = rows[0][0]
            created = (
                isinstance(initial_version, int)
                and 1 <= initial_version <= version
                and len(rows) == version - initial_version + 1
                and all(
                    row[0] == initial_version + offset
                    and row[1] == steps.MIGRATION_IDS[row[0] - 1]
                    and row[4] == "upgraded"
                    for offset, row in enumerate(rows[1:], 1)
                )
            )
        upgraded = len(rows) == version and all(
            row[0] == index
            and row[1] == steps.MIGRATION_IDS[index - 1]
            and row[4] == "upgraded"
            for index, row in enumerate(rows, 1)
        )
        if not (created or upgraded) or any(
            not isinstance(row[2], str)
            or not row[2]
            or not isinstance(row[3], (int, float))
            or not math.isfinite(row[3])
            for row in rows
        ):
            raise MigrationError("Schema version and migration ledger disagree")
    elif "migration_history" in objects:
        raise MigrationError("Migration ledger has no authoritative schema version")
    steps.validate_structure(conn, legacy=version == 0)
    if version >= steps.TRAJECTORY_VERSION:
        steps.validate_trajectories(conn, convert=False)
    if version == steps.CURRENT_VERSION:
        marker = conn.execute(
            "SELECT value FROM system_meta "
            "WHERE key='wikilink_relations_schema_version'"
        ).fetchone()
        if marker is None or marker[0] != "2":
            raise MigrationError("Current world has an inconsistent WikiLink marker")
        steps.validate_integrity(conn)
    return {
        "detected_version": version,
        "target_version": steps.CURRENT_VERSION,
        "pending_steps": list(steps.MIGRATION_IDS[version:]),
        "completed_entries": entries,
        "empty": False,
    }


def _stamp(conn: sqlite3.Connection, version: int, step: str, origin: str) -> None:
    conn.execute(
        "INSERT INTO migration_history VALUES (?, ?, ?, ?, ?)",
        (version, step, VERSION, time.time(), origin),
    )
    conn.execute(
        "INSERT INTO system_meta (key, value) VALUES ('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(version),),
    )


def _apply(conn: sqlite3.Connection, version: int) -> bool:
    if version == steps.STRUCTURAL_VERSION:
        steps.structural_compatibility(conn)
    elif version == steps.TRAJECTORY_VERSION:
        steps.validate_trajectories(conn, convert=True)
        steps.validate_trajectories(conn, convert=False)
    elif version == steps.RELATION_VERSION:
        marker = conn.execute(
            "SELECT value FROM system_meta "
            "WHERE key='wikilink_relations_schema_version'"
        ).fetchone()
        if marker is not None and marker[0] != "2":
            raise MigrationError("Unsupported legacy WikiLink schema marker")
        if marker is None:
            had_history = (
                conn.execute("SELECT 1 FROM command_history LIMIT 1").fetchone()
                is not None
            )
            relations.normalize_relations(conn)
            steps.validate_integrity(conn)
            return had_history
        relations.install_relation_integrity(conn)
        steps.validate_integrity(conn)
    return False


def prepare_database(
    conn: sqlite3.Connection,
    database_path: str,
    *,
    read_only: bool = False,
    world_root: Path | None = None,
) -> dict[str, Any]:
    """Initialize or upgrade before repositories can access a writable world."""
    recovery: Path | None = None
    owns_upgrade = False
    step = "inspection"
    try:
        status = inspect_database(conn)
        if read_only or status["detected_version"] == steps.CURRENT_VERSION:
            return status
        if conn.in_transaction:
            raise MigrationError("Cannot upgrade inside an existing transaction")
        step = "writer_lock"
        # BEGIN IMMEDIATE excludes competing writers but allows the read connection
        # needed by SQLite backup in both rollback-journal and WAL databases.
        conn.execute("BEGIN IMMEDIATE")
        owns_upgrade = True
        status = inspect_database(conn)  # Recheck under the writer reservation.
        if status["detected_version"] == steps.CURRENT_VERSION:
            conn.rollback()
            return status
        if status["empty"]:
            step = "create_current"
            steps.structural_compatibility(conn)
            relations.install_relation_integrity(conn)
            conn.execute(
                "INSERT INTO system_meta VALUES ('wikilink_relations_schema_version','2')"
            )
            conn.execute(LEDGER_SQL)
            _stamp(conn, steps.CURRENT_VERSION, "created_current", "created")
            archived = False
        else:
            step = "recovery_backup"
            if database_path != ":memory:":
                recovery = create_recovery_bundle(
                    conn, database_path, world_root, status
                )
            start = status["detected_version"]
            if start == 0:
                conn.execute(LEDGER_SQL)
            archived = False
            for version in range(start + 1, steps.CURRENT_VERSION + 1):
                step = steps.MIGRATION_IDS[version - 1]
                archived = _apply(conn, version) or archived
                _stamp(conn, version, step, "upgraded")
        step = "final_validation"
        final = inspect_database(conn)
        step = "commit"
        conn.commit()
        return {
            **final,
            "upgraded_from": status["detected_version"],
            "recovery_path": str(recovery) if recovery else None,
            "history_archived": archived,
        }
    except Exception as exc:
        message = str(exc)
        if owns_upgrade and conn.in_transaction:
            try:
                conn.rollback()
            except sqlite3.Error as rollback_error:
                message += f"; rollback also failed: {rollback_error}. "
                message += "Use the verified recovery bundle while Kraken is closed."
        if isinstance(exc, MigrationError):
            recovery_path = exc.recovery_path or (str(recovery) if recovery else None)
            record_ids = exc.record_ids
            failed_step = exc.step if exc.step != "inspection" else step
        else:
            recovery_path = str(recovery) if recovery else None
            record_ids = []
            failed_step = step
        raise MigrationError(
            f"World upgrade blocked at {failed_step}: {message}",
            step=failed_step,
            database_path=database_path,
            recovery_path=recovery_path,
            record_ids=record_ids,
        ) from exc
