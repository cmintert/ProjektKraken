"""Exercise queued cleanup, slow workers, and confirmed thread exit."""

import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from src.app.coordinators.shutdown_coordinator import ShutdownCoordinator

pytestmark = pytest.mark.ci_fast


class CleanupWorker(QObject):
    cleanup_finished = Signal(dict)

    def __init__(self, release, result):
        super().__init__()
        self.release = release
        self.entered = threading.Event()
        self.result = result
        self.calls = 0
        self.correct_thread = False

    @Slot()
    def cleanup(self):
        self.calls += 1
        self.correct_thread = QThread.currentThread() is self.thread()
        self.entered.set()
        if self.release.wait(5):
            self.cleanup_finished.emit(self.result)


@pytest.mark.parametrize("success", [True, False])
def test_shutdown_keeps_gui_alive_and_delivers_cleanup_result(qapp, qtbot, success):
    release = threading.Event()
    result = {"success": success, "error": "" if success else "close failed"}
    thread = QThread()
    worker = CleanupWorker(release, result)
    worker.moveToThread(thread)
    thread.finished.connect(worker.deleteLater)
    owner = QObject()
    coordinator = ShutdownCoordinator(worker, thread, owner)
    finished = []
    coordinator.finished.connect(finished.append)
    waiting = []
    coordinator.waiting.connect(lambda: waiting.append(True))
    coordinator._timer.setInterval(10)
    thread.start()
    try:
        coordinator.start()
        coordinator.start()
        qtbot.waitUntil(worker.entered.is_set)
        heartbeat = []
        QTimer.singleShot(0, lambda: heartbeat.append(True))
        qtbot.waitUntil(lambda: bool(heartbeat and waiting))
        assert coordinator.pending
        assert not coordinator.complete
        assert thread.isRunning()
        assert not finished
        assert worker.calls == 1
        assert worker.correct_thread
        release.set()
        qtbot.waitUntil(lambda: bool(finished))
        assert finished == [result]
        assert coordinator.complete
        assert not coordinator.pending
        assert thread.wait(0)
        coordinator.start()
        assert finished == [result]
    finally:
        release.set()
        thread.quit()
        assert thread.wait(5000)


def test_shutdown_reports_missing_cleanup_confirmation(qapp):
    thread = QThread()
    thread.start()
    thread.quit()
    assert thread.wait(5000)
    owner = QObject()
    worker = CleanupWorker(threading.Event(), {})
    coordinator = ShutdownCoordinator(worker, thread, owner)
    finished = []
    coordinator.finished.connect(finished.append)
    coordinator.start()
    assert coordinator.complete
    assert finished[0]["success"] is False
    assert "without confirming" in finished[0]["error"]


def test_shutdown_before_worker_start_needs_no_database_cleanup(qapp):
    thread = QThread()
    owner = QObject()
    worker = CleanupWorker(threading.Event(), {})
    coordinator = ShutdownCoordinator(worker, thread, owner)
    finished = []
    coordinator.finished.connect(finished.append)
    coordinator.start()
    assert coordinator.complete
    assert finished == [{"success": True, "error": ""}]
    assert worker.calls == 0


@pytest.mark.parametrize("success", [True, False])
@pytest.mark.parametrize("controller", ["performance", "smoke"])
def test_internal_exit_waits_for_shutdown_result(
    qapp, monkeypatch, tmp_path, success, controller
):
    from src.app.package_smoke import PackageSmokeController, PackageSmokeReport
    from src.performance.probe import PerformanceProbeController

    class Signals(QObject):
        finished = Signal(dict)

    signals = Signals()
    exit_app = Mock()
    monkeypatch.setattr("PySide6.QtWidgets.QApplication.exit", exit_app)
    window = SimpleNamespace(
        shutdown_finished=signals.finished,
        close=Mock(),
        setProperty=Mock(),
        worker_manager=SimpleNamespace(package_smoke_callback=None),
    )
    instance = SimpleNamespace(
        _window=window,
        _completed=False,
        _watchdog=Mock(),
        _write_report=Mock(),
        _options=SimpleNamespace(report_path=tmp_path / "report.json"),
    )
    if controller == "performance":
        PerformanceProbeController._finish(instance, 7)
    else:
        report = PackageSmokeReport(
            success=True,
            phase="first-run",
            version="test",
            world_id="test",
            world_name="test",
            world_path="test",
            database_path="test",
            resources_checked=(),
            errors=(),
        )
        PackageSmokeController._finish(instance, report, 7)
    window.close.assert_called_once()
    window.setProperty.assert_called_once_with("krakenInternalExit", True)
    exit_app.assert_not_called()
    signals.finished.emit({"success": success})
    exit_app.assert_called_once_with(7 if success else 1)
