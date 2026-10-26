"""Feature-local queued reads on the existing database thread."""

import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from src.services.db_service import DatabaseService
from src.services.entity_connection_browse_service import (
    EntityConnectionBrowseService,
    StaleConnectionCursor,
)

logger = logging.getLogger(__name__)


class EntityConnectionBrowseTask(QObject):
    """Borrow the database only inside a queued slot on its owning thread."""

    finished = Signal(dict)

    def __init__(self, database: Callable[[], DatabaseService | None]) -> None:
        """Retain a narrow provider, never a GUI or database snapshot."""
        super().__init__()
        self._database = database

    @Slot(dict)
    def run(self, request: dict[str, Any]) -> None:
        """Finish one batch before commands and subsequent reads are dispatched."""
        response = {"request_id": request["request_id"], "kind": request["kind"]}
        try:
            database = self._database()
            if database is None:
                raise RuntimeError("Database unavailable")
            service = EntityConnectionBrowseService(database)
            if request["kind"] == "check":
                response["stale"] = service.revision() != request["revision"]
            else:
                response.update(service.step(request))
        except StaleConnectionCursor:
            response["stale"] = True
        except Exception:
            logger.exception("Direct connection browsing failed")
            response["error"] = True
        self.finished.emit(response)
