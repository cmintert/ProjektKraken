import pytest
from unittest.mock import MagicMock
from src.commands.map_commands import UpdateMarkerColorCommand, CommandResult
from src.core.marker import Marker
from src.services.db_service import DatabaseService


@pytest.fixture
def mock_db_service():
    return MagicMock(spec=DatabaseService)


@pytest.fixture
def sample_marker():
    return Marker(
        map_id="map1",
        object_id="obj1",
        object_type="entity",
        x=0.5,
        y=0.5,
        id="marker1",
        attributes={"icon": "castle.svg", "color": "#0000FF"},
    )


def test_update_marker_color_command(mock_db_service, sample_marker):
    # Setup
    mock_db_service.get_marker.return_value = sample_marker
    new_color = "#FF0000"
    command = UpdateMarkerColorCommand(marker_id="marker1", color=new_color)

    # Execute
    result = command.execute(mock_db_service)

    # Verify
    assert result.success
    assert result.command_name == "UpdateMarkerColorCommand"

    # Check that insert_marker was called with updated color
    args, _ = mock_db_service.insert_marker.call_args
    updated_marker = args[0]
    assert updated_marker.id == "marker1"
    assert updated_marker.attributes["color"] == new_color
    # Icon should be preserved
    assert updated_marker.attributes["icon"] == "castle.svg"


def test_update_marker_color_command_undo(mock_db_service, sample_marker):
    # Setup
    mock_db_service.get_marker.return_value = sample_marker
    new_color = "#FF0000"
    command = UpdateMarkerColorCommand(marker_id="marker1", color=new_color)

    # Execute first to set state
    command.execute(mock_db_service)

    # Undo
    command.undo(mock_db_service)

    # Verify
    # Check that insert_marker was called with original color
    # (The command calls insert_marker twice: once for execute, once for undo)
    assert mock_db_service.insert_marker.call_count == 2
    args, _ = mock_db_service.insert_marker.call_args  # Last call
    restored_marker = args[0]
    assert restored_marker.id == "marker1"
    assert restored_marker.attributes["color"] == "#0000FF"


def test_update_marker_color_command_undo_no_previous_color(mock_db_service):
    # Marker with no initial color
    marker_no_color = Marker(
        map_id="map1",
        object_id="obj1",
        object_type="entity",
        x=0.5,
        y=0.5,
        id="marker2",
        attributes={"icon": "castle.svg"},
    )
    mock_db_service.get_marker.return_value = marker_no_color

    new_color = "#FF0000"
    command = UpdateMarkerColorCommand(marker_id="marker2", color=new_color)

    # Execute
    command.execute(mock_db_service)

    # Undo
    command.undo(mock_db_service)

    # Verify
    args, _ = mock_db_service.insert_marker.call_args
    restored_marker = args[0]
    # 'color' key should be gone or None (our implementation pops it if not present before)
    assert "color" not in restored_marker.attributes


def test_update_marker_color_not_found(mock_db_service):
    mock_db_service.get_marker.return_value = None
    command = UpdateMarkerColorCommand(marker_id="missing", color="#FFFFFF")

    result = command.execute(mock_db_service)

    assert not result.success
    assert "not found" in result.message
