"""Worker-thread reads and impact evidence for the relation dictionary."""

import logging
from collections.abc import Callable
from sqlite3 import Connection
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from src.core.relation_vocabulary import VOCABULARY_KEY, load_document
from src.services.db_service import DatabaseService
from src.services.repositories.settings_repository import SettingsRepository

logger = logging.getLogger(__name__)


def usage(connection: Connection, key: str) -> dict[str, Any]:
    """Count stored assertions and select one stable representative for review."""
    count = connection.execute(
        "SELECT COUNT(*) FROM relations WHERE rel_type = ? COLLATE BINARY", (key,)
    ).fetchone()[0]
    sample = connection.execute(
        """
        SELECT r.id, r.source_id, r.target_id,
               COALESCE(se.name, sv.name, r.source_id) AS source_name,
               COALESCE(te.name, tv.name, r.target_id) AS target_name,
               CASE WHEN se.id IS NOT NULL THEN 'entity'
                    WHEN sv.id IS NOT NULL THEN 'event' ELSE '' END AS source_kind,
               CASE WHEN te.id IS NOT NULL THEN 'entity'
                    WHEN tv.id IS NOT NULL THEN 'event' ELSE '' END AS target_kind
        FROM relations r
        LEFT JOIN entities se ON se.id = r.source_id
        LEFT JOIN events sv ON sv.id = r.source_id
        LEFT JOIN entities te ON te.id = r.target_id
        LEFT JOIN events tv ON tv.id = r.target_id
        WHERE r.rel_type = ? COLLATE BINARY
        ORDER BY r.id LIMIT 1
        """,
        (key,),
    ).fetchone()
    return {"count": count, "sample": dict(sample) if sample is not None else None}


class RelationDictionaryReader(QObject):
    """Serve detached editor snapshots on the existing database thread."""

    finished = Signal(dict)

    def __init__(self, database: Callable[[], DatabaseService | None]) -> None:
        """Accept the database provider owned by worker composition."""
        super().__init__()
        self._database = database

    @Slot(dict)
    def load(self, request: dict[str, Any]) -> None:
        """Reply to a list or review request for its originating world."""
        result = dict(request)
        db = self._database()
        if db is None or db.db_path != request["database"]:
            result["error"] = "The active world changed."
        else:
            try:
                connection = db.require_connection()
                raw = SettingsRepository(connection).raw(VOCABULARY_KEY)
                document = load_document(raw)
                result.update(raw=raw, writable=not db.read_only)
                if "key" in request:
                    result["usage"] = usage(connection, request["key"])
                elif "preset_keys" in request:
                    result["preset_usage"] = {
                        key: usage(connection, key) for key in request["preset_keys"]
                    }
                else:
                    result["definitions"] = document["definitions"]
                    result["counts"] = dict(
                        connection.execute(
                            "SELECT rel_type, COUNT(*) FROM relations GROUP BY rel_type"
                        ).fetchall()
                    )
            except ValueError as exc:
                result["error"] = str(exc)
            except Exception:
                logger.exception("Could not read the relation dictionary")
                result["error"] = "The relation dictionary could not be loaded."
        self.finished.emit(result)
