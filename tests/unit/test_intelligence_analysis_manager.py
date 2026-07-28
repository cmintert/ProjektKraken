"""Tests for IntelligenceAnalysisManager job routing and cancellation."""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any

import pytest
from PySide6.QtCore import QObject, Signal, Slot

from src.app.intelligence_analysis_manager import IntelligenceAnalysisManager
from src.services.intelligence_analyzer import IntelligenceAnalysisCancelled


class _SnapshotWorker(QObject):
    """Small database-worker stand-in that emits serialized snapshots."""

    intelligence_snapshot_ready = Signal(str, dict)
    intelligence_snapshot_failed = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[tuple[str, str, str]] = []
        self.auto_reply = True

    @Slot(str, str, str)
    def prepare_intelligence_analysis(
        self,
        job_id: str,
        world_id: str,
        analysis_type: str,
    ) -> None:
        self.requests.append((job_id, world_id, analysis_type))
        if self.auto_reply:
            self.intelligence_snapshot_ready.emit(
                job_id,
                {
                    "world_id": world_id,
                    "analysis_type": analysis_type,
                    "captured_at": time.time(),
                    "entities": [],
                    "events": [],
                    "relations": [],
                    "calendar_config": None,
                },
            )


class _ManagerWindow(QObject):
    """Minimal QObject parent for the manager."""

    def __init__(self, worker: _SnapshotWorker) -> None:
        super().__init__()
        self.worker = worker
        self.current_world = SimpleNamespace(id="world-1")


class _CancellableAnalyzer:
    """Block until the manager's shared cancellation token is set."""

    def __init__(self, _snapshot: dict[str, Any]) -> None:
        pass

    def analyze(self, **kwargs: Any) -> None:
        is_cancelled = kwargs["is_cancelled"]
        while not is_cancelled():
            time.sleep(0.005)
        raise IntelligenceAnalysisCancelled()


class _FailingAnalyzer:
    """Raise a top-level job failure."""

    def __init__(self, _snapshot: dict[str, Any]) -> None:
        pass

    def analyze(self, **_kwargs: Any) -> None:
        raise RuntimeError("provider setup failed")


@pytest.mark.unit
def test_manager_rejects_duplicate_jobs_and_filters_stale_results(qtbot):
    worker = _SnapshotWorker()
    worker.auto_reply = False
    window = _ManagerWindow(worker)
    manager = IntelligenceAnalysisManager(window)  # type: ignore[arg-type]
    completed: list[Any] = []
    manager.completed.connect(completed.append)

    try:
        assert manager.start("all") is True
        assert manager.start("all") is False
        manager._on_completed("stale-job", object())
        assert completed == []
        assert manager.is_running is True
        assert manager.cancel() is True
        assert manager.is_running is False
    finally:
        manager.shutdown()


@pytest.mark.unit
def test_manager_cancels_a_dispatched_job(qtbot, monkeypatch):
    monkeypatch.setattr(
        "src.services.intelligence_analysis_worker.IntelligenceAnalyzer",
        _CancellableAnalyzer,
    )
    worker = _SnapshotWorker()
    window = _ManagerWindow(worker)
    manager = IntelligenceAnalysisManager(window)  # type: ignore[arg-type]

    try:
        assert manager.start("all") is True
        qtbot.waitUntil(lambda: manager._job_dispatched, timeout=1000)
        with qtbot.waitSignal(manager.cancelled, timeout=1000):
            assert manager.cancel() is True
        assert manager.is_running is False
    finally:
        manager.shutdown()


@pytest.mark.unit
def test_manager_discards_snapshot_after_world_change(qtbot):
    worker = _SnapshotWorker()
    worker.auto_reply = False
    window = _ManagerWindow(worker)
    manager = IntelligenceAnalysisManager(window)  # type: ignore[arg-type]

    try:
        assert manager.start("all") is True
        qtbot.waitUntil(lambda: bool(worker.requests), timeout=1000)
        job_id = worker.requests[0][0]
        window.current_world.id = "world-2"
        with qtbot.waitSignal(manager.cancelled, timeout=1000):
            worker.intelligence_snapshot_ready.emit(
                job_id,
                {
                    "world_id": "world-1",
                    "analysis_type": "all",
                    "captured_at": time.time(),
                    "entities": [],
                    "events": [],
                    "relations": [],
                    "calendar_config": None,
                },
            )
        assert manager.is_running is False
    finally:
        manager.shutdown()


@pytest.mark.unit
def test_manager_recovers_from_snapshot_failure(qtbot):
    worker = _SnapshotWorker()
    worker.auto_reply = False
    window = _ManagerWindow(worker)
    manager = IntelligenceAnalysisManager(window)  # type: ignore[arg-type]

    try:
        assert manager.start("all") is True
        qtbot.waitUntil(lambda: bool(worker.requests), timeout=1000)
        job_id = worker.requests[0][0]
        with qtbot.waitSignal(manager.failed, timeout=1000) as blocker:
            worker.intelligence_snapshot_failed.emit(job_id, "read failed")
        assert blocker.args == ["Could not prepare AI analysis: read failed"]
        assert manager.is_running is False
    finally:
        manager.shutdown()


@pytest.mark.unit
def test_manager_recovers_from_analysis_worker_failure(qtbot, monkeypatch):
    monkeypatch.setattr(
        "src.services.intelligence_analysis_worker.IntelligenceAnalyzer",
        _FailingAnalyzer,
    )
    worker = _SnapshotWorker()
    window = _ManagerWindow(worker)
    manager = IntelligenceAnalysisManager(window)  # type: ignore[arg-type]

    try:
        with qtbot.waitSignal(manager.failed, timeout=1000) as blocker:
            assert manager.start("all") is True
        assert blocker.args == ["AI analysis failed: provider setup failed"]
        assert manager.is_running is False
    finally:
        manager.shutdown()


@pytest.mark.unit
def test_shutdown_cancels_active_job_and_stops_thread(qtbot, monkeypatch):
    monkeypatch.setattr(
        "src.services.intelligence_analysis_worker.IntelligenceAnalyzer",
        _CancellableAnalyzer,
    )
    worker = _SnapshotWorker()
    window = _ManagerWindow(worker)
    manager = IntelligenceAnalysisManager(window)  # type: ignore[arg-type]

    assert manager.start("all") is True
    qtbot.waitUntil(lambda: manager._job_dispatched, timeout=1000)
    manager.shutdown()

    assert manager._thread.isRunning() is False
    assert manager.is_running is False
