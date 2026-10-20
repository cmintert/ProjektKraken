"""An initial data load failure must release the real startup splash."""

import sqlite3
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import QMainWindow

from src.app.coordinators.data_coordinator import DataCoordinator
from src.app.data_handler import DataHandler
from src.app.worker_manager import WorkerManager
from src.gui.splash_screen import SplashScreen
from src.gui.widgets.unified_list import UnifiedListWidget
from src.services.db_service import DatabaseService
from src.services.worker import DatabaseWorker

pytestmark = [pytest.mark.ci_fast, pytest.mark.integration, pytest.mark.real_qt_invoke]


class _Window(QMainWindow):
    startup_completed = Signal(bool)


class _Requests(QObject):
    initialize = Signal()
    events = Signal()
    entities = Signal()
    cleanup = Signal()


@pytest.mark.parametrize("failed_dataset", ["events", "entities"])
@pytest.mark.parametrize("other_ready_first", [False, True])
def test_initial_load_failure_dismisses_splash(
    qtbot, qapp, tmp_path, monkeypatch, failed_dataset, other_ready_first
):
    """Real queued failure emits False once and exposes the existing error status."""
    thread = QThread()
    failure_threads = []

    def fail_query(_database):
        failure_threads.append(QThread.currentThread())
        raise sqlite3.OperationalError("synthetic startup query failure")

    monkeypatch.setattr(DatabaseService, f"get_all_{failed_dataset}", fail_query)
    worker = DatabaseWorker(str(tmp_path / "startup-failure.kraken"))
    worker.moveToThread(thread)
    window = _Window()
    qtbot.addWidget(window)
    window.worker = worker
    window.event_editor = MagicMock()
    window.entity_editor = MagicMock()
    window.timeline = MagicMock()
    window.map_widget = MagicMock()
    window.longform_manager = MagicMock()
    window.workspace = MagicMock()
    window.workspace.panel_ids.return_value = []
    window.unified_list = UnifiedListWidget(window)
    window.setCentralWidget(window.unified_list)
    window.status_bar = window.statusBar()
    coordinator = DataCoordinator(window)
    handler = DataHandler()
    manager = WorkerManager(window)
    splash = SplashScreen()
    qtbot.addWidget(splash)
    completions = []
    window.startup_completed.connect(completions.append)
    window.startup_completed.connect(lambda _success: splash.dismiss(window))
    handler.events_ready.connect(coordinator.on_events_ready)
    handler.entities_ready.connect(coordinator.on_entities_ready)
    requests = _Requests()
    queued = Qt.ConnectionType.QueuedConnection
    requests.initialize.connect(worker.initialize_db, queued)
    requests.events.connect(worker.load_events, queued)
    requests.entities.connect(worker.load_entities, queued)
    requests.cleanup.connect(worker.cleanup, queued)
    worker.events_loaded.connect(handler.on_events_loaded, queued)
    worker.entities_loaded.connect(handler.on_entities_loaded, queued)
    worker.dataset_load_failed.connect(coordinator.on_dataset_load_failed, queued)
    worker.error_occurred.connect(manager.show_error_message, queued)
    thread.finished.connect(worker.deleteLater)
    thread.start()
    window.show()
    splash.show()

    try:
        with qtbot.waitSignal(worker.initialized, timeout=5000) as initialized:
            requests.initialize.emit()
        assert initialized.args == [True]
        other_dataset = "entities" if failed_dataset == "events" else "events"
        if other_ready_first:
            with qtbot.waitSignal(
                getattr(handler, f"{other_dataset}_ready"), timeout=3000
            ):
                getattr(requests, other_dataset).emit()
            assert completions == []
            assert splash.isVisible()
        with qtbot.waitSignal(window.startup_completed, timeout=3000) as finished:
            getattr(requests, failed_dataset).emit()
        assert finished.args == [False]
        qtbot.waitUntil(lambda: not splash.isVisible(), timeout=3000)
        assert f"Failed to load {failed_dataset}." in window.status_bar.currentMessage()
        assert failure_threads == [thread]
        assert coordinator.thread() == qapp.thread()
        assert completions == [False]
        with qtbot.waitSignal(getattr(handler, f"{other_dataset}_ready"), timeout=3000):
            getattr(requests, other_dataset).emit()
        assert completions == [False]
    finally:
        try:
            with qtbot.waitSignal(worker.cleanup_finished, timeout=3000):
                requests.cleanup.emit()
        finally:
            thread.quit()
            assert thread.wait(3000)
            coordinator.stop_graph_reload_timer()
            coordinator.stop_semantic_debounce_timer()
