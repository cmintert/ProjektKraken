"""
Additional tests for MainWindow and EditorCoordinator to improve coverage.
"""

from unittest.mock import patch

import pytest

from src.app.main import MainWindow


@pytest.fixture
def main_window(qtbot):
    """Create MainWindow with mocked DB."""
    with (
        patch("src.app.worker_manager.DatabaseWorker") as MockWorker,
        patch("src.app.main_window.QTimer"),
        patch("src.app.worker_manager.QThread"),
    ):
        mock_worker = MockWorker.return_value
        mock_db = mock_worker.db_service
        mock_db.get_all_events.return_value = []
        window = MainWindow()
        qtbot.addWidget(window)
        yield window


def test_delete_event_success(main_window, qtbot):
    """Test successful event deletion via editor_coordinator."""
    with patch("src.app.coordinators.editor_coordinator.DeleteEventCommand") as MockCmd:
        with qtbot.waitSignal(
            main_window.editor_coordinator.command_requested, timeout=1000
        ):
            main_window.editor_coordinator.delete_event("del1")

        MockCmd.assert_called_once()


def test_delete_event_sends_command(main_window, qtbot):
    """Test delete event sends command via editor_coordinator."""
    with patch("src.app.coordinators.editor_coordinator.DeleteEventCommand"):
        with qtbot.waitSignal(
            main_window.editor_coordinator.command_requested, timeout=1000
        ):
            main_window.editor_coordinator.delete_event("nonexistent")


def test_update_event_success(main_window, qtbot):
    """Test successful event update via editor_coordinator."""
    event_data = {"id": "up1", "name": "Updated", "lore_date": 200.0, "type": "combat"}

    with patch("src.app.coordinators.editor_coordinator.UpdateEventCommand") as MockCmd:
        with qtbot.waitSignal(
            main_window.editor_coordinator.command_requested, timeout=1000
        ):
            main_window.editor_coordinator.update_event(event_data)

        MockCmd.assert_called_once_with("up1", event_data)


def test_update_event_sends_command(main_window, qtbot):
    """Test update event sends command via editor_coordinator."""
    event_data = {"id": "up2", "name": "Failed", "lore_date": 300.0, "type": "generic"}

    with patch("src.app.coordinators.editor_coordinator.UpdateEventCommand") as MockCmd:
        with qtbot.waitSignal(
            main_window.editor_coordinator.command_requested, timeout=1000
        ):
            main_window.editor_coordinator.update_event(event_data)

        MockCmd.assert_called_once_with("up2", event_data)


def test_add_relation_success(main_window, qtbot):
    """Test adding a relation via editor_coordinator."""
    with patch("src.app.coordinators.editor_coordinator.AddRelationCommand") as MockCmd:
        with qtbot.waitSignal(
            main_window.editor_coordinator.command_requested, timeout=1000
        ):
            main_window.editor_coordinator.add_relation(
                "src", "tgt", "causes", bidirectional=False
            )

        MockCmd.assert_called_once()


def test_add_relation_bidirectional(main_window):
    """Test adding bidirectional relation via editor_coordinator."""
    with patch("src.app.coordinators.editor_coordinator.AddRelationCommand") as MockCmd:
        main_window.editor_coordinator.add_relation(
            "src", "tgt", "related", bidirectional=True
        )

        # Check bidirectional was passed
        call_args = MockCmd.call_args
        assert call_args[1]["bidirectional"] is True


def test_remove_relation_success(main_window, qtbot):
    """Test removing a relation via editor_coordinator."""
    with patch("src.app.coordinators.editor_coordinator.RemoveRelationCommand"):
        with qtbot.waitSignal(
            main_window.editor_coordinator.command_requested, timeout=1000
        ):
            main_window.editor_coordinator.remove_relation("rel1")


def test_remove_relation_emits_command(main_window):
    """Test removing a relation emits command via editor_coordinator."""
    with patch(
        "src.app.coordinators.editor_coordinator.RemoveRelationCommand"
    ) as MockCmd:
        main_window.editor_coordinator.remove_relation("rel1")
        MockCmd.assert_called_once_with("rel1")


def test_update_relation_success(main_window, qtbot):
    """Test updating a relation via editor_coordinator."""
    with patch(
        "src.app.coordinators.editor_coordinator.UpdateRelationCommand"
    ) as MockCmd:
        with qtbot.waitSignal(
            main_window.editor_coordinator.command_requested, timeout=1000
        ):
            main_window.editor_coordinator.update_relation(
                "rel1", "new_target", "new_type"
            )

        MockCmd.assert_called_once_with(
            "rel1", "new_target", "new_type", attributes=None
        )


def test_update_relation_emits_command(main_window):
    """Test updating a relation emits command via editor_coordinator."""
    with patch(
        "src.app.coordinators.editor_coordinator.UpdateRelationCommand"
    ) as MockCmd:
        main_window.editor_coordinator.update_relation("rel1", "tgt", "type")
        MockCmd.assert_called_once_with("rel1", "tgt", "type", attributes=None)


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
