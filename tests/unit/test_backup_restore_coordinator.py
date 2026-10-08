"""Queued restore ordering and cancellation at the application boundary."""

import sqlite3
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import QWidget

from src.app.coordinators.backup_coordinator import BackupCoordinator
from src.core.backup_config import BackupConfig
from src.services.backup_service import BackupService

pytestmark = pytest.mark.ci_fast


class ClosingWorker(QObject):
    cleanup_finished = Signal(dict)
    work_requested = Signal()

    def __init__(self, order):
        super().__init__()
        self.order = order
        self.result = {"success": True, "error": ""}
        self.work_requested.connect(self.write, Qt.ConnectionType.QueuedConnection)

    @Slot()
    def write(self):
        self.order.append("queued write")

    @Slot()
    def cleanup(self):
        self.order.append("closed")
        self.cleanup_finished.emit(self.result)


@pytest.fixture
def restore_window(qapp, tmp_path, monkeypatch):
    window = QWidget()
    backups = tmp_path / "backups"
    backups.mkdir()
    for name, value in [("current.kraken", "current"), ("backups/old.kraken", "old")]:
        with closing(sqlite3.connect(tmp_path / name)) as db:
            db.execute("CREATE TABLE trust (value TEXT)")
            db.execute("INSERT INTO trust VALUES (?)", (value,))
            db.commit()
    window.db_path = str(tmp_path / "current.kraken")
    window.backup_service = BackupService(BackupConfig(backup_dir=backups))
    window.status_bar = Mock()
    window.map_handler = Mock()
    window.map_handler.has_pending_raster_strokes.return_value = False
    window.event_editor = Mock()
    window.entity_editor = Mock()
    window.check_unsaved_changes = Mock(return_value=True)
    window.app_coordinator = SimpleNamespace(
        trajectory_edit=SimpleNamespace(is_active=False),
        feature_geometry=SimpleNamespace(is_active=False),
        map_edits=SimpleNamespace(is_waiting=False, request_transition=Mock()),
    )
    window.command_coordinator = SimpleNamespace(mutations_suspended=False)
    window.longform_manager = Mock()
    window.data_coordinator = Mock()
    window.ai_search_manager = Mock()
    window.intelligence_analysis_manager = Mock()
    order = []
    window.worker = ClosingWorker(order)
    window.worker_thread = QThread()
    window.worker.moveToThread(window.worker_thread)
    window.worker_thread.finished.connect(window.worker.deleteLater)
    window.worker_thread.start()
    window.close = Mock(side_effect=lambda: order.append("window closed"))
    monkeypatch.setattr(
        "src.app.coordinators.backup_coordinator.QMessageBox.information", Mock()
    )
    monkeypatch.setattr(
        "src.app.coordinators.backup_coordinator.QMessageBox.critical", Mock()
    )
    coordinator = BackupCoordinator(window)
    yield window, coordinator, tmp_path / "backups/old.kraken", order
    if coordinator._restore_task is not None:
        coordinator._restore_task.wait(5000)
    window.worker_thread.quit()
    assert window.worker_thread.wait(5000)
    window.deleteLater()


def test_restore_waits_for_worker_shutdown(restore_window, qtbot, monkeypatch):
    from src.services.database_restore_service import DatabaseRestoreService

    window, coordinator, backup, order = restore_window
    original = DatabaseRestoreService.restore

    def restore(self, *args):
        assert order == ["queued write", "closed"]
        assert not window.worker_thread.isRunning()
        assert window.command_coordinator.mutations_suspended
        order.append("replace")
        return original(self, *args)

    monkeypatch.setattr(DatabaseRestoreService, "restore", restore)
    window.worker.work_requested.emit()
    coordinator._execute_restore(str(backup))
    qtbot.waitUntil(lambda: window.close.called, timeout=5000)
    assert order == ["queued write", "closed", "replace", "window closed"]
    with closing(sqlite3.connect(window.db_path)) as db:
        assert db.execute("SELECT value FROM trust").fetchone() == ("old",)


@pytest.mark.parametrize("blocked", ["draft", "raster", "trajectory", "geometry"])
def test_unfinished_work_does_not_shutdown(restore_window, blocked):
    window, coordinator, backup, order = restore_window
    if blocked == "draft":
        window.check_unsaved_changes.return_value = False
    elif blocked == "raster":
        window.map_handler.has_pending_raster_strokes.return_value = True
    else:
        getattr(
            window.app_coordinator,
            "trajectory_edit" if blocked == "trajectory" else "feature_geometry",
        ).is_active = True
    coordinator._execute_restore(str(backup))
    assert order == []
    assert window.worker_thread.isRunning()
    assert not window.command_coordinator.mutations_suspended
    assert window.isEnabled()


def test_shutdown_failure_never_replaces_world(restore_window, qtbot):
    window, coordinator, backup, order = restore_window
    window.worker.result = {"success": False, "error": "injected close failure"}
    original = open(window.db_path, "rb").read()
    coordinator._execute_restore(str(backup))
    qtbot.waitUntil(lambda: window.close.called)
    assert order == ["closed", "window closed"]
    assert coordinator._restore_task is None
    assert coordinator.restart_required
    assert open(window.db_path, "rb").read() == original


@pytest.mark.parametrize("invalid", ["corrupt", "unauthorized"])
def test_invalid_backup_keeps_session_active(restore_window, invalid, tmp_path):
    window, coordinator, backup, order = restore_window
    if invalid == "corrupt":
        backup.write_bytes(b"corrupt")
    else:
        outside = tmp_path / "outside.kraken"
        outside.write_bytes(backup.read_bytes())
        backup = outside
    coordinator._execute_restore(str(backup))
    assert order == []
    assert window.worker_thread.isRunning()
    assert window.isEnabled()


def test_restore_guard_retains_continuation_without_stopping_worker(restore_window):
    window, coordinator, backup, order = restore_window
    window.app_coordinator.trajectory_edit.is_active = True
    coordinator._execute_restore(str(backup))
    guard = window.app_coordinator.map_edits
    guard.request_transition.assert_called_once()
    reason, continuation = guard.request_transition.call_args.args
    assert reason == "restore the backup" and order == []
    assert callable(continuation)
    assert window.worker_thread.isRunning()
