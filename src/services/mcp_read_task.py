"""Feature-local queued MCP reads on the existing database worker thread."""

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from src.core.mcp_access import McpFailure, failure
from src.services.db_service import DatabaseService
from src.services.mcp_read_service import McpReadService


class McpReadTask(QObject):
    """Borrow the active database only for one cancellable queued operation."""

    finished = Signal(dict)

    def __init__(
        self,
        database: Callable[[], DatabaseService | None],
        expired: Callable[[str], bool],
    ) -> None:
        """Retain narrow providers rather than the worker or application."""
        super().__init__()
        self._database = database
        self._expired = expired
        self._service = McpReadService()

    @Slot(dict)
    def run(self, request: dict[str, Any]) -> None:
        """Read a detached factual response without emitting sensitive errors."""
        identifier = request["request_id"]

        def expired() -> bool:
            return self._expired(identifier)

        try:
            database = self._database()
            if expired():
                raise McpFailure("UNAVAILABLE")
            if database is None or str(database.db_path) != request["database"]:
                raise McpFailure("WORLD_CHANGED")
            result = self._service.execute(database, request, expired)
        except McpFailure as exc:
            result = failure(exc.code)
        except Exception:
            result = failure("TIMEOUT" if expired() else "INTERNAL_ERROR")
        self.finished.emit({"request_id": identifier, "result": result})
