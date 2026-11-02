"""Persistent Qt calculation worker with worker-owned preview sessions."""

from __future__ import annotations

import json
import threading
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from src.core.event_timing.constraints import TimingCancelled
from src.services.event_timing.preview import MovementPreviewSession


class MovementPreviewWorker(QObject):
    """Receive detached JSON through queued slots; never access widgets or SQL."""

    completed = Signal(str)

    def __init__(self) -> None:
        """Separate cancellation infrastructure from worker-owned source data."""
        super().__init__()
        self._session: MovementPreviewSession | None = None
        self._error = ""
        self._cancelled: set[int] = set()
        self._lock = threading.Lock()

    def cancel_session(self, session: int) -> None:
        """Set an infrastructure token without accessing worker-owned session data."""
        with self._lock:
            self._cancelled.add(session)

    def _cancelled_session(self, session: int) -> bool:
        with self._lock:
            return session in self._cancelled

    @Slot(str)
    def initialize(self, payload: str) -> None:
        """Build the complete component baseline once per drag on this thread."""
        data = json.loads(payload)
        self._session = None
        self._error = ""
        try:
            self._session = MovementPreviewSession(
                data, lambda: self._cancelled_session(data["session"])
            )
        except TimingCancelled:
            self._error = "Movement preview cancelled."
        except Exception as exc:
            self._error = str(exc)
        with self._lock:
            self._cancelled = {key for key in self._cancelled if key >= data["session"]}

    @Slot(str)
    def calculate(self, payload: str) -> None:
        """Return one compact result even when a session is cancelled or invalid."""
        request = json.loads(payload)
        result: dict[str, Any] = {
            key: request[key]
            for key in ("session", "sequence", "generation", "world_id")
        }
        try:
            if self._session is None:
                raise ValueError(self._error or "Movement preview unavailable.")
            result.update(
                self._session.calculate(
                    request, lambda: self._cancelled_session(request["session"])
                )
            )
        except TimingCancelled:
            result["cancelled"] = True
        except Exception as exc:
            result["error"] = str(exc)
        self.completed.emit(json.dumps(result))
