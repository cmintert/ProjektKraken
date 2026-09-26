from unittest.mock import Mock, patch

import pytest
from PySide6.QtWidgets import QMainWindow, QMessageBox

from src.app.coordinators.navigation_coordinator import NavigationCoordinator
from src.commands.event_commands import CreateEventCommand


class MockMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.workspace = Mock()
        self.event_editor = Mock()
        self.entity_editor = Mock()
        self.event_editor.has_unsaved_changes.return_value = False
        self.entity_editor.has_unsaved_changes.return_value = False
        self.event_editor.current_event_id = None
        self.entity_editor.current_entity_id = None
        self.editor_coordinator = Mock()
        self.unified_list = Mock()

        # Mock methods
        self.check_unsaved_changes = Mock(return_value=True)
        self.load_event_details = Mock()
        self.load_entity_details = Mock()
        self.timeline = Mock()
        # Data coordinator mock for navigation
        self.data_coordinator = Mock()
        self.data_coordinator.load_event_details = self.load_event_details
        self.data_coordinator.load_entity_details = self.load_entity_details


@pytest.fixture
def mock_main_window(qtbot):
    window = MockMainWindow()
    return window


def test_delayed_selection(qtbot, mock_main_window):
    """Test that selection is delayed."""
    coordinator = NavigationCoordinator(mock_main_window)

    # Trigger selection
    coordinator.on_item_selected("entity", "id_1")

    # Immediate check - should NOT be selected yet
    assert coordinator._pending_selection == ("entity", "id_1")
    assert coordinator.selected_id is None

    # Wait for timer: NAVIGATION_SELECTION_DELAY_MS (250ms) + 100ms buffer
    qtbot.wait(350)

    # Should be selected now
    assert coordinator._pending_selection is None
    assert coordinator.selected_id == "id_1"


def test_cross_type_navigation_guards_dirty_source(mock_main_window):
    coordinator = NavigationCoordinator(mock_main_window)
    coordinator._last_selected_type = "event"
    coordinator._last_selected_id = "event-1"
    mock_main_window.event_editor.current_event_id = "event-1"
    mock_main_window.event_editor.has_unsaved_changes.return_value = True

    with patch(
        "src.app.coordinators.navigation_coordinator.QMessageBox.warning",
        return_value=QMessageBox.StandardButton.Cancel,
    ):
        coordinator.set_global_selection("entity", "entity-2")

    mock_main_window.check_unsaved_changes.assert_not_called()
    mock_main_window.load_entity_details.assert_not_called()
    assert coordinator.selected_id == "event-1"


def test_navigation_waits_for_exact_save_acknowledgement(mock_main_window):
    coordinator = NavigationCoordinator(mock_main_window)
    coordinator._last_selected_type = "event"
    coordinator._last_selected_id = "event-1"
    source = mock_main_window.event_editor
    source.current_event_id = "event-1"
    source.has_unsaved_changes.return_value = True
    source._on_save.side_effect = lambda: setattr(source, "_pending_save_revision", 7)

    with patch(
        "src.app.coordinators.navigation_coordinator.QMessageBox.warning",
        return_value=QMessageBox.StandardButton.Save,
    ):
        coordinator.set_global_selection("entity", "entity-2")

    mock_main_window.load_entity_details.assert_not_called()
    coordinator._on_navigation_save_finished("event", "event-1", 6, True)
    mock_main_window.load_entity_details.assert_not_called()
    source.has_unsaved_changes.return_value = False
    coordinator._on_navigation_save_finished("event", "event-1", 7, True)
    mock_main_window.load_entity_details.assert_called_once_with("entity-2")


def test_selection_cancelled_by_drag(qtbot, mock_main_window):
    """Test that drag start cancels pending selection and restores previous."""
    coordinator = NavigationCoordinator(mock_main_window)

    # Set initial state (Item 1 is selected)
    coordinator._last_selected_type = "entity"
    coordinator._last_selected_id = "id_1"

    # User clicks Item 2 -> Trigger pending selection
    coordinator.on_item_selected("entity", "id_2")
    assert coordinator._pending_selection == ("entity", "id_2")

    # Trigger drag start
    coordinator.on_drag_started()
    assert coordinator._pending_selection is None

    # Wait for timer duration (to ensure delayed selection didn't happen)
    qtbot.wait(200)
    assert coordinator.selected_id == "id_1"  # Should match initial

    # Verify restore call was made (async)
    # Since we used QTimer.singleShot(0, ...), we simply wait for the event loop
    qtbot.wait(10)
    mock_main_window.unified_list.select_item.assert_called_with("entity", "id_1")


def test_drag_restore_captures_validated_selection(qtbot, mock_main_window):
    """Queued restoration uses the selection valid when the drag started."""
    coordinator = NavigationCoordinator(mock_main_window)
    coordinator._last_selected_type = "entity"
    coordinator._last_selected_id = "id_1"

    coordinator.on_drag_started()
    coordinator._last_selected_type = None
    coordinator._last_selected_id = None

    qtbot.wait(10)

    mock_main_window.unified_list.select_item.assert_called_once_with(
        "entity", "id_1"
    )


def test_missing_link_event_uses_playhead_time(mock_main_window):
    """Creating an event for a missing link uses the current playhead."""
    coordinator = NavigationCoordinator(mock_main_window)
    mock_main_window.command_requested = Mock()
    mock_main_window.timeline.get_playhead_time.return_value = 87.125

    with patch(
        "src.app.coordinators.navigation_coordinator.QMessageBox"
    ) as message_box:
        entity_button = Mock()
        event_button = Mock()
        message_box.return_value.addButton.side_effect = [
            entity_button,
            event_button,
            Mock(),
        ]
        message_box.return_value.clickedButton.return_value = event_button

        coordinator._prompt_create_missing_target("Arrival")

    command = mock_main_window.command_requested.emit.call_args.args[0]
    assert isinstance(command, CreateEventCommand)
    assert command.event.name == "Arrival"
    assert command.event.lore_date == 87.125
    mock_main_window.timeline.get_playhead_time.assert_called_once_with()
