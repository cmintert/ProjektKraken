"""Recovery-protected restart boundary for the ordered history format."""

import sqlite3

from src.services.migrations.schema import (
    HISTORY_COMMAND_ID_INDEX_SQL,
    LEGACY_HISTORY_PAYLOAD_INDEX_SQL,
)


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


def install_portable_history_index(connection: sqlite3.Connection) -> None:
    """Replace the v7 JSON5 index without rewriting any command payloads."""
    connection.execute("DROP INDEX IF EXISTS idx_ch_world_identity")
    connection.execute(HISTORY_COMMAND_ID_INDEX_SQL)
    connection.execute(LEGACY_HISTORY_PAYLOAD_INDEX_SQL)
