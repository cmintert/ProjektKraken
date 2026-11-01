"""Feature-owned preview adapter running on the existing database thread."""

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal, Slot

from src.core.batch_metadata import MetadataOperation, normalize_targets
from src.services.batch_metadata_service import prepare_metadata
from src.services.db_service import DatabaseService

logger = logging.getLogger(__name__)
DatabaseProvider = Callable[[], DatabaseService | None]


class BatchMetadataWorker(QObject):
    """Read saved records without exposing the database to the GUI thread."""

    completed = Signal(dict)

    def __init__(self, database: DatabaseProvider) -> None:
        """Retain a provider that is invoked only on the worker thread."""
        super().__init__()
        self._database = database

    @Slot(dict)
    def preview(self, request: dict) -> None:
        """Return a correlated detached preview or a recoverable error."""
        result = {"job": request["job"], "world": request["world"]}
        try:
            db = self._database()
            if db is None:
                raise ValueError("The world database is not ready.")
            if str(db.db_path) != request["world"]:
                raise ValueError("The world changed. Open Batch Edit again.")
            operation = MetadataOperation.from_dict(request["operation"])
            targets = normalize_targets(request["targets"])
            with db.transaction():
                result["preview"] = prepare_metadata(db, targets, operation)
            result["success"] = True
        except Exception as exc:
            logger.warning("Batch preview failed: %s", type(exc).__name__)
            result.update(success=False, error=str(exc))
        self.completed.emit(result)
