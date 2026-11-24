"""Queued canonical pair reads on the existing database thread."""

import logging

from PySide6.QtCore import QObject, Signal, Slot

from src.services.graph_pair_service import graph_pair_relations
from src.services.worker import DatabaseWorker

logger = logging.getLogger(__name__)


class GraphPairReader(QObject):
    """Read draft details from the worker-owned connection."""

    ready = Signal(dict)

    def __init__(self, worker: DatabaseWorker) -> None:
        """Keep the connection's owner and request routing together."""
        super().__init__()
        self._worker = worker

    @Slot(dict)
    def load(self, request: dict) -> None:
        """Echo request identity on success and failure."""
        try:
            database = self._worker.db_service
            history = self._worker.history_service
            if database is None or (history and request["world"] != history.world_id):
                raise RuntimeError("No matching world database.")
            rows = graph_pair_relations(
                database, request["source"], request["target"], request["playhead"]
            )
        except Exception:
            logger.exception("Unable to inspect saved connections")
            self.ready.emit(
                {"request": request, "error": "Could not load saved relationships."}
            )
        else:
            self.ready.emit({"request": request, "rows": rows})
