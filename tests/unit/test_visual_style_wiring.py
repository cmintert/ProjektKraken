"""Tests for the unified visual styling signal wiring and data flow.

Verifies:
- marker_visual_style_changed signal propagates from view → widget → handler
- MapHandler.on_marker_visual_style_changed creates correct command
- DataHandler forwards visual_attributes and prefers _v_fill over legacy color
- MarkerManager passes visual_attributes through to MarkerItem
"""

from unittest.mock import MagicMock, patch

import pytest

from src.commands.marker_commands import (
    ApplyMarkerAppearanceCommand,
    UpdateMarkerAttributeCommand,
)
from src.core.marker_appearance import MARKER_ICON_ANCHOR_ATTRIBUTE
from src.core.style_constants import V_BORDER_WIDTH, V_FILL, V_SIZE_SCALE

# ---------------------------------------------------------------------------
# MapHandler – visual style signal → command
# ---------------------------------------------------------------------------


class TestMapHandlerVisualStyle:
    """Tests for MapHandler.on_marker_visual_style_changed."""

    @pytest.fixture
    def map_handler(self):
        from src.app.map_handler import MapHandler

        map_widget = MagicMock()
        worker = MagicMock()
        db_path = MagicMock(return_value="/tmp/test.kraken")
        nav = MagicMock()
        handler = MapHandler(map_widget, worker, db_path, nav)
        # Pre-populate the object→marker ID mapping
        handler._marker_object_to_id = {
            "obj_1": "actual_marker_1",
            "obj_2": "actual_marker_2",
        }
        return handler

    def test_emits_update_attribute_command(self, map_handler):
        """Visual style change should emit UpdateMarkerAttributeCommand."""
        spy = MagicMock()
        map_handler.command_requested.connect(spy)

        map_handler.on_marker_visual_style_changed(
            "obj_1", {V_FILL: "#FF0000", V_SIZE_SCALE: 1.5}
        )

        spy.assert_called_once()
        cmd = spy.call_args[0][0]
        assert isinstance(cmd, UpdateMarkerAttributeCommand)
        assert cmd.marker_id == "actual_marker_1"
        assert cmd.updates == {V_FILL: "#FF0000", V_SIZE_SCALE: 1.5}

    def test_unknown_marker_id_does_not_emit(self, map_handler):
        """Unknown object_id should not emit a command."""
        spy = MagicMock()
        map_handler.command_requested.connect(spy)

        map_handler.on_marker_visual_style_changed("unknown_obj", {V_FILL: "#FF0000"})

        spy.assert_not_called()

    def test_border_width_change(self, map_handler):
        """Border width changes route through the same path."""
        spy = MagicMock()
        map_handler.command_requested.connect(spy)

        map_handler.on_marker_visual_style_changed("obj_2", {V_BORDER_WIDTH: 4})

        cmd = spy.call_args[0][0]
        assert cmd.updates == {V_BORDER_WIDTH: 4}
        assert cmd.marker_id == "actual_marker_2"

    def test_complete_appearance_uses_atomic_command(self, map_handler):
        """Copy/paste and direct edits use exact appearance replacement."""
        spy = MagicMock()
        map_handler.command_requested.connect(spy)
        appearance = {
            V_FILL: "#FF0000",
            MARKER_ICON_ANCHOR_ATTRIBUTE: {"x": 0.5, "y": 1.0},
        }

        map_handler.on_marker_appearance_changed("obj_1", appearance)

        command = spy.call_args.args[0]
        assert isinstance(command, ApplyMarkerAppearanceCommand)
        assert command.marker_id == "actual_marker_1"
        assert command.appearance == appearance


# ---------------------------------------------------------------------------
# DataHandler – visual_attributes and _v_fill priority
# ---------------------------------------------------------------------------


class TestDataHandlerVisualAttributes:
    """Tests for DataHandler.on_markers_loaded attribute forwarding."""

    @pytest.fixture
    def data_handler(self):
        from src.app.data_handler import DataHandler

        handler = DataHandler()
        return handler

    def test_attributes_included_in_processed_markers(self, data_handler):
        """Processed markers should include the full attributes dict."""
        marker = MagicMock()
        marker.id = "m1"
        marker.object_id = "obj1"
        marker.object_type = "entity"
        marker.x = 0.5
        marker.y = 0.5
        marker.attributes = {
            "icon": "castle.svg",
            V_FILL: "#E02A2A",
            V_SIZE_SCALE: 1.5,
        }
        marker.feature_type = "point"
        marker.geometry = None
        marker.style = None

        entity = MagicMock()
        entity.id = "obj1"
        entity.name = "Stronghold"
        entity.description = "A fortress"

        data_handler._cached_entities = [entity]
        data_handler._cached_events = []

        received = []
        data_handler.markers_ready.connect(
            lambda map_id, markers: received.extend(markers)
        )

        data_handler.on_markers_loaded("map1", [marker])

        assert len(received) == 1
        processed = received[0]
        assert processed["attributes"] == marker.attributes
        assert processed["attributes"][V_FILL] == "#E02A2A"
        assert processed["attributes"][V_SIZE_SCALE] == 1.5

    def test_v_fill_preferred_over_legacy_color(self, data_handler):
        """``_v_fill`` should take priority over legacy ``color`` key."""
        marker = MagicMock()
        marker.id = "m2"
        marker.object_id = "obj2"
        marker.object_type = "entity"
        marker.x = 0.5
        marker.y = 0.5
        marker.attributes = {"color": "#OLD_BLUE", V_FILL: "#NEW_RED"}
        marker.feature_type = "point"
        marker.geometry = None
        marker.style = None

        entity = MagicMock()
        entity.id = "obj2"
        entity.name = "Village"
        entity.description = ""

        data_handler._cached_entities = [entity]
        data_handler._cached_events = []

        received = []
        data_handler.markers_ready.connect(
            lambda map_id, markers: received.extend(markers)
        )

        data_handler.on_markers_loaded("map1", [marker])

        processed = received[0]
        # color field should prefer _v_fill
        assert processed["color"] == "#NEW_RED"

    def test_legacy_color_used_when_no_v_fill(self, data_handler):
        """Falls back to legacy ``color`` key when ``_v_fill`` is absent."""
        marker = MagicMock()
        marker.id = "m3"
        marker.object_id = "obj3"
        marker.object_type = "entity"
        marker.x = 0.5
        marker.y = 0.5
        marker.attributes = {"color": "#LEGACY_BLUE"}
        marker.feature_type = "point"
        marker.geometry = None
        marker.style = None

        entity = MagicMock()
        entity.id = "obj3"
        entity.name = "Old Town"
        entity.description = ""

        data_handler._cached_entities = [entity]
        data_handler._cached_events = []

        received = []
        data_handler.markers_ready.connect(
            lambda map_id, markers: received.extend(markers)
        )

        data_handler.on_markers_loaded("map1", [marker])

        processed = received[0]
        assert processed["color"] == "#LEGACY_BLUE"

    @pytest.mark.parametrize("object_type", ["entity", "event"])
    def test_marker_uses_summary_instead_of_description(
        self, data_handler, object_type
    ):
        """Marker tooltip data should contain the stored item summary."""
        marker = MagicMock()
        marker.id = "m-summary"
        marker.object_id = "obj-summary"
        marker.object_type = object_type
        marker.x = 0.5
        marker.y = 0.5
        marker.attributes = {}
        marker.feature_type = "point"
        marker.geometry = None
        marker.style = None

        item = MagicMock()
        item.id = marker.object_id
        item.name = "North Star"
        item.description = "The full description must not be used."
        item.attributes = {"_summary_data": {"text": "  A concise summary.  "}}
        item.lore_date = 12.0
        data_handler._cached_entities = [item] if object_type == "entity" else []
        data_handler._cached_events = [item] if object_type == "event" else []

        received = []
        data_handler.markers_ready.connect(
            lambda map_id, markers: received.extend(markers)
        )

        data_handler.on_markers_loaded("map1", [marker])

        assert received[0]["summary"] == "A concise summary."
        assert "description" not in received[0]

    def test_marker_without_summary_leaves_name_fallback(self, data_handler):
        """Missing or blank summaries should let the marker display its name."""
        marker = MagicMock()
        marker.id = "m-name"
        marker.object_id = "obj-name"
        marker.object_type = "entity"
        marker.x = 0.5
        marker.y = 0.5
        marker.attributes = {}
        marker.feature_type = "point"
        marker.geometry = None
        marker.style = None

        entity = MagicMock()
        entity.id = marker.object_id
        entity.name = "North Star"
        entity.description = "The full description must not be used."
        entity.attributes = {"_summary_data": {"text": "   "}}
        data_handler._cached_entities = [entity]
        data_handler._cached_events = []

        received = []
        data_handler.markers_ready.connect(
            lambda map_id, markers: received.extend(markers)
        )

        data_handler.on_markers_loaded("map1", [marker])

        assert received[0]["label"] == "North Star"
        assert received[0]["summary"] == ""


# ---------------------------------------------------------------------------
# MarkerManager – visual_attributes passthrough
# ---------------------------------------------------------------------------


class TestMarkerManagerVisualAttributes:
    """Tests that MarkerManager passes visual_attributes to MarkerItem."""

    def test_visual_attributes_forwarded(self, qtbot):
        """MarkerItem should receive visual_attributes from MarkerManager."""
        from src.gui.widgets.map.marker_manager import MarkerManager

        # Fully mocked view — avoids real QGraphicsScene.addItem type check
        view = MagicMock()

        manager = MarkerManager(view)

        test_attrs = {V_FILL: "#E02A2A", V_SIZE_SCALE: 1.5}

        with patch("src.gui.widgets.map.marker_manager.MarkerItem") as MockMarker:
            mock_instance = MagicMock()
            mock_instance.clicked = MagicMock()
            mock_instance.clicked.connect = MagicMock()
            MockMarker.return_value = mock_instance

            manager.add_marker(
                marker_id="obj1",
                object_type="entity",
                label="Stronghold",
                x=0.5,
                y=0.5,
                visual_attributes=test_attrs,
            )

            MockMarker.assert_called_once()
            call_kwargs = MockMarker.call_args
            # visual_attributes is passed as keyword arg
            assert call_kwargs[1].get("visual_attributes") == test_attrs
