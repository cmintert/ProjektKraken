"""Recovery-protected restart boundary for the ordered history format."""

import sqlite3

from src.services.migrations.schema import HISTORY_COMMAND_ID_INDEX_SQL


def reset_legacy_history(connection: sqlite3.Connection) -> bool:
    """Reset rows only; recovery bundles retain their command artifacts."""
    had_history = connection.execute("SELECT 1 FROM command_history LIMIT 1").fetchone()
    connection.execute("DELETE FROM command_history")
    connection.execute(HISTORY_COMMAND_ID_INDEX_SQL)
    connection.execute(
        "DELETE FROM system_meta WHERE key GLOB 'command_history_stacks_v2:*'"
    )
    connection.execute(
        "INSERT INTO system_meta(key,value) VALUES ('command_history_format','2') "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value"
    )
    return had_history is not None
