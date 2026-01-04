from unittest.mock import MagicMock, patch

import pytest

from src.app.main import MainWindow
from src.core.events import Event


@pytest.fixture
def main_window(qtbot):
    # Mock DB service to avoid real DB creation
    # Also Mock QTimer to prevent deferred initialization crash in tests
    from PySide6.QtWidgets import QMessageBox

    with (
        patch("src.app.worker_manager.DatabaseWorker") as MockWorker,
        patch("src.app.worker_manager.QTimer"),
        patch("src.app.worker_manager.QThread"),
        patch(
            "src.app.main_window.QMessageBox.warning", return_value=QMessageBox.Discard
        ),
    ):
        mock_worker = MockWorker.return_value
        mock_db = mock_worker.db_service
        mock_db.get_all_events.return_value = []
        window = MainWindow()
        qtbot.addWidget(window)
        yield window


def test_init_window(main_window):
    from src.app.constants import WINDOW_TITLE

    assert main_window.windowTitle() == f"{WINDOW_TITLE} - world.kraken"
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


def test_create_entity(main_window):
    with patch(
        "PySide6.QtWidgets.QInputDialog.getText", return_value=("New Entity", True)
    ):
        # Ensure editor check passes
        main_window.entity_editor.has_unsaved_changes = MagicMock(return_value=False)

        main_window.create_entity()

        # Verify run_command called
        main_window.worker.run_command.assert_called_once()
        cmd = main_window.worker.run_command.call_args[0][0]
        assert cmd.__class__.__name__ == "CreateEntityCommand"
        assert cmd._entity.name == "New Entity"


def test_delete_entity(main_window):
    main_window.delete_entity("ent1")

    main_window.worker.run_command.assert_called_once()
    cmd = main_window.worker.run_command.call_args[0][0]
    assert cmd.__class__.__name__ == "DeleteEntityCommand"
    assert cmd._entity_id == "ent1"


def test_delete_event(main_window):
    main_window.delete_event("ev1")

    main_window.worker.run_command.assert_called_once()
    cmd = main_window.worker.run_command.call_args[0][0]
    assert cmd.__class__.__name__ == "DeleteEventCommand"
    assert cmd.event_id == "ev1"


def test_update_entity(main_window):
    main_window.update_entity({"id": "ent1", "name": "Updated"})

    main_window.worker.run_command.assert_called_once()
    cmd = main_window.worker.run_command.call_args[0][0]
    assert cmd.__class__.__name__ == "UpdateEntityCommand"
    assert cmd.entity_id == "ent1"
    assert cmd.update_data["name"] == "Updated"


def test_add_relation(main_window):
    main_window.add_relation("src", "dst", "relates_to", bidirectional=True)

    main_window.worker.run_command.assert_called_once()
    cmd = main_window.worker.run_command.call_args[0][0]
    assert cmd.__class__.__name__ == "AddRelationCommand"
    assert cmd.source_id == "src"
    assert cmd.target_id == "dst"
    assert cmd.bidirectional is True


@patch("src.app.main_window.QMessageBox.warning")
def test_check_unsaved_changes_save(mock_warning, main_window):
    # Setup editor with unsaved changes
    main_window.event_editor.has_unsaved_changes = MagicMock(return_value=True)
    main_window.event_editor._on_save = MagicMock()

    # Simulate User clicking Save
    from PySide6.QtWidgets import QMessageBox

    mock_warning.return_value = QMessageBox.Save

    result = main_window.check_unsaved_changes(main_window.event_editor)

    assert result is True
    main_window.event_editor._on_save.assert_called_once()


@patch("src.app.main_window.QMessageBox.warning")
def test_check_unsaved_changes_cancel(mock_warning, main_window):
    main_window.event_editor.has_unsaved_changes = MagicMock(return_value=True)

    # Simulate User clicking Cancel
    from PySide6.QtWidgets import QMessageBox

    mock_warning.return_value = QMessageBox.Cancel

    result = main_window.check_unsaved_changes(main_window.event_editor)

    assert result is False
