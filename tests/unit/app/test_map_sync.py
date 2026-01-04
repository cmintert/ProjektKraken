from unittest.mock import MagicMock

import pytest

from src.app.data_handler import DataHandler
from src.app.map_handler import MapHandler
from src.commands.base_command import CommandResult


@pytest.fixture
def mock_window():
    window = MagicMock()
    # Mock data handler and map widget
    window.data_handler = DataHandler()
    window.map_widget = MagicMock()
    window.unified_list = MagicMock()
    # Mock ui_manager and docks for raise_() calls
    window.ui_manager = MagicMock()
    window.ui_manager.docks = {"event": MagicMock(), "entity": MagicMock()}
    window.check_unsaved_changes = MagicMock(return_value=True)
    window.load_event_details = MagicMock()
    window.load_entity_details = MagicMock()
    return window


def test_map_sync_entity_update(mock_window):
    """
    Test that updating an entity triggers the immediate visual update on the map.
    """
    data_handler = mock_window.data_handler

    # Init map handler (it connects to data_handler signals)
    map_handler = MapHandler(mock_window)

    # Simulate an entity ID mapping (needed for check)
    map_handler._marker_object_to_id = {"entity_123": "marker_456"}

    # Create a result from UpdateEntityCommand
    result_data = {
        "id": "entity_123",
        "name": "New Name",
        "type": "entity",
        "icon": "new_icon.svg",
        "color": "#FF0000",
    }
    result = CommandResult(
        success=True,
        message="Updated",
        command_name="UpdateEntityCommand",
        data=result_data,
    )

    # Simulate command finished
    data_handler.on_command_finished(result)

    # Verify signal was emitted
    # (Optional: can assert signal call args if using spy, but side-effect is better)

    # Verify map widget was updated with the ENTITY ID (view ID), not the DB ID
    mock_window.map_widget.update_marker_visuals.assert_called_once_with(
        marker_id="entity_123", label="New Name", icon="new_icon.svg", color="#FF0000"
    )


def test_map_sync_event_update(mock_window):
    """
    Test that updating an event triggers the immediate visual update on the map.
    """
    data_handler = mock_window.data_handler
    map_handler = MapHandler(mock_window)
    # Mapping needed to verify item is on map
    map_handler._marker_object_to_id = {"event_789": "marker_999"}

    result_data = {
        "id": "event_789",
        "name": "New Event Name",
        "type": "event",
        "icon": "event_icon.svg",
        "color": "#00FF00",
    }
    result = CommandResult(
        success=True,
        message="Updated",
        command_name="UpdateEventCommand",
        data=result_data,
    )

    data_handler.on_command_finished(result)

    # Expect EVENT ID
    mock_window.map_widget.update_marker_visuals.assert_called_once_with(
        marker_id="event_789",
        label="New Event Name",
        icon="event_icon.svg",
        color="#00FF00",
    )


def test_map_sync_no_marker(mock_window):
    """
    Test that updates are ignored if the item is not on the map (no mapping).
    """
    data_handler = mock_window.data_handler
    map_handler = MapHandler(mock_window)
    # Empty mapping
    map_handler._marker_object_to_id = {}

    result_data = {
        "id": "entity_unused",
        "name": "Ghost",
        "type": "entity",
        "icon": None,
        "color": None,
    }
    result = CommandResult(
        success=True,
        message="Updated",
        command_name="UpdateEntityCommand",
        data=result_data,
    )

    data_handler.on_command_finished(result)

    mock_window.map_widget.update_marker_visuals.assert_not_called()


def test_map_marker_click_syncs_selection(mock_window):
    """
    Test that clicking a marker syncs the selection to the Project Explorer.
    """
    map_handler = MapHandler(mock_window)

    # Test Event Click
    map_handler.on_marker_clicked("event_123", "event")
    mock_window.unified_list.select_item.assert_called_with("event", "event_123")

    # Test Entity Click
    map_handler.on_marker_clicked("entity_456", "entity")
    mock_window.unified_list.select_item.assert_called_with("entity", "entity_456")
