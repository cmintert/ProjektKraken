import pytest
from PySide6.QtCore import QObject, Signal, Slot
from unittest.mock import MagicMock

from src.gui.widgets.entity_editor import EntityEditorWidget
from src.gui.widgets.event_editor import EventEditorWidget
from src.app.worker_manager import WorkerManager
from src.core.entities import Entity
from src.core.events import Event


class MockWorker(QObject):
    generate_summary = Slot(object)

    def __init__(self):
        super().__init__()
        self.generate_summary_called = False
        self.last_item = None

    @Slot(object)
    def generate_summary(self, item):
        self.generate_summary_called = True
        self.last_item = item


class MockMainWindow(QObject):
    def __init__(self):
        super().__init__()
        self.worker = MockWorker()
        self.worker_thread = QObject()
        self.status_bar = MagicMock()


@pytest.fixture
def mock_main_window():
    return MockMainWindow()


@pytest.fixture
def worker_manager(mock_main_window):
    manager = WorkerManager(mock_main_window)
    # Important: In unit test, we might avoid init_worker() full logic
    # but we need to connect the signal to test end-to-end integration with worker
    manager.summary_requested.connect(manager.window.worker.generate_summary)
    return manager


def test_entity_editor_signal_connection(qtbot, worker_manager):
    """Test that EntityEditor signal triggers WorkerManager.summary_requested."""

    # Setup
    editor = EntityEditorWidget()
    editor.summary_generation_requested.connect(worker_manager.generate_summary)

    # Mock data
    editor._current_entity_id = "test_entity_id"
    editor.name_edit.setText("Test Entity")

    # We want to wait for the SIGNAL from worker_manager, confirming proper flow
    with qtbot.waitSignal(worker_manager.summary_requested, timeout=1000) as blocker:
        editor._on_summary_generate_requested()

    assert blocker.signal_triggered
    # We can also verify the payload if needed
    args = blocker.args
    assert isinstance(args[0], Entity)
    assert args[0].name == "Test Entity"

    # Verify Worker received it (since we connected it manually in fixture)
    assert worker_manager.window.worker.generate_summary_called
    assert worker_manager.window.worker.last_item.id == "test_entity_id"


def test_event_editor_signal_connection(qtbot, worker_manager):
    """Test that EventEditor signal triggers WorkerManager.summary_requested."""

    editor = EventEditorWidget()
    editor.summary_generation_requested.connect(worker_manager.generate_summary)

    editor._current_event_id = "test_event_id"
    editor.name_edit.setText("Test Event")

    with qtbot.waitSignal(worker_manager.summary_requested, timeout=1000) as blocker:
        editor._on_summary_generate_requested()

    assert blocker.signal_triggered
    assert worker_manager.window.worker.generate_summary_called
    assert worker_manager.window.worker.last_item.id == "test_event_id"
