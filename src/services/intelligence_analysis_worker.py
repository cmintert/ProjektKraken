"""Dedicated worker for database-independent AI intelligence analysis."""

from __future__ import annotations

import logging
import threading
import traceback
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from src.services.intelligence_analyzer import (
    IntelligenceAnalysisCancelled,
    IntelligenceAnalyzer,
)

logger = logging.getLogger(__name__)


class IntelligenceAnalysisWorker(QObject):
    """Run intelligence snapshots on a dedicated Qt worker thread.

    The worker never receives a database connection. Cancellation is driven by
    a thread-safe event because a queued Qt cancellation slot cannot execute
    while :meth:`run` occupies this object's event thread.
    """

    partial_result = Signal(str, str, object)
    completed = Signal(str, object)
    failed = Signal(str, str)
    cancelled = Signal(str)

    def __init__(self, cancellation_event: threading.Event) -> None:
        """Initialize the worker with its shared cancellation token."""
        super().__init__()
        self._cancellation_event = cancellation_event

    @Slot(str, dict)
    def run(self, job_id: str, snapshot: dict[str, Any]) -> None:
        """Analyze one serialized world snapshot.

        Args:
            job_id: Stable identifier used to reject stale results.
            snapshot: Database-independent click-time world snapshot.
        """
        if self._cancellation_event.is_set():
            self.cancelled.emit(job_id)
            return

        try:

            def _on_partial(result_type: str, data: Any) -> None:
                if not self._cancellation_event.is_set():
                    self.partial_result.emit(job_id, result_type, data)

            analyzer = IntelligenceAnalyzer(snapshot)
            estimate_coverage = getattr(analyzer, "estimate_coverage", None)
            if callable(estimate_coverage):
                self.partial_result.emit(job_id, "estimate", estimate_coverage())
            report = analyzer.analyze(
                on_partial=_on_partial,
                is_cancelled=self._cancellation_event.is_set,
            )
            if self._cancellation_event.is_set():
                self.cancelled.emit(job_id)
            else:
                self.completed.emit(job_id, report)
        except IntelligenceAnalysisCancelled:
            self.cancelled.emit(job_id)
        except Exception as exc:
            logger.error(
                "Intelligence analysis job %s failed: %s\n%s",
                job_id,
                exc,
                traceback.format_exc(),
            )
            self.failed.emit(job_id, str(exc))
