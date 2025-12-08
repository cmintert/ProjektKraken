"""
Additional tests for MainWindow to improve coverage.
"""

import pytest
from unittest.mock import patch, MagicMock
from PySide6.QtCore import QSettings
from src.app.main import MainWindow
from src.core.events import Event


@pytest.fixture
def main_window(qtbot):
    """Create MainWindow with mocked DB."""
    with patch("src.app.main.DatabaseService") as MockDB:
        mock_db = MockDB.return_value
        mock_db.get_all_events.return_value = []
        window = MainWindow()
        qtbot.addWidget(window)
        yield window


def test_delete_event_success(main_window):
    """Test successful event deletion."""
    event = Event(id="del1", name="To Delete", lore_date=100.0, type="generic")
    main_window.db_service.get_event.return_value = event
    main_window.db_service.delete_event.return_value = True

    # Mock command to return True
    with patch("src.app.main.DeleteEventCommand") as MockCmd:
        mock_cmd = MockCmd.return_value
        mock_cmd.execute.return_value = True

        main_window.delete_event("del1")

        # Verify command was created and executed
        MockCmd.assert_called_once()
        mock_cmd.execute.assert_called_once()


def test_delete_event_failure(main_window):
    """Test event deletion failure."""
    with patch("src.app.main.DeleteEventCommand") as MockCmd:
        mock_cmd = MockCmd.return_value
        mock_cmd.execute.return_value = False

        main_window.delete_event("nonexistent")

        # Should still create command but not reload
        mock_cmd.execute.assert_called_once()


def test_update_event_success(main_window):
    """Test successful event update."""
    event = Event(id="up1", name="Updated", lore_date=200.0, type="combat")
    main_window.db_service.get_event.return_value = event

    with patch("src.app.main.UpdateEventCommand") as MockCmd:
        mock_cmd = MockCmd.return_value
        mock_cmd.execute.return_value = True

        main_window.update_event(event)

        MockCmd.assert_called_once()
        mock_cmd.execute.assert_called_once()


def test_update_event_failure(main_window):
    """Test event update failure."""
    event = Event(id="up2", name="Failed", lore_date=300.0, type="generic")

    with patch("src.app.main.UpdateEventCommand") as MockCmd:
        mock_cmd = MockCmd.return_value
        mock_cmd.execute.return_value = False

        main_window.update_event(event)

        mock_cmd.execute.assert_called_once()


def test_add_relation_success(main_window):
    """Test adding a relation."""
    with patch("src.app.main.AddRelationCommand") as MockCmd:
        mock_cmd = MockCmd.return_value
        mock_cmd.execute.return_value = True

        # Mock the load_event_details to avoid errors
        main_window.db_service.get_event.return_value = Event(
            id="src", name="Source", lore_date=100.0, type="generic"
        )
        main_window.db_service.get_relations.return_value = []
        main_window.db_service.get_incoming_relations.return_value = []

        main_window.add_relation("src", "tgt", "causes", bidirectional=False)

        MockCmd.assert_called_once()
        mock_cmd.execute.assert_called_once()


def test_add_relation_bidirectional(main_window):
    """Test adding bidirectional relation."""
    with patch("src.app.main.AddRelationCommand") as MockCmd:
        mock_cmd = MockCmd.return_value
        mock_cmd.execute.return_value = True

        main_window.db_service.get_event.return_value = Event(
            id="src", name="Source", lore_date=100.0, type="generic"
        )
        main_window.db_service.get_relations.return_value = []
        main_window.db_service.get_incoming_relations.return_value = []

        main_window.add_relation("src", "tgt", "related", bidirectional=True)

        # Check bidirectional was passed
        call_args = MockCmd.call_args
        assert call_args[1]["bidirectional"] is True


def test_remove_relation_success(main_window):
    """Test removing a relation."""
    main_window.event_editor._current_event_id = "evt1"

    with patch("src.app.main.RemoveRelationCommand") as MockCmd:
        mock_cmd = MockCmd.return_value
        mock_cmd.execute.return_value = True

        main_window.db_service.get_event.return_value = Event(
            id="evt1", name="Event", lore_date=100.0, type="generic"
        )
        main_window.db_service.get_relations.return_value = []
        main_window.db_service.get_incoming_relations.return_value = []

        main_window.remove_relation("rel1")

        MockCmd.assert_called_once_with(main_window.db_service, "rel1")
        mock_cmd.execute.assert_called_once()


def test_remove_relation_no_current_event(main_window):
    """Test removing relation when no current event."""
    main_window.event_editor._current_event_id = None

    with patch("src.app.main.RemoveRelationCommand") as MockCmd:
        mock_cmd = MockCmd.return_value
        mock_cmd.execute.return_value = True

        main_window.remove_relation("rel1")

        # Should not try to reload details
        main_window.db_service.get_event.assert_not_called()


def test_update_relation_success(main_window):
    """Test updating a relation."""
    main_window.event_editor._current_event_id = "evt1"

    with patch("src.app.main.UpdateRelationCommand") as MockCmd:
        mock_cmd = MockCmd.return_value
        mock_cmd.execute.return_value = True

        main_window.db_service.get_event.return_value = Event(
            id="evt1", name="Event", lore_date=100.0, type="generic"
        )
        main_window.db_service.get_relations.return_value = []
        main_window.db_service.get_incoming_relations.return_value = []

        main_window.update_relation("rel1", "new_target", "new_type")

        MockCmd.assert_called_once_with(
            main_window.db_service, "rel1", "new_target", "new_type"
        )
        mock_cmd.execute.assert_called_once()


def test_update_relation_no_current_event(main_window):
    """Test updating relation when no current event."""
    main_window.event_editor._current_event_id = None

    with patch("src.app.main.UpdateRelationCommand") as MockCmd:
        mock_cmd = MockCmd.return_value
        mock_cmd.execute.return_value = True

        main_window.update_relation("rel1", "tgt", "type")

        # Should not reload
    with patch("src.app.main.CreateEventCommand") as MockCmd:
        mock_cmd = MockCmd.return_value
        mock_cmd.execute.return_value = True

        main_window.seed_data()

        # Should create at least 2 event commands
        assert MockCmd.call_count >= 2


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
    main_window.db_service.get_event.return_value = None

    # Should not crash
    main_window.load_event_details("nonexistent")

    # Should not try to get relations
    main_window.db_service.get_relations.assert_not_called()
