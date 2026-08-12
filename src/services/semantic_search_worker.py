"""Background worker for user-triggered semantic searches."""

import logging

from PySide6.QtCore import QObject, Signal, Slot

from src.services.rag_service import RAGService

logger = logging.getLogger(__name__)


class SemanticSearchWorker(QObject):
    """Run one semantic search without blocking the Qt GUI thread."""

    completed = Signal(list)
    failed = Signal(str)

    def __init__(
        self,
        db_path: str,
        query: str,
        object_type: str | None,
        top_k: int,
    ) -> None:
        """Store the immutable inputs for one background search.

        Args:
            db_path: Active world database path.
            query: User-entered semantic query.
            object_type: Optional entity/event filter.
            top_k: Maximum number of results.

        """
        super().__init__()
        self._db_path = db_path
        self._query = query
        self._object_type = object_type
        self._top_k = top_k

    @Slot()
    def run(self) -> None:
        """Execute the search and emit a serializable result or error."""
        try:
            results = RAGService(self._db_path).search(
                query=self._query,
                top_k=self._top_k,
                object_type=self._object_type,
            )
            self.completed.emit(results)
        except Exception as exc:
            logger.exception("Semantic search failed")
            self.failed.emit(str(exc))
