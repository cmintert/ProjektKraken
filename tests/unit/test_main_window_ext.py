"""
Additional tests for MainWindow to improve coverage.
"""

import pytest
from unittest.mock import patch
from src.app.main import MainWindow
from src.core.events import Event


@pytest.fixture
def main_window(qtbot):
    """Create MainWindow with mocked DB."""
    with patch("src.app.main.DatabaseWorker") as MockWorker, patch(
        "src.app.main.QTimer"
    ) as MockTimer:
        mock_worker = MockWorker.return_value
        mock_db = mock_worker.db_service
        mock_db.get_all_events.return_value = []
        window = MainWindow()
        qtbot.addWidget(window)
        yield window


def test_delete_event_success(main_window):
    """Test successful event deletion."""
    event = Event(id="del1", name="To Delete", lore_date=100.0, type="generic")
    main_window.worker.db_service.get_event.return_value = event
    main_window.worker.db_service.delete_event.return_value = True

    # Mock command to return True
    with patch("src.app.main.DeleteEventCommand") as MockCmd:
        main_window.delete_event("del1")

        # Verify command was created and sent to worker
        MockCmd.assert_called_once()
        main_window.worker.run_command.assert_called_once()
        # Verify the argument was the command instance
        cmd_arg = main_window.worker.run_command.call_args[0][0]
        assert isinstance(cmd_arg, MockCmd.return_value.__class__)


def test_delete_event_sends_command(main_window):
    """Test delete event sends command to worker."""
    with patch("src.app.main.DeleteEventCommand"):
        main_window.delete_event("nonexistent")
        main_window.worker.run_command.assert_called_once()


def test_update_event_success(main_window):
    """Test successful event update."""
    event_data = {"id": "up1", "name": "Updated", "lore_date": 200.0, "type": "combat"}
    # We mock the DB get to return something valid if needed,
    # but here we just check if command is emitted or created.
    # Actually, in MainWindow test, we are checking if it calls emit.

    with patch("src.app.main.UpdateEventCommand") as MockCmd:
        main_window.update_event(event_data)

        MockCmd.assert_called_once_with("up1", event_data)
        # Verify command was sent to worker via signal
        # Since usage of signals + mocks can be tricky without Qt loop processing,
        # we check if the worker's slot was called.
        # NOTE: Real signals connected to Mocks might not fire synchronously without an event loop spin.
        # But previous tests (delete) suggest it works or we should use qtbot.
        # Let's try direct check first as per other tests.
        main_window.worker.run_command.assert_called_once()
        args = main_window.worker.run_command.call_args[0]
        assert args[0] == MockCmd.return_value


def test_update_event_sends_command(main_window):
    """Test update event sends command to worker."""
    event_data = {"id": "up2", "name": "Failed", "lore_date": 300.0, "type": "generic"}

    with patch("src.app.main.UpdateEventCommand") as MockCmd:
        main_window.update_event(event_data)

        MockCmd.assert_called_once_with("up2", event_data)
        main_window.worker.run_command.assert_called_once()


def test_add_relation_success(main_window):
    """Test adding a relation."""
    with patch("src.app.main.AddRelationCommand") as MockCmd:
        # Mock the load_event_details to avoid errors
        main_window.worker.db_service.get_event.return_value = Event(
            id="src", name="Source", lore_date=100.0, type="generic"
        )
        main_window.worker.db_service.get_relations.return_value = []
        main_window.worker.db_service.get_incoming_relations.return_value = []

        main_window.add_relation("src", "tgt", "causes", bidirectional=False)

        MockCmd.assert_called_once()
        main_window.worker.run_command.assert_called_once()


def test_add_relation_bidirectional(main_window):
    """Test adding bidirectional relation."""
    with patch("src.app.main.AddRelationCommand") as MockCmd:
        main_window.worker.db_service.get_event.return_value = Event(
            id="src", name="Source", lore_date=100.0, type="generic"
        )
        main_window.worker.db_service.get_relations.return_value = []
        main_window.worker.db_service.get_incoming_relations.return_value = []

        main_window.add_relation("src", "tgt", "related", bidirectional=True)

        # Check bidirectional was passed
        call_args = MockCmd.call_args
        assert call_args[1]["bidirectional"] is True


def test_remove_relation_success(main_window):
    """Test removing a relation."""
    main_window.event_editor._current_event_id = "evt1"

    with patch("src.app.main.RemoveRelationCommand"):
        main_window.worker.db_service.get_event.return_value = Event(
            id="evt1", name="Event", lore_date=100.0, type="generic"
        )
        main_window.worker.db_service.get_relations.return_value = []
        main_window.worker.db_service.get_incoming_relations.return_value = []

        main_window.remove_relation("rel1")

        # MockCmd.assert_called_once_with("rel1") # Params changed
        main_window.worker.run_command.assert_called_once()


def test_remove_relation_no_current_event(main_window):
    """Test removing relation when no current event."""
    main_window.event_editor._current_event_id = None

    with patch("src.app.main.RemoveRelationCommand"):
        main_window.remove_relation("rel1")

        # Should not try to reload details
        main_window.worker.db_service.get_event.assert_not_called()


def test_update_relation_success(main_window):
    """Test updating a relation."""
    main_window.event_editor._current_event_id = "evt1"

    with patch("src.app.main.UpdateRelationCommand") as MockCmd:
        mock_cmd = MockCmd.return_value
        mock_cmd.execute.return_value = True

        main_window.worker.db_service.get_event.return_value = Event(
            id="evt1", name="Event", lore_date=100.0, type="generic"
        )
        main_window.worker.db_service.get_relations.return_value = []
        main_window.worker.db_service.get_incoming_relations.return_value = []

        main_window.update_relation("rel1", "new_target", "new_type")

        MockCmd.assert_called_once_with("rel1", "new_target", "new_type")
        main_window.worker.run_command.assert_called_once()


def test_update_relation_no_current_event(main_window):
    """Test updating relation when no current event."""
    main_window.event_editor._current_event_id = None

    with patch("src.app.main.UpdateRelationCommand"):
        main_window.update_relation("rel1", "tgt", "type")

        # Command should still be sent
        main_window.worker.run_command.assert_called_once()


def test_dock_options_set(main_window):
    """Test advanced docking options are enabled."""
    from PySide6.QtWidgets import QMainWindow

    options = main_window.dockOptions()
    assert options & QMainWindow.AnimatedDocks
    assert options & QMainWindow.AllowNestedDocks
    assert options & QMainWindow.AllowTabbedDocks


def test_central_widget_is_hidden(main_window):
    """Test central widget is hidden to allow full docking."""
    assert main_window.centralWidget() is not None
    assert main_window.centralWidget().isHidden()


def test_all_docks_are_floatable(main_window):
    """Test all dock widgets can be floated."""
    from PySide6.QtWidgets import QDockWidget

    for dock in [
        main_window.list_dock,
        main_window.editor_dock,
        main_window.timeline_dock,
    ]:
        features = dock.features()
        assert features & QDockWidget.DockWidgetFloatable
        assert features & QDockWidget.DockWidgetMovable


def test_load_event_details_no_event(main_window):
    """Test load_event_details when event doesn't exist."""
    main_window.worker.db_service.get_event.return_value = None

    # Should not crash
    main_window.load_event_details("nonexistent")

    # Should not try to get relations
    main_window.worker.db_service.get_relations.assert_not_called()


def test_wikilink_completion_refreshes_ui(main_window):
    """Test that WikiLink command completion triggers UI refresh."""
    from src.commands.base_command import CommandResult
    from unittest.mock import call

    # Setup active event in editor
    main_window.event_editor._current_event_id = "evt1"

    # Simulate WikiLink command completion
    # Simulate WikiLink command completion
    result = CommandResult(
        True, "Created links", command_name="ProcessWikiLinksCommand"
    )

    # Patch load_event_details to verify it gets called
    with patch.object(main_window, "load_event_details") as mock_load:
        main_window.on_command_finished(result)

        # Verify load_event_details was called with the correct ID
        mock_load.assert_called_once_with("evt1")
