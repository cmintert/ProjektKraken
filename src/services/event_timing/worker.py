"""Feature-owned DB adapter and a pure cancellable computation thread."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot

from src.core.event_timing.constraints import TimingCancelled
from src.services.db_service import DatabaseService
from src.services.event_timing.planning import (
    TimingChangePlan,
    TimingChangeRequest,
    prepare_change,
)
from src.services.event_timing.store import capture, discard, register

DatabaseProvider = Callable[[], DatabaseService | None]


class EventTimingDatabaseAdapter(QObject):
    """Receive feature requests on the existing DB-owning thread."""

    completed = Signal(str)

    def __init__(self, database: Callable[[], DatabaseService | None]) -> None:
        """Keep a provider that is invoked exclusively on the owning thread."""
        super().__init__()
        self._database = database
        self._cancelled: set[str] = set()
        self._cancel_lock = threading.Lock()

    def cancel_job(self, job: str) -> None:
        """Thread-safe cancellation token only; this never accesses the database."""
        with self._cancel_lock:
            self._cancelled.add(job)

    def _check_cancelled(self, job: str) -> None:
        with self._cancel_lock:
            if job in self._cancelled:
                raise InterruptedError("Timing edit cancelled.")

    @Slot(str)
    def run(self, payload: str) -> None:
        """Capture or register; neither operation performs constraint solving."""
        request = json.loads(payload)
        result: dict[str, Any] = {
            "job": request["job"],
            "operation": request["operation"],
        }
        try:
            self._check_cancelled(request["job"])
            db = self._database()
            if db is None or db.db_path != request["world_id"]:
                raise ValueError(
                    "The active world changed. Start the timing edit again."
                )
            if request["operation"] == "capture":
                result["snapshot"] = capture(db)
            elif request["operation"] == "register":
                plan = TimingChangePlan.from_dict(request["plan"])
                result["plan_id"] = register(db, plan)
                result["fingerprint"] = plan.fingerprint
                try:
                    self._check_cancelled(request["job"])
                except InterruptedError:
                    discard(db, plan.identity)
                    raise
            else:
                raise ValueError("Unknown timing operation")
            result["success"] = True
        except (ValueError, TypeError, KeyError, InterruptedError) as exc:
            result.update(success=False, error=str(exc))
        self.completed.emit(json.dumps(result))


class EventTimingCalculation(QThread):
    """Only detached JSON enters or leaves this computation thread."""

    completed = Signal(str)

    def __init__(
        self,
        job: str,
        snapshot: dict[str, Any],
        request: TimingChangeRequest,
        parent: QObject | None = None,
    ) -> None:
        """Own immutable input bytes and a thread-safe cancellation token."""
        super().__init__(parent)
        self.job = job
        self._snapshot = json.dumps(snapshot)
        self._request = json.dumps(request.to_dict())
        self.cancelled = threading.Event()

    def run(self) -> None:
        """Continue until proven, cancelled, or a reported computation failure."""
        result: dict[str, Any] = {"job": self.job}
        try:
            plan = prepare_change(
                json.loads(self._snapshot),
                TimingChangeRequest.from_dict(json.loads(self._request)),
                self.cancelled.is_set,
            )
            result.update(success=True, plan=plan.to_dict())
        except TimingCancelled:
            result.update(success=False, cancelled=True)
        except Exception as exc:
            result.update(success=False, error=f"Timing calculation failed: {exc}")
        self.completed.emit(json.dumps(result))
