"""Yielding worker snapshots for explicit local semantic preparation."""

import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from PySide6.QtCore import QObject, Qt, Signal, Slot

from src.core.mcp_access import McpFailure
from src.services.db_service import DatabaseService
from src.services.mcp_facts import saved_tags
from src.services.mcp_public import public_projection
from src.services.mcp_read_service import McpReadService, read_guard
from src.services.mcp_semantic import McpSemanticIndex
from src.services.repositories.mcp_read_repository import McpReadRepository

MAX_DOCUMENTS = 50000
MAX_TEXT_BYTES = 64 * 1024 * 1024
BATCH_SIZE = 100


class SemanticPreparation(QObject):
    """Copy at most 100 records per queued step, leaving commands room to execute."""

    changed = Signal(dict)
    _next = Signal(dict)
    _ready = Signal(dict)

    def __init__(
        self,
        database: Callable[[], DatabaseService | None],
        expired: Callable[[str], bool],
        index: McpSemanticIndex,
        executor: ThreadPoolExecutor,
        parent: QObject,
    ) -> None:
        """Use the feature task's worker affinity and inference executor."""
        super().__init__(parent)
        self._database, self._expired = database, expired
        self._index, self._executor = index, executor
        self._documents: list[dict[str, Any]] = []
        self._bytes = 0
        self._active_request = ""
        self._next.connect(self.step, Qt.ConnectionType.QueuedConnection)
        self._ready.connect(self._finish, Qt.ConnectionType.QueuedConnection)

    @Slot(dict)
    def prepare(self, request: dict[str, Any]) -> None:
        """Start only from the local Prepare action; MCP cannot invoke this slot."""
        self._index.clear()
        self._documents, self._bytes = [], 0
        self._active_request = request["request_id"]
        self._next.emit({**request, "after": ""})

    @Slot(dict)
    def step(self, request: dict[str, Any]) -> None:
        """Copy one bounded batch and yield before the next worker operation."""
        try:
            if request["request_id"] != self._active_request:
                return
            if self._expired(request["request_id"]):
                self._documents = []
                return
            db = self._database()
            if db is None or str(db.db_path) != request["database"]:
                raise McpFailure("WORLD_CHANGED")
            with read_guard(
                db.require_connection(), lambda: self._expired(request["request_id"])
            ):
                revision = McpReadService.revision(db)
                if request.get("revision", revision) != revision:
                    raise McpFailure("WORLD_CHANGED")
                rows = McpReadRepository(db.require_connection()).candidates(
                    ["entity", "event"], [], request["after"], 100
                )
                for row in rows[:100]:
                    self._append(db, row)
            self.changed.emit(
                {
                    "generation": request["generation"],
                    "state": "preparing",
                    "count": len(self._documents),
                }
            )
            if len(rows) > BATCH_SIZE:
                self._next.emit(
                    {**request, "revision": revision, "after": rows[99]["ordering"]}
                )
            else:
                documents, self._documents = self._documents, []
                self._executor.submit(
                    self._embed, {**request, "revision": revision}, documents
                )
        except McpFailure as exc:
            self._documents = []
            self.changed.emit(
                {
                    "generation": request["generation"],
                    "state": "stale" if exc.code == "WORLD_CHANGED" else "unavailable",
                }
            )
        except Exception:
            self._documents = []
            self.changed.emit(
                {"generation": request["generation"], "state": "unavailable"}
            )

    def _append(self, db: DatabaseService, row: Any) -> None:
        item = (
            db.get_entity(row["id"])
            if row["kind"] == "entity"
            else db.get_event(row["id"])
        )
        if item is None:
            raise McpFailure("WORLD_CHANGED")
        public = public_projection(
            {
                "name": item.name,
                "type": item.type,
                "description": item.description,
                "attributes": item.attributes,
            }
        )
        tags = [tag["name"].strip().casefold() for tag in saved_tags(db, item)]
        text = json.dumps({**public, "tags": tags}, ensure_ascii=False)
        self._bytes += len(text.encode())
        if len(self._documents) >= MAX_DOCUMENTS or self._bytes > MAX_TEXT_BYTES:
            raise McpFailure("CONTEXT_LIMIT")
        self._documents.append(
            {
                "kind": row["kind"],
                "id": item.id,
                "name": item.name,
                "type": item.type,
                "tags": tags,
                "text": text,
                "description": item.description,
            }
        )

    def _embed(self, request: dict[str, Any], documents: list[dict[str, Any]]) -> None:
        try:
            self._index.prepare(
                request["generation"],
                request["revision"],
                request["model"],
                documents,
                lambda: self._expired(request["request_id"]),
            )
            state = "ready"
        except Exception:
            state = "unavailable"
        try:
            self._ready.emit({**request, "state": state})
        except RuntimeError:
            self._index.clear()

    @Slot(dict)
    def _finish(self, result: dict[str, Any]) -> None:
        db = self._database()
        if self._expired(result["request_id"]):
            return
        if db is None or McpReadService.revision(db) != result["revision"]:
            self._index.clear()
            result["state"] = "stale"
        self.changed.emit(
            {"generation": result["generation"], "state": result["state"]}
        )
