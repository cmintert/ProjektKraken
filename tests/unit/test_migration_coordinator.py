"""Migration recovery presentation and queued worker startup."""

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QMetaObject, QObject, Qt, QThread, Slot
from PySide6.QtWidgets import QWidget

from src.app.coordinators.migration_coordinator import MigrationCoordinator
from src.services.worker import DatabaseWorker

pytestmark = pytest.mark.ci_fast


def test_failure_dialog_contains_step_records_and_recovery(qapp, monkeypatch):
    parent = QWidget()
    box = MagicMock()
    monkeypatch.setattr("src.app.coordinators.migration_coordinator.QMessageBox", box)
    coordinator = MigrationCoordinator(parent, "world.kraken")
    report = {
        "success": False,
        "database_path": "world.kraken",
        "failed_step": "002_mfjson_trajectories",
        "record_ids": ["bad-trajectory"],
        "message": "Malformed trajectory",
        "recovery_path": "recovery-folder",
    }
    coordinator.on_report(report)
    details = box.return_value.setDetailedText.call_args.args[0]
    assert "bad-trajectory" in details
    assert "002_mfjson_trajectories" in details
    assert "recovery-folder" in details and "recovery.json" in details
    assert "closed" in details
    box.return_value.exec.assert_called_once()
    parent.close()


def test_success_notice_only_for_reset_history(qapp, monkeypatch):
    parent = QWidget()
    notice = MagicMock()
    monkeypatch.setattr(
        "src.app.coordinators.migration_coordinator.QMessageBox.information", notice
    )
    coordinator = MigrationCoordinator(parent, "world.kraken")
    report = {"success": True, "database_path": "world.kraken"}
    coordinator.on_report(report)
    notice.assert_not_called()
    coordinator.on_report(
        {**report, "history_archived": True, "recovery_path": "backup"}
    )
    assert "backup" in notice.call_args.args[2]
    coordinator.on_report({"success": False, "database_path": "stale.kraken"})
    assert coordinator.last_report["success"] is True
    parent.close()


def test_queued_worker_reports_snapshot_on_main_thread(qtbot, tmp_path):
    class Receiver(QObject):
        def __init__(self):
            super().__init__()
            self.report = None
            self.thread_seen = None
            self.initialized = None

        @Slot(dict)
        def on_report(self, report):
            self.report = report
            self.thread_seen = QThread.currentThread()

        @Slot(bool)
        def on_initialized(self, initialized):
            self.initialized = initialized

    receiver = Receiver()
    thread = QThread()
    worker = DatabaseWorker(str(tmp_path / "new.kraken"))
    worker.moveToThread(thread)
    worker.migration_report.connect(
        receiver.on_report, Qt.ConnectionType.QueuedConnection
    )
    worker.initialized.connect(
        receiver.on_initialized, Qt.ConnectionType.QueuedConnection
    )
    thread.started.connect(worker.initialize_db, Qt.ConnectionType.QueuedConnection)
    thread.finished.connect(worker.deleteLater)
    thread.start()
    try:
        qtbot.waitUntil(lambda: receiver.initialized is not None, timeout=10000)
        assert receiver.initialized is True
        assert receiver.report["detected_version"] == 3
        assert receiver.thread_seen == receiver.thread()
    finally:
        QMetaObject.invokeMethod(worker, "cleanup", Qt.ConnectionType.QueuedConnection)
        thread.quit()
        assert thread.wait(10000)
