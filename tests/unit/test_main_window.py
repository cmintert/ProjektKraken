import pytest
from unittest.mock import patch
from src.app.main import MainWindow
from src.core.events import Event


@pytest.fixture
def main_window(qtbot):
    # Mock DB service to avoid real DB creation
    # Also Mock QTimer to prevent deferred initialization crash in tests
    with patch("src.app.main.DatabaseWorker") as MockWorker, patch(
        "src.app.main.QTimer"
    ):
        mock_worker = MockWorker.return_value
        mock_db = mock_worker.db_service
        mock_db.get_all_events.return_value = []
        window = MainWindow()
        qtbot.addWidget(window)
        return window


def test_init_window(main_window):
    assert main_window.windowTitle() == "Project Kraken - v0.2.0 (Editor Phase)"
    assert main_window.timeline is not None


def test_load_event_details(main_window, mock_invoke_method):
    # Setup mock return
    ev = Event(id="1", name="Test", lore_date=100.0)
    main_window.worker.db_service.get_event.return_value = ev
    main_window.worker.db_service.get_relations.return_value = []
    main_window.worker.db_service.get_incoming_relations.return_value = []

    # Call
    main_window.load_event_details("1")

    # Verify worker was called via invokeMethod
    # invokeMethod(worker, "load_event_details", QueuedConnection, Q_ARG(str, "1"))
    assert mock_invoke_method.called

    # Check if any call matches the expected pattern
    found_call = False
    for call in mock_invoke_method.call_args_list:
        args, _ = call
        if args[0] == main_window.worker and args[1] == "load_event_details":
            found_call = True
            break
    assert found_call, "load_event_details was not invoked via QMetaObject.invokeMethod"

    # Manually invoke the slot to verify UI update
    main_window.data_handler.on_event_details_loaded(ev, [], [])

    # Assert
    assert main_window.event_editor.name_edit.text() == "Test"


def test_create_event_flow(main_window):
    # Simulate save from editor
    ev_data = {"id": "1", "name": "New", "lore_date": 10.0}

    # Update implies existing event. Create is implicit in seeding?
    # MainWindow handles update_relation, remove_relation.
    # It passes update_event to command.

    main_window.update_event(ev_data)

    # Verify command was sent to worker
    main_window.worker.run_command.assert_called_once()
