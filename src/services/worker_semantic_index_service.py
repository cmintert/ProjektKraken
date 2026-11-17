"""Worker-thread orchestration for semantic indexing and suggestions."""

from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from src.core.semantic_config import (
    SEMANTIC_COMPLETION_ENABLE_EMBEDDING,
    SEMANTIC_COMPLETION_PROBE_ON_WINDOWS,
    SEMANTIC_COMPLETION_PROBE_TIMEOUT_S,
)
from src.services.db_service import DatabaseService

if TYPE_CHECKING:
    from src.services.search_service import SearchService
    from src.services.semantic_index_task import SemanticIndexTask

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SemanticIndexNotifications:
    """Existing worker signal emitters used by semantic operations."""

    operation_started: Callable[[str], None]
    operation_finished: Callable[[str], None]
    error_occurred: Callable[[str], None]
    rebuild_progress: Callable[[int, int, int], None]
    rebuild_finished: Callable[[int, int, int], None]
    suggestions_ready: Callable[[str, list[str]], None]
    job_state: Callable[[dict[str, Any]], None] = lambda _snapshot: None


class WorkerSemanticIndexService:
    """Own semantic model state and execute on the database worker thread."""

    def __init__(self, notifications: SemanticIndexNotifications) -> None:
        """Bind the worker's existing signal emitters without owning its QObject."""
        self._notifications = notifications
        self._search_service: SearchService | None = None
        self._task: SemanticIndexTask | None = None
        self._semantic_probe_ran = False
        self._semantic_probe_ok = True

    def reset_database(self) -> None:
        """Discard state bound to the previous database connection."""
        self._search_service = None
        if self._task is not None:
            self._task.close()
            self._task.deleteLater()
            self._task = None

    def _get_search_service(
        self, db_service: DatabaseService | None
    ) -> SearchService | None:
        """Create one search service per database connection, on the worker thread."""
        if self._search_service is not None:
            return self._search_service
        if db_service is None:
            return None

        from src.services.search_service import create_search_service

        conn = db_service.get_connection()
        if conn is None:
            return None
        self._search_service = create_search_service(conn)
        return self._search_service

    def _index_task(self, database: DatabaseService) -> SemanticIndexTask:
        """Create the scheduler lazily with the database worker's affinity."""
        from src.services.semantic_index_task import SemanticIndexTask

        if self._task is None:
            self._task = SemanticIndexTask(database, self._notifications)
        return self._task

    def index_object(
        self,
        db_service: DatabaseService | None,
        object_type: str,
        object_id: str | list[str],
        excluded_attributes: list[str] | None = None,
    ) -> None:
        """Queue detached identities and return before model initialization."""
        if db_service is None:
            return
        identifiers = [object_id] if isinstance(object_id, str) else object_id
        self._index_task(db_service).enqueue(
            [(object_type, identifier) for identifier in identifiers],
            excluded_attributes or [],
        )

    def rebuild_search_index(
        self,
        db_service: DatabaseService | None,
        object_type: str,
        excluded_attributes: list[str] | None = None,
    ) -> None:
        """Queue a yielding rebuild with the existing completion signals."""
        if db_service is None:
            self._notifications.error_occurred("Database not ready for index rebuild.")
            return
        self._index_task(db_service).rebuild(object_type, excluded_attributes or [])

    def query_semantic_suggestions(
        self,
        db_service: DatabaseService | None,
        prefix: str,
        top_k: int = 5,
        min_score: float = 0.85,
    ) -> None:
        """Emit matching names when semantic completion is available."""
        if not SEMANTIC_COMPLETION_ENABLE_EMBEDDING or db_service is None:
            return
        if not self._ensure_semantic_probe():
            return
        try:
            search_service = self._get_search_service(db_service)
            if search_service is None:
                return
            results = search_service.query(text=prefix, top_k=top_k)
            names = [
                result["name"]
                for result in results
                if result["score"] >= min_score and result["name"]
            ]
            self._notifications.suggestions_ready(prefix, names)
        except Exception:
            logger.debug("Semantic suggestion query failed", exc_info=True)

    def _ensure_semantic_probe(self) -> bool:
        """Probe Windows native model safety once per worker lifetime."""
        if self._semantic_probe_ran:
            return self._semantic_probe_ok
        self._semantic_probe_ran = True
        if sys.platform != "win32" or not SEMANTIC_COMPLETION_PROBE_ON_WINDOWS:
            self._semantic_probe_ok = True
            return True

        model_name = "all-MiniLM-L6-v2"
        probe_code = (
            "import os;"
            "os.environ.setdefault('TOKENIZERS_PARALLELISM','false');"
            "os.environ.setdefault('OMP_NUM_THREADS','1');"
            "from sentence_transformers import SentenceTransformer;"
            f"m=SentenceTransformer('{model_name}', device='cpu');"
            "m.encode(['probe'], show_progress_bar=False)"
        )
        try:
            result = subprocess.run(
                [sys.executable, "-c", probe_code],
                check=False,
                capture_output=True,
                text=True,
                timeout=SEMANTIC_COMPLETION_PROBE_TIMEOUT_S,
            )
        except Exception:
            logger.warning("Semantic embedding probe failed", exc_info=True)
            self._semantic_probe_ok = False
            return False
        if result.returncode != 0:
            logger.warning(
                "Semantic embedding probe disabled feature on this run "
                "(code=%s, stderr=%s)",
                result.returncode,
                (result.stderr or "").strip()[:300],
            )
            self._semantic_probe_ok = False
            return False
        self._semantic_probe_ok = True
        logger.info("Semantic embedding probe passed")
        return True
