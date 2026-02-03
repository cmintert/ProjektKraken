import pytest
from unittest.mock import MagicMock, patch
from src.app.map_handler import MapHandler
from src.core.map import Map

# UpdateMapCommand is imported in map_handler, but we mock it.


@pytest.fixture
def mock_window():
    window = MagicMock()
    # Mock data structs
    window.data_handler = MagicMock()
    # Mock map selector default behavior
    window.map_widget.map_selector.currentData.return_value = None
    return window


@pytest.fixture
def map_handler(mock_window):
    return MapHandler(mock_window)


def test_on_map_scale_changed_emits_command(map_handler):
    """Test that changing scale emits an update command."""
    # Setup
    # Mock the map selector to return a valid ID
    map_handler.window.map_widget.map_selector.currentData.return_value = "map_1"

    # We need to mock UpdateMapCommand to check if it's called
    with patch("src.app.map_handler.UpdateMapCommand") as MockCommand:
        # Action
        map_handler.on_map_scale_changed(500.0)

        # Verify
        # Should create command
        MockCommand.assert_called_once()
        args, kwargs = MockCommand.call_args
        assert args[0] == "map_1"  # map_id

        # Check kwargs or second arg depending on constructor
        # UpdateMapCommand(map_id, update_data)
        if len(args) > 1:
            assert args[1] == {"attributes": {"width_meters": 500.0}}
        else:
            # Maybe passed as kwargs?
            # It seems constructor is UpdateMapCommand(map_id, update_data)
            # Check call args carefully
            assert args[1] == {"attributes": {"width_meters": 500.0}}

        # Should emit command via window
        map_handler.window.command_requested.emit.assert_called_once()


def test_on_map_selected_loads_scale(map_handler):
    """Test that selecting a map loads its scale."""
    # Setup
    map_id = "map_1"
    mock_map = MagicMock(spec=Map)
    mock_map.id = map_id
    mock_map.image_path = "/tmp/test.png"
    mock_map.attributes = {"width_meters": 2500.0}

    mock_map_default = MagicMock(spec=Map)
    mock_map_default.id = "map_2"
    mock_map_default.image_path = "/tmp/test2.png"
    mock_map_default.attributes = {}

    # MapHandler accesses map_widget._maps_data list
    map_handler.window.map_widget._maps_data = [mock_map, mock_map_default]

    # Mock the view
    map_handler.window.map_widget.view = MagicMock()

    # Action 1: Load map with scale
    map_handler.on_map_selected(map_id)

    # Verify
    map_handler.window.map_widget.load_map.assert_called()
    map_handler.window.map_widget.view.set_map_width_meters.assert_called_with(2500.0)

    # Action 2: Load map without scale (default)
    map_handler.window.map_widget.view.set_map_width_meters.reset_mock()
    map_handler.on_map_selected("map_2")

    # Verify default
    map_handler.window.map_widget.view.set_map_width_meters.assert_called_with(
        1_000_000.0
    )
