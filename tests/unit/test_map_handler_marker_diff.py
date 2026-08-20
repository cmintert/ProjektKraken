"""Tests for incremental marker diff on reload.

When the same map's markers are reloaded, MapHandler should only
add/remove/update changed markers — not clear and rebuild the
entire scene.  Full rebuild should only happen on map switch.
"""

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

from src.app.map_handler import MapHandler


@pytest.fixture(scope="session", autouse=True)
def qapp():
    """Ensure a QApplication exists."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_marker(
    object_id: str,
    label: str = "M",
    x: float = 0.5,
    y: float = 0.5,
    **overrides: object,
) -> dict:
    """Build a minimal processed-marker dict."""
    d: dict = {
        "id": f"db-{object_id}",
        "object_id": object_id,
        "object_type": "entity",
        "label": label,
        "x": x,
        "y": y,
        "color": None,
        "description": "",
        "attributes": {},
        "connection_count": 0,
    }
    d.update(overrides)
    return d


def _make_handler_with_markers(
    initial_markers: list[dict],
    map_id: str = "map-1",
) -> tuple[MapHandler, MagicMock]:
    """Create a MapHandler, call on_markers_ready once, return (handler, widget)."""
    mock_widget = MagicMock()
    mock_widget.get_selected_map_id.return_value = map_id
    mock_widget.map_selector.currentData.return_value = map_id
    mock_widget._cached_entities = []
    mock_widget._cached_events = []

    test_map = MagicMock()
    test_map.id = map_id
    test_map.layers = None
    test_map.attributes = {}
    mock_widget.maps_data = [test_map]

    # Mock the view's markers dict to reflect what add_marker would store
    mock_view = MagicMock()
    markers_store: dict = {}
    mock_view.markers = markers_store
    mock_view.graphics_scene.selectedItems.return_value = []
    mock_widget.view = mock_view
    mock_widget.layer_panel.selected_node_id = None

    mock_worker = MagicMock()
    handler = MapHandler(
        map_widget=mock_widget,
        worker=mock_worker,
        db_path_accessor=lambda: "/tmp/world.kraken",
        navigation_set_selection=MagicMock(),
    )

    # Simulate initial load — populate markers_store as add_marker would
    def fake_add_marker(**kwargs: object) -> None:
        mid = kwargs["marker_id"]
        item = MagicMock()
        item.marker_id = mid
        item.connection_count = 0
        markers_store[mid] = item

    mock_widget.add_marker.side_effect = fake_add_marker

    handler.on_markers_ready(map_id, initial_markers)

    # Reset call history so we only count calls from the second reload
    mock_widget.add_marker.reset_mock()
    mock_widget.clear_markers.reset_mock()
    mock_widget.add_marker.side_effect = fake_add_marker

    return handler, mock_widget


class TestIncrementalMarkerDiff:
    """Tests for incremental marker reload."""

    def test_marker_reload_same_set_no_clear(self, qapp) -> None:
        """Reloading the same markers must NOT call clear_markers."""
        markers = [_make_marker("a"), _make_marker("b"), _make_marker("c")]
        handler, widget = _make_handler_with_markers(markers)

        handler.on_markers_ready("map-1", markers)

        widget.clear_markers.assert_not_called()

    def test_marker_reload_adds_only_new(self, qapp) -> None:
        """Reloading with new markers only adds the newcomers."""
        initial = [_make_marker("a"), _make_marker("b")]
        handler, widget = _make_handler_with_markers(initial)

        reloaded = initial + [_make_marker("c"), _make_marker("d")]
        handler.on_markers_ready("map-1", reloaded)

        # Only 2 new add_marker calls (c, d) — not 4
        added_ids = [c.kwargs["marker_id"] for c in widget.add_marker.call_args_list]
        assert sorted(added_ids) == ["c", "d"]

    def test_marker_reload_removes_deleted(self, qapp) -> None:
        """Reloading with fewer markers removes the absent ones."""
        initial = [_make_marker("a"), _make_marker("b"), _make_marker("c")]
        handler, widget = _make_handler_with_markers(initial)

        reloaded = [_make_marker("a")]
        handler.on_markers_ready("map-1", reloaded)

        # b and c should be individually removed via the widget (not view directly)
        removed_ids = [
            c.args[0] if c.args else c.kwargs.get("marker_id")
            for c in widget.remove_marker.call_args_list
        ]
        assert sorted(removed_ids) == ["b", "c"]

    def test_marker_reload_updates_position(self, qapp) -> None:
        """Reloading with a changed position does incremental update, not full rebuild."""
        initial = [_make_marker("a", x=0.1, y=0.1)]
        handler, widget = _make_handler_with_markers(initial)

        reloaded = [_make_marker("a", x=0.9, y=0.9)]
        handler.on_markers_ready("map-1", reloaded)

        # Should NOT have cleared and rebuilt the entire scene
        widget.clear_markers.assert_not_called()
        # The changed marker is re-added (remove + add) but NOT via full rebuild
        assert widget.view.remove_marker.call_count == 1
        assert widget.add_marker.call_count == 1

    def test_marker_geometry_reload_preserves_map_viewport(self, qapp) -> None:
        """Changing icon geometry must not nudge the map viewport."""
        initial = [
            _make_marker("a", attributes={"_v_marker_icon_id": "map.pin"})
        ]
        handler, widget = _make_handler_with_markers(initial)
        transform = MagicMock(name="saved_transform")
        widget.view.transform.return_value = transform
        widget.view.horizontalScrollBar().value.return_value = 123
        widget.view.verticalScrollBar().value.return_value = 456

        handler.on_markers_ready(
            "map-1",
            [
                _make_marker(
                    "a", attributes={"_v_marker_icon_id": "place.castle"}
                )
            ],
        )

        widget.view.setTransform.assert_called_with(transform)
        widget.view.horizontalScrollBar().setValue.assert_called_with(123)
        widget.view.verticalScrollBar().setValue.assert_called_with(456)

    def test_marker_attribute_change_rebuilds_only_that_marker(self, qapp) -> None:
        """Sizing provenance changes must be visible after redo and undo reloads."""
        initial = [_make_marker("a", attributes={"_v_marker_sizing_source": "custom"})]
        handler, widget = _make_handler_with_markers(initial)

        handler.on_markers_ready(
            "map-1",
            [
                _make_marker(
                    "a",
                    attributes={"_v_marker_sizing_source": "icon_default"},
                )
            ],
        )

        widget.view.remove_marker.assert_called_once_with("a")
        assert widget.add_marker.call_count == 1

    def test_full_rebuild_on_map_switch(self, qapp) -> None:
        """Switching to a different map ID must do a full rebuild."""
        initial = [_make_marker("a")]
        handler, widget = _make_handler_with_markers(initial, map_id="map-1")

        # Switch to different map
        widget.map_selector.currentData.return_value = "map-2"
        widget.get_selected_map_id.return_value = "map-2"
        new_map = MagicMock()
        new_map.id = "map-2"
        new_map.layers = None
        new_map.attributes = {}
        widget.maps_data.append(new_map)

        handler.on_markers_ready("map-2", [_make_marker("x")])

        widget.clear_markers.assert_called_once()
