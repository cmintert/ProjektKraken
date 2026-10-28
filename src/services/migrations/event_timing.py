"""Nullable temporal projections without losing Event dependents or history."""

import sqlite3

from src.services.migrations.errors import MigrationError


def migrate_event_timing(conn: sqlite3.Connection) -> None:
    """Rebuild only Events under the runner's recovery-backed writer isolation."""
    from src.services.migrations.steps import schema_statements

    if conn.execute("PRAGMA foreign_keys").fetchone()[0]:
        raise MigrationError("Event timing migration requires foreign-key isolation")
    if not any(
        row[1] == "lore_date" and row[3]
        for row in conn.execute("PRAGMA table_info(events)")
    ):
        return
    triggers = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='trigger' AND sql IS NOT NULL"
    ).fetchall()
    indexes = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='events' AND sql IS NOT NULL"
    ).fetchall()
    # SQLite validates all triggers when renaming a table. Temporarily remove
    # them, then restore their exact definitions in the same transaction.
    for name, _ in triggers:
        conn.execute('DROP TRIGGER "' + str(name).replace('"', '""') + '"')
    statement = next(
        sql
        for sql in schema_statements()
        if "CREATE TABLE IF NOT EXISTS events (" in sql
    )
    conn.execute(statement.replace("IF NOT EXISTS events (", "_migration_events ("))
    names = "id, type, name, lore_date, lore_duration, description, attributes, created_at, modified_at"
    conn.execute(f"INSERT INTO _migration_events ({names}) SELECT {names} FROM events")
    conn.execute("DROP TABLE events")
    conn.execute("ALTER TABLE _migration_events RENAME TO events")
    for (sql,) in indexes:
        conn.execute(sql)
    for _, sql in triggers:
        conn.execute(sql)
