"""Integration coverage for the dedicated AI analysis thread."""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any

import pytest
from PySide6.QtCore import (
    QMetaObject,
    QObject,
    Qt,
    QThread,
    QTimer,
    Signal,
)

from src.app.intelligence_analysis_manager import IntelligenceAnalysisManager
from src.core.analysis import IntelligenceReport
from src.services.worker import DatabaseWorker


class _DatabaseRequests(QObject):
    """Test-only queued requests for the database worker."""

    initialize = Signal()
    load_entities = Signal()


class _TestWindow(QObject):
    """Minimal QObject parent satisfying IntelligenceAnalysisManager."""

    def __init__(self, worker: DatabaseWorker) -> None:
        super().__init__()
        self.worker = worker
        self.current_world = SimpleNamespace(id="world-1")


class _SlowSnapshotAnalyzer:
    """Analyzer stub that keeps the AI thread busy without touching a provider."""

    def __init__(self, snapshot: dict[str, Any]) -> None:
        self._snapshot = snapshot

    def analyze(self, **_kwargs: Any) -> IntelligenceReport:
        time.sleep(0.15)
        return IntelligenceReport(
            timestamp=time.time(),
            plot_holes=[],
            relation_proposals=[],
            lore_suggestions=[],
            analysis_model="slow-test-model",
            audit_log=[],
            snapshot_timestamp=float(self._snapshot["captured_at"]),
        )


@pytest.mark.integration
def test_database_worker_and_ui_remain_available_during_ai_analysis(
    qtbot,
    tmp_path,
    monkeypatch,
):
    """A queued DB load and Qt heartbeat complete before the slow AI result."""
    monkeypatch.setattr(
        "src.services.intelligence_analysis_worker.IntelligenceAnalyzer",
        _SlowSnapshotAnalyzer,
    )

    database_thread = QThread()
    database_worker = DatabaseWorker(str(tmp_path / "background.kraken"))
    database_worker.moveToThread(database_thread)
    database_requests = _DatabaseRequests()
    database_requests.initialize.connect(
        database_worker.initialize_db,
        Qt.ConnectionType.QueuedConnection,
    )
    database_requests.load_entities.connect(
        database_worker.load_entities,
        Qt.ConnectionType.QueuedConnection,
    )
    database_thread.start()

    with qtbot.waitSignal(database_worker.initialized, timeout=3000):
        database_requests.initialize.emit()

    window = _TestWindow(database_worker)
    manager = IntelligenceAnalysisManager(window)  # type: ignore[arg-type]
    completion_order: list[str] = []
    heartbeat_count = 0

    def _record_heartbeat() -> None:
        nonlocal heartbeat_count
        heartbeat_count += 1

    timer = QTimer()
    timer.setInterval(10)
    timer.timeout.connect(_record_heartbeat)
    timer.start()
    database_worker.entities_loaded.connect(
        lambda _entities: completion_order.append("database")
    )
    manager.completed.connect(lambda _report: completion_order.append("analysis"))

    try:
        with qtbot.waitSignal(manager.completed, timeout=3000):
            assert manager.start("plot_holes") is True
            database_requests.load_entities.emit()

        assert completion_order == ["database", "analysis"]
        assert heartbeat_count >= 3
    finally:
        timer.stop()
        manager.shutdown()
        QMetaObject.invokeMethod(
            database_worker,
            "cleanup",
            Qt.ConnectionType.BlockingQueuedConnection,
        )
        database_thread.quit()
        assert database_thread.wait(3000)
