"""Real queued load failures preserve existing displayed world data."""

import sqlite3
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot

from src.app.coordinators.data_coordinator import DataCoordinator
from src.app.data_handler import DataHandler
from src.core.events import Event
from src.gui.widgets.unified_list import UnifiedListWidget
from src.services.db_service import DatabaseService
from src.services.worker import DatabaseWorker

pytestmark = [pytest.mark.ci_fast, pytest.mark.integration, pytest.mark.real_qt_invoke]


class _LoadWorker(DatabaseWorker):
    phase_finished = Signal(str)

    def __init__(self, path):
        super().__init__(path)
        self.fail_load = False

    @Slot(str)
    def run_phase(self, phase):
        assert self.db_service is not None
        if phase == "seed":
            self.db_service.insert_event(
                Event(id="existing-event", name="Existing event", lore_date=1.0)
            )
        elif phase == "empty":
            self.db_service.delete_event("existing-event")
        self.fail_load = phase == "failure"
        self.load_events()
        self.phase_finished.emit(phase)


class _Requests(QObject):
    initialize = Signal()
    phase = Signal(str)
    cleanup = Signal()


class _GuiObserver(QObject):
    settled = Signal(str)

    def __init__(self):
        super().__init__()
        self.errors = []
        self.receiving_threads = []

    @Slot(str)
    def on_error(self, message):
        self.receiving_threads.append(QThread.currentThread())
        self.errors.append(message)

    @Slot(list)
    def on_loaded(self, _events):
        self.receiving_threads.append(QThread.currentThread())

    @Slot(str)
    def on_settled(self, phase):
        self.receiving_threads.append(QThread.currentThread())
        self.settled.emit(phase)


def test_failed_event_load_preserves_display_until_successful_empty_result(
    qapp, qtbot, tmp_path, monkeypatch
):
    """DB work stays off the GUI thread; errors never become empty snapshots."""
    thread = QThread()
    worker = _LoadWorker(str(tmp_path / "load-delivery.kraken"))
    database_calls = []

    def track(name):
        original = getattr(DatabaseService, name)

        def tracked(database, *args, **kwargs):
            current = QThread.currentThread()
            database_calls.append((name, current))
            assert current == thread
            if name == "get_all_events" and worker.fail_load:
                raise sqlite3.OperationalError("synthetic private failure")
            return original(database, *args, **kwargs)

        monkeypatch.setattr(DatabaseService, name, tracked)

    for method in (
        "connect",
        "ensure_fresh_view",
        "get_all_events",
        "insert_event",
        "delete_event",
        "close",
    ):
        track(method)

    window = QObject()
    window.worker = worker
    window.event_editor = MagicMock()
    window.entity_editor = MagicMock()
    window.unified_list = UnifiedListWidget()
    qtbot.addWidget(window.unified_list)
    window.timeline = MagicMock()
    window.map_widget = MagicMock()
    window.longform_manager = MagicMock()
    window.workspace = MagicMock()
    window.workspace.panel_ids.return_value = []
    coordinator = DataCoordinator(window)
    handler = DataHandler()
    observer = _GuiObserver()
    assert handler.thread() == coordinator.thread() == qapp.thread()
    handler.events_ready.connect(coordinator.on_events_ready)
    queued = Qt.ConnectionType.QueuedConnection
    worker.moveToThread(thread)
    requests = _Requests()
    requests.initialize.connect(worker.initialize_db, queued)
    requests.phase.connect(worker.run_phase, queued)
    requests.cleanup.connect(worker.cleanup, queued)
    worker.events_loaded.connect(handler.on_events_loaded, queued)
    worker.events_loaded.connect(observer.on_loaded, queued)
    worker.error_occurred.connect(observer.on_error, queued)
    worker.phase_finished.connect(observer.on_settled, queued)
    thread.finished.connect(worker.deleteLater)
    thread.start()

    try:
        with qtbot.waitSignal(worker.initialized, timeout=5000) as initialized:
            requests.initialize.emit()
        assert initialized.args == [True]
        with qtbot.waitSignal(observer.settled, timeout=3000):
            requests.phase.emit("seed")
        assert [event.id for event in handler._cached_events] == ["existing-event"]
        assert [event.id for event in coordinator.cached_events] == ["existing-event"]
        model = window.unified_list.list_widget.model()
        assert model.rowCount() == 1
        displayed = model.index(0, 0).data()
        assert "Existing event" in displayed
        window.timeline.reset_mock()

        with qtbot.waitSignal(observer.settled, timeout=3000):
            requests.phase.emit("failure")
        assert observer.errors == ["Failed to load events."]
        assert [event.id for event in handler._cached_events] == ["existing-event"]
        assert [event.id for event in coordinator.cached_events] == ["existing-event"]
        assert model.rowCount() == 1
        assert model.index(0, 0).data() == displayed
        window.timeline.set_events.assert_not_called()

        with qtbot.waitSignal(observer.settled, timeout=3000):
            requests.phase.emit("empty")
        assert handler._cached_events == []
        assert coordinator.cached_events == []
        assert model.rowCount() == 0
        window.timeline.set_events.assert_called_once_with([])
        assert observer.errors == ["Failed to load events."]
        assert observer.receiving_threads
        assert all(t == qapp.thread() for t in observer.receiving_threads)
        assert (
            len([name for name, _ in database_calls if name == "get_all_events"]) == 3
        )
    finally:
        try:
            with qtbot.waitSignal(worker.cleanup_finished, timeout=3000) as cleanup:
                requests.cleanup.emit()
            assert cleanup.args == [{"success": True, "error": ""}]
        finally:
            thread.quit()
            assert thread.wait(3000)
            coordinator.stop_graph_reload_timer()
            coordinator.stop_semantic_debounce_timer()
    assert database_calls[-1] == ("close", thread)
    assert all(t == thread and t != qapp.thread() for _, t in database_calls)
