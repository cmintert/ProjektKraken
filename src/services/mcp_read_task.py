"""Feature-local queued MCP reads on the existing database worker thread."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from PySide6.QtCore import QObject, Qt, Signal, Slot

from src.core.mcp_access import McpFailure, failure
from src.services.db_service import DatabaseService
from src.services.mcp_images import decode_image
from src.services.mcp_read_service import McpReadService
from src.services.mcp_semantic import McpSemanticIndex
from src.services.mcp_semantic_preparation import SemanticPreparation

DatabaseProvider = Callable[[], DatabaseService | None]


class McpReadTask(QObject):
    """Borrow the active database only for one cancellable queued operation."""

    finished = Signal(dict)
    _image_ready = Signal(dict)
    semantic_changed = Signal(dict)

    def __init__(
        self,
        database: DatabaseProvider,
        expired: Callable[[str], bool],
    ) -> None:
        """Retain narrow providers rather than the worker or application."""
        super().__init__()
        self._database = database
        self._expired = expired
        self._service = McpReadService()
        self._images = ThreadPoolExecutor(max_workers=2, thread_name_prefix="McpImage")
        self._semantic = McpSemanticIndex()
        self.preparation = SemanticPreparation(
            database, expired, self._semantic, self._images, self
        )
        self.preparation.changed.connect(self.semantic_changed)
        self._image_ready.connect(
            self._finish_image, Qt.ConnectionType.QueuedConnection
        )
        self.destroyed.connect(
            lambda: self._images.shutdown(wait=False, cancel_futures=True)
        )
        self.destroyed.connect(lambda: self._semantic.clear())

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
            if request.get("semantic_state") == "ready" and not self._semantic.ready(
                request["generation"], self._service.revision(database)
            ):
                request["semantic_state"] = "stale"
                self._semantic.clear()
                self.semantic_changed.emit(
                    {"generation": request["generation"], "state": "stale"}
                )
            result = self._service.execute(database, request, expired)
            if request["tool"] == "semantic_search" and "semantic" in request.get(
                "scopes", []
            ):
                if self._semantic.ready(request["generation"], result["revision"]):
                    self._images.submit(self._semantic_query, request, result, expired)
                    return
            job = result.pop("_image_job", None)
            if job is not None:
                self._images.submit(self._decode, request, result, job, expired)
                return
        except McpFailure as exc:
            result = failure(exc.code)
        except Exception:
            result = failure("TIMEOUT" if expired() else "INTERNAL_ERROR")
        self.finished.emit({"request_id": identifier, "result": result})

    @Slot()
    def reset(self) -> None:
        """Release public index contents when sharing or saved facts change."""
        self._semantic.clear()
        self._service.reset()

    def _semantic_query(
        self,
        request: dict[str, Any],
        fallback: dict[str, Any],
        expired: Callable[[], bool],
    ) -> None:
        try:
            rows = self._semantic.query(request, fallback["revision"], expired)
            fallback["data"] = {
                "rows": rows,
                "effective_search": "semantic",
                "index_revision": fallback["revision"],
                "model": self._semantic.model,
                "done": True,
                "next_cursor": None,
                "score_meaning": "relevance_only",
            }
        except Exception:
            fallback["data"]["fallback_reason"] = "model_unavailable"
        try:
            self._image_ready.emit({"request": request, "result": fallback})
        except RuntimeError:
            pass

    def _decode(
        self,
        request: dict[str, Any],
        result: dict[str, Any],
        job: dict[str, Any],
        expired: Callable[[], bool],
    ) -> None:
        """Decode outside the worker; queue final authorization checks back to it."""
        try:
            decoded = decode_image(job, expired)
            result["_image"] = decoded.pop("image")
            result["data"] = {
                **decoded,
                "source_kind": job["source_kind"],
                "source_id": job["source_id"],
                "variant_id": job["variant_id"],
                "rendering": "saved_raster_without_overlays",
            }
        except McpFailure as exc:
            result = failure(exc.code)
        except Exception:
            result = failure("IMAGE_UNAVAILABLE")
        try:
            self._image_ready.emit({"request": request, "result": result})
        except RuntimeError:
            pass  # Task was deleted after session shutdown; release no late data.

    @Slot(dict)
    def _finish_image(self, response: dict[str, Any]) -> None:
        request, result = response["request"], response["result"]
        database = self._database()
        if self._expired(request["request_id"]):
            result = failure("UNAVAILABLE")
        elif (
            database is None
            or str(database.db_path) != request["database"]
            or (
                result["status"] == "OK"
                and self._service.revision(database) != result["revision"]
            )
        ):
            result = failure("WORLD_CHANGED")
        self.finished.emit({"request_id": request["request_id"], "result": result})
