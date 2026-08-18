from unittest.mock import MagicMock

import pytest

from src.app.map_handler import MapHandler
from src.core.map import Map
from src.core.marker_sizing import MARKER_SIZING_ATTRIBUTE

# UpdateMapCommand is imported in map_handler, but we mock it.


@pytest.fixture
def mock_map_widget():
    widget = MagicMock()
    widget.map_selector.currentData.return_value = None
    return widget


@pytest.fixture
def map_handler(mock_map_widget):
    handler = MapHandler(
        map_widget=mock_map_widget,
        worker=MagicMock(),
        db_path_accessor=lambda: "/tmp/test.db",
        navigation_set_selection=MagicMock(),
    )
    return handler


def test_on_map_scale_changed_emits_command(map_handler, mock_map_widget):
    """Test that changing scale emits an update command."""
    # Setup — mock the map selector to return a valid ID
    mock_map_widget.map_selector.currentData.return_value = "map_1"

    # Spy on the real Signal
    spy = MagicMock()
    map_handler.command_requested.connect(spy)

    map_handler.on_map_scale_changed(500.0)

    spy.assert_called_once()
    cmd = spy.call_args[0][0]
    assert cmd.__class__.__name__ == "UpdateMapCommand"
    assert cmd.update_data == {"attributes": {"width_meters": 500.0}}


def test_on_map_settings_changed_emits_one_atomic_command(
    map_handler, mock_map_widget
):
    """Map attribute changes persist through one map command."""
    mock_map_widget.map_selector.currentData.return_value = "map_1"
    spy = MagicMock()
    map_handler.command_requested.connect(spy)
    updates = {
        "width_meters": 500.0,
    }

    map_handler.on_map_settings_changed(updates)

    spy.assert_called_once()
    cmd = spy.call_args[0][0]
    assert cmd.update_data == {"attributes": updates}


def test_on_map_selected_loads_scale(map_handler, mock_map_widget):
    """Test that selecting a map loads its scale."""
    map_id = "map_1"
    mock_map = MagicMock(spec=Map)
    mock_map.id = map_id
    mock_map.image_path = "/tmp/test.png"
    mock_map.attributes = {"width_meters": 2500.0}

    mock_map_default = MagicMock(spec=Map)
    mock_map_default.id = "map_2"
    mock_map_default.image_path = "/tmp/test2.png"
    mock_map_default.attributes = {}

    mock_map_widget.maps_data = [mock_map, mock_map_default]
    mock_map_widget.view = MagicMock()

    # Action 1: Load map with scale
    map_handler.on_map_selected(map_id)

    mock_map_widget.load_map.assert_called()
    mock_map_widget.view.set_map_width_meters.assert_called_with(2500.0)

    # Action 2: Load map without scale (explicitly uncalibrated)
    mock_map_widget.view.set_map_width_meters.reset_mock()
    map_handler.on_map_selected("map_2")

    mock_map_widget.view.clear_map_scale.assert_called_once_with()


def test_delete_map_exits_editing_before_emitting_command(map_handler, mock_map_widget):
    """Map deletion must shut down active edit modes before dispatching the command."""
    order: list[str] = []
    mock_map_widget.exit_editing_modes.side_effect = lambda: order.append("exit")
    map_handler.command_requested.connect(lambda _cmd: order.append("emit"))

    map_handler.delete_map("map_1")

    mock_map_widget.exit_editing_modes.assert_called_once_with()
    assert order == ["exit", "emit"]


def test_create_marker_persists_native_fifty_pixel_relative_size(
    map_handler, mock_map_widget
):
    """New marker placement stores the map-relative size derived from its image."""
    pixmap_item = MagicMock()
    pixmap_item.boundingRect.return_value.width.return_value = 1000.0
    mock_map_widget.view.pixmap_item = pixmap_item
    spy = MagicMock()
    map_handler.command_requested.connect(spy)

    map_handler.create_marker("map-1", "entity-1", "entity", "Harbour", 0.5, 0.5)

    command = spy.call_args.args[0]
    settings = command._marker.attributes[MARKER_SIZING_ATTRIBUTE]
    assert settings["map_value"] == pytest.approx(5.0)
