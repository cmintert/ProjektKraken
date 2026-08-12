"""Lifecycle and routing for non-blocking AI intelligence analysis."""

from __future__ import annotations

import logging
import threading
import uuid
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot

from src.services.intelligence_analysis_worker import IntelligenceAnalysisWorker

if TYPE_CHECKING:
    from src.app.main_window import MainWindow

logger = logging.getLogger(__name__)


class IntelligenceAnalysisManager(QObject):
    """Coordinate snapshot capture and dedicated-thread AI analysis."""

    snapshot_requested = Signal(str, str, str, dict)
    analysis_requested = Signal(str, dict)

    started = Signal()
    partial_result = Signal(str, object)
    completed = Signal(object)
    failed = Signal(str)
    cancelling = Signal()
    cancelled = Signal()

    def __init__(self, main_window: MainWindow) -> None:
        """Create and start the dedicated intelligence analysis thread."""
        super().__init__(parent=main_window)
        self._window = main_window
        self._active_job_id: str | None = None
        self._active_world_id: str | None = None
        self._job_dispatched = False
        self._shutting_down = False
        self._cancellation_event = threading.Event()

        self._thread = QThread(self)
        self._worker = IntelligenceAnalysisWorker(self._cancellation_event)
        self._worker.moveToThread(self._thread)
        self._thread.finished.connect(self._worker.deleteLater)

        connection_type = Qt.ConnectionType.QueuedConnection
        self.snapshot_requested.connect(
            self._window.worker.prepare_intelligence_analysis,
            connection_type,
        )
        self._window.worker.intelligence_snapshot_ready.connect(
            self._on_snapshot_ready,
            connection_type,
        )
        self._window.worker.intelligence_snapshot_failed.connect(
            self._on_snapshot_failed,
            connection_type,
        )
        self.analysis_requested.connect(self._worker.run, connection_type)
        self._worker.partial_result.connect(
            self._on_partial_result,
            connection_type,
        )
        self._worker.completed.connect(self._on_completed, connection_type)
        self._worker.failed.connect(self._on_failed, connection_type)
        self._worker.cancelled.connect(self._on_cancelled, connection_type)
        self._thread.start()

    @property
    def is_running(self) -> bool:
        """Return whether an intelligence analysis job is active."""
        return self._active_job_id is not None

    def start(
        self,
        analysis_type: str = "all",
        options: dict[str, Any] | None = None,
    ) -> bool:
        """Request a click-time snapshot and start one analysis job.

        Args:
            analysis_type: Requested intelligence analysis scope.

        Returns:
            bool: ``True`` when a job was accepted.
        """
        if self._shutting_down or self.is_running:
            return False

        current_world = getattr(self._window, "current_world", None)
        world_id = str(getattr(current_world, "id", "") or "")
        job_id = str(uuid.uuid4())

        self._active_job_id = job_id
        self._active_world_id = world_id
        self._job_dispatched = False
        self._cancellation_event.clear()
        self.started.emit()
        self.snapshot_requested.emit(job_id, world_id, analysis_type, options or {})
        logger.info("AI analysis job %s requested for world %s", job_id, world_id)
        return True

    def cancel(self) -> bool:
        """Request cooperative cancellation of the active analysis job."""
        if self._active_job_id is None:
            return False

        self._cancellation_event.set()
        if not self._job_dispatched:
            self._clear_active_job()
            self.cancelled.emit()
        else:
            self.cancelling.emit()
        return True

    def shutdown(self) -> None:
        """Cancel active work and retain the QThread until it exits safely."""
        if self._shutting_down:
            return
        self._shutting_down = True
        self._cancellation_event.set()
        self._thread.quit()
        self._thread.wait()
        self._clear_active_job()

    @Slot(str, dict)
    def _on_snapshot_ready(self, job_id: str, snapshot: dict[str, Any]) -> None:
        """Dispatch an accepted snapshot to the dedicated AI thread."""
        if self._shutting_down or not self._is_current_job(job_id):
            return
        if self._cancellation_event.is_set():
            self._clear_active_job()
            self.cancelled.emit()
            return
        if str(snapshot.get("world_id", "")) != self._active_world_id:
            self._clear_active_job()
            self.cancelled.emit()
            return
        if not self._world_is_current():
            self._clear_active_job()
            self.cancelled.emit()
            return

        self._job_dispatched = True
        self.analysis_requested.emit(job_id, snapshot)

    @Slot(str, str)
    def _on_snapshot_failed(self, job_id: str, message: str) -> None:
        """Fail the current job when snapshot capture fails."""
        if not self._is_current_job(job_id):
            return
        self._clear_active_job()
        self.failed.emit(f"Could not prepare AI analysis: {message}")

    @Slot(str, str, object)
    def _on_partial_result(
        self,
        job_id: str,
        result_type: str,
        data: Any,
    ) -> None:
        """Forward a current partial result and discard stale job output."""
        if not self._is_current_job(job_id) or not self._world_is_current():
            return
        if not self._cancellation_event.is_set():
            self.partial_result.emit(result_type, data)

    @Slot(str, object)
    def _on_completed(self, job_id: str, report: Any) -> None:
        """Publish the current job's final report."""
        if not self._is_current_job(job_id):
            return
        if not self._world_is_current():
            self._clear_active_job()
            self.cancelled.emit()
            return
        self._clear_active_job()
        self.completed.emit(report)

    @Slot(str, str)
    def _on_failed(self, job_id: str, message: str) -> None:
        """Publish a current worker failure."""
        if not self._is_current_job(job_id):
            return
        self._clear_active_job()
        self.failed.emit(f"AI analysis failed: {message}")

    @Slot(str)
    def _on_cancelled(self, job_id: str) -> None:
        """Publish cancellation after the worker has stopped the job."""
        if not self._is_current_job(job_id):
            return
        self._clear_active_job()
        self.cancelled.emit()

    def _is_current_job(self, job_id: str) -> bool:
        """Return whether a signal belongs to the active job."""
        return job_id == self._active_job_id

    def _world_is_current(self) -> bool:
        """Return whether the active job still belongs to the open world."""
        current_world = getattr(self._window, "current_world", None)
        current_world_id = str(getattr(current_world, "id", "") or "")
        return current_world_id == self._active_world_id

    def _clear_active_job(self) -> None:
        """Reset active-job state after the worker is no longer using the token."""
        self._active_job_id = None
        self._active_world_id = None
        self._job_dispatched = False
        self._cancellation_event.clear()
