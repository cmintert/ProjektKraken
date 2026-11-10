"""Queued worker-thread endpoint for derived world presentation settings."""

import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from src.services.db_service import DatabaseService
from src.services.repositories.category_palette_repository import (
    CategoryPaletteRepository,
)

DatabaseProvider = Callable[[], DatabaseService | None]
logger = logging.getLogger(__name__)


class CategoryPaletteTask(QObject):
    """Borrow the worker-owned database for one identity-bound request."""

    finished = Signal(dict)

    def __init__(self, database: DatabaseProvider) -> None:
        """Retain a worker-only provider, never a GUI or worker facade."""
        super().__init__()
        self._database = database

    @Slot(dict)
    def run(self, request: dict[str, Any]) -> None:
        """Resolve saved types and return a detached mapping or safe failure."""
        result = dict(request)
        try:
            database = self._database()
            if database is None or str(database.db_path) != request["database"]:
                return
            repository = CategoryPaletteRepository(database.require_connection())
            result["assignments"] = repository.ensure_assignments(
                read_only=database.read_only
            )
        except Exception:
            logger.exception("Could not load world type color assignments")
            result["error"] = "Type color settings are unavailable."
        self.finished.emit(result)
