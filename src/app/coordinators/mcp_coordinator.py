"""Session ownership for opt-in MCP, independent of the application facade."""

from __future__ import annotations

import json
import time
from collections import deque
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot

from src.services.mcp_compact import record_ids
from src.services.mcp_read_task import DatabaseProvider, McpReadTask
from src.services.mcp_session import McpSession

if TYPE_CHECKING:
    from src.integrations.mcp.server import LocalMcpServer


class McpCoordinator(QObject):
    """Own enable/stop and stale-result protection through narrow dependencies."""

    changed = Signal(dict)
    requested = Signal(dict)
    _admitted = Signal(dict)
    _started = Signal(dict)

    def __init__(
        self,
        context: Callable[[], dict[str, str]],
        database: DatabaseProvider,
        db_thread: QThread,
        parent: QObject | None = None,
    ) -> None:
        """Bind one feature endpoint on the existing DB thread."""
        super().__init__(parent)
        self._context = context
        self._db_thread = db_thread
        self._session: McpSession | None = None
        self._server: LocalMcpServer | None = None
        self._retiring: list[LocalMcpServer] = []
        self._state = "Off"
        self._message = ""
        self._activity: deque[dict[str, Any]] = deque(maxlen=200)
        self._requests: dict[str, tuple[str, float, int]] = {}
        self._lore_epoch = 0
        self._task = McpReadTask(database, self._expired)
        self._task.moveToThread(db_thread)
        db_thread.finished.connect(self._task.deleteLater)
        self.requested.connect(self._task.run, Qt.ConnectionType.QueuedConnection)
        self._task.finished.connect(self._completed, Qt.ConnectionType.QueuedConnection)
        self._admitted.connect(self._dispatch, Qt.ConnectionType.QueuedConnection)
        self._started.connect(self._on_started, Qt.ConnectionType.QueuedConnection)
        self._poll = QTimer(self)
        self._poll.setInterval(100)
        self._poll.timeout.connect(self._check)

    def _expired(self, identifier: str) -> bool:
        session = self._session
        return session is None or session.expired(identifier)

    def snapshot(self) -> dict[str, Any]:
        """Return presentation state without connection secrets or paths."""
        world = self._context()
        return {
            "state": self._state,
            "message": self._message,
            "world_name": world.get("world_name", "No world loaded"),
            "available": bool(world.get("database")) and self._db_thread.isRunning(),
            "activity": list(self._activity),
        }

    @Slot()
    def enable(self) -> None:
        """Enable only from deliberate local UI intent, never persisted settings."""
        if self._state != "Off":
            return
        world = self._context()
        if not world.get("database") or not self._db_thread.isRunning():
            self._message = "Open a world and wait for its database to become ready."
            self._emit()
            return
        try:
            from src.integrations.mcp.discovery import SessionDiscovery
            from src.integrations.mcp.server import LocalMcpServer

            self._poll.start()
            self._message = ""
            self._state = "Starting"
            self._session = McpSession(world, self._admitted.emit)
            generation = self._session.generation
            self._server = LocalMcpServer(
                self._session,
                SessionDiscovery(),
                lambda result: self._started.emit({**result, "generation": generation}),
            )
            self._server.start()
        except Exception:
            if self._session is not None:
                self._session.revoke()
                self._session = None
            self._state = "Off"
            self._message = "Local MCP runtime could not be loaded securely."
            self._poll.stop()
            self._emit()
            return
        self._emit()

    @Slot()
    def stop(self) -> None:
        """Revoke before asynchronous socket shutdown; never wait on the GUI."""
        if self._session is not None:
            self._session.revoke()
        self._poll.start()
        self._state = "Stopping"
        if self._server is not None:
            self._server.stop()
            self._retiring.append(self._server)
            self._server = None
        self._session = None
        self._requests.clear()
        self._emit()
        self._check()

    @Slot(dict)
    def _on_started(self, result: dict[str, Any]) -> None:
        if self._session is None or result["generation"] != self._session.generation:
            return
        if "error" in result:
            self._message = (
                "Local access could not start securely. Stop sharing in other "
                "Kraken instances, then try again."
            )
            self.stop()
        else:
            self._state = "Active"
            self._emit()

    @Slot(dict)
    def _dispatch(self, request: dict[str, Any]) -> None:
        session = self._session
        if session is None or session.generation != request["generation"]:
            return
        if self._context() != session.world:
            self.stop()
            return
        if not session.expired(request["request_id"]):
            self._requests[request["request_id"]] = (
                request["tool"],
                time.monotonic(),
                self._lore_epoch,
            )
            self.requested.emit(request)

    @Slot(dict)
    def _completed(self, response: dict[str, Any]) -> None:
        session = self._session
        request = self._requests.pop(response["request_id"], None)
        if session is None or request is None:
            return
        if self._context() != session.world:
            self.stop()
            return
        result = response["result"]
        if request[2] != self._lore_epoch:
            result = {"status": "WORLD_CHANGED", "data": None}
            response["result"] = result
        if session.expired(response["request_id"]):
            result = {"status": "TIMEOUT", "data": None}
            response["result"] = result
        self._activity.append(
            {
                "tool": request[0],
                "outcome": result["status"],
                "elapsed_ms": round((time.monotonic() - request[1]) * 1000),
                "bytes": len(json.dumps(result).encode()),
                "record_ids": self._record_ids(result.get("data")),
                "time": time.time(),
            }
        )
        session.complete(response)
        self._emit()

    def invalidate(self, *_args: Any) -> None:
        """Reject queued results whose saved lore changed before delivery."""
        self._lore_epoch += 1

    @staticmethod
    def _record_ids(value: Any) -> list[str]:
        """Log factual identities, excluding authored values and missing records."""
        return record_ids(value)

    def _check(self) -> None:
        if self._session is not None and self._context() != self._session.world:
            self.stop()
            return
        self._retiring = [thread for thread in self._retiring if thread.is_alive()]
        if self._state == "Stopping" and not self._retiring:
            self._state = "Off"
            self._poll.stop()
            self._emit()

    def _emit(self) -> None:
        self.changed.emit(self.snapshot())
