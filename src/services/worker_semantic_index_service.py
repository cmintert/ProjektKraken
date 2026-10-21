"""Worker-thread orchestration for semantic indexing and suggestions."""

from __future__ import annotations

import logging
import subprocess
import sys
import traceback
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from src.core.semantic_config import (
    SEMANTIC_COMPLETION_ENABLE_EMBEDDING,
    SEMANTIC_COMPLETION_PROBE_ON_WINDOWS,
    SEMANTIC_COMPLETION_PROBE_TIMEOUT_S,
)
from src.services.db_service import DatabaseService

if TYPE_CHECKING:
    from src.services.search_service import SearchService

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


class WorkerSemanticIndexService:
    """Own semantic model state and execute on the database worker thread."""

    def __init__(self, notifications: SemanticIndexNotifications) -> None:
        """Bind the worker's existing signal emitters without owning its QObject."""
        self._notifications = notifications
        self._search_service: SearchService | None = None
        self._embedding_in_progress = False
        self._pending_embeddings: set[tuple[str, str, tuple[str, ...] | None]] = set()
        self._semantic_probe_ran = False
        self._semantic_probe_ok = True

    def reset_database(self) -> None:
        """Discard state bound to the previous database connection."""
        self._search_service = None
        self._embedding_in_progress = False
        self._pending_embeddings.clear()

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

    def index_object(
        self,
        db_service: DatabaseService | None,
        object_type: str,
        object_id: str,
        excluded_attributes: list[str] | None = None,
    ) -> None:
        """Queue an embedding behind any active embedding operation."""
        if db_service is None:
            return
        if self._embedding_in_progress:
            self._pending_embeddings.add(
                (
                    object_type,
                    object_id,
                    tuple(excluded_attributes) if excluded_attributes else None,
                )
            )
            logger.debug(
                "[Worker] Embedding already in progress, queuing %s %s",
                object_type,
                object_id,
            )
            return
        self._do_index_object(db_service, object_type, object_id, excluded_attributes)

    def _do_index_object(
        self,
        db_service: DatabaseService,
        object_type: str,
        object_id: str,
        excluded_attributes: list[str] | None,
    ) -> None:
        """Index one object, then drain pending requests sequentially."""
        self._embedding_in_progress = True
        try:
            self._notifications.operation_started(
                f"Indexing {object_type} {object_id}..."
            )
            search_service = self._get_search_service(db_service)
            if search_service is None:
                raise RuntimeError("Search service unavailable")
            if object_type == "entity":
                search_service.index_entity(object_id, excluded_attributes)
            elif object_type == "event":
                search_service.index_event(object_id, excluded_attributes)
            else:
                raise ValueError(f"Unknown object type: {object_type}")
            self._notifications.operation_finished(
                f"Indexed {object_type} {object_id}."
            )
        except Exception:
            logger.error("Failed to index %s: %s", object_type, traceback.format_exc())
            self._notifications.error_occurred(
                f"Failed to index {object_type} {object_id}."
            )
        finally:
            self._embedding_in_progress = False
            self._process_pending_embeddings(db_service)

    def _process_pending_embeddings(self, db_service: DatabaseService) -> None:
        """Process the next pending embedding with its saved exclusions."""
        if not self._pending_embeddings:
            return
        object_type, object_id, exclusions = self._pending_embeddings.pop()
        excluded_attributes = list(exclusions) if exclusions else None
        logger.debug(
            "[Worker] Processing queued embedding for %s %s", object_type, object_id
        )
        self._do_index_object(db_service, object_type, object_id, excluded_attributes)

    def rebuild_search_index(
        self,
        db_service: DatabaseService | None,
        object_type: str,
        excluded_attributes: list[str] | None = None,
    ) -> None:
        """Rebuild the index with the worker's existing signal contract."""
        signals = self._notifications
        if db_service is None:
            signals.error_occurred("Database not ready for index rebuild.")
            return
        try:
            try:
                search_service = self._get_search_service(db_service)
            except ImportError as exc:
                signals.error_occurred(str(exc).split("\n")[0])
                signals.rebuild_finished(0, 0, 1)
                return
            if search_service is None:
                signals.error_occurred("Search service unavailable for rebuild.")
                signals.rebuild_finished(0, 0, 1)
                return

            types = ["entity", "event"] if object_type == "all" else [object_type]
            signals.operation_started("Rebuilding search index...")

            def report_progress(done: int, total: int) -> None:
                percentage = 100 if total == 0 else int(done * 100 / total)
                signals.rebuild_progress(done, total, percentage)

            result = search_service.rebuild_index(
                object_types=types,
                excluded_attributes=excluded_attributes or [],
                progress_callback=report_progress,
            )
            signals.rebuild_finished(result.indexed, result.unchanged, result.failed)
            signals.operation_finished(
                "Index rebuilt: "
                f"{result.indexed} indexed, "
                f"{result.unchanged} unchanged, "
                f"{result.failed} failed."
            )
        except Exception:
            logger.error("Index rebuild failed: %s", traceback.format_exc())
            signals.error_occurred("Index rebuild failed.")
            signals.rebuild_finished(0, 0, 1)

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
