"""Tests for the Visual Resolver and Style Constants system.

Tests cover:
- Style Constants definitions
- VisualResolver cascading resolution (user override → theme → hard fallback)
- UpdateMarkerAttributeCommand undo/redo
- GraphBuilder integration with VisualResolver
- MarkerItem integration with VisualResolver
"""

from unittest.mock import MagicMock

import pytest

from src.core.entities import Entity
from src.core.events import Event
from src.core.marker import Marker
from src.core.style_constants import (
    BASE_BORDER_WIDTH,
    BASE_SCALE,
    BASE_SIZE,
    DEFAULT_BORDER_COLOR,
    DEFAULT_ENTITY_COLOR,
    DEFAULT_EVENT_COLOR,
    V_BORDER,
    V_BORDER_WIDTH,
    V_FILL,
    V_ICON,
    V_SIZE_SCALE,
)
from src.services.visual_resolver import VisualResolver

# ---------------------------------------------------------------------------
# Style Constants
# ---------------------------------------------------------------------------


class TestStyleConstants:
    """Tests for style_constants module values."""

    def test_base_size_is_24(self):
        assert BASE_SIZE == 24

    def test_base_border_width_is_2(self):
        assert BASE_BORDER_WIDTH == 2

    def test_base_scale_is_1(self):
        assert BASE_SCALE == 1.0

    def test_key_prefixes(self):
        """All visual keys start with _v_ prefix."""
        for key in (V_FILL, V_BORDER, V_SIZE_SCALE, V_BORDER_WIDTH, V_ICON):
            assert key.startswith("_v_")


# ---------------------------------------------------------------------------
# VisualResolver – Fill Color
# ---------------------------------------------------------------------------


class TestResolveFill:
    """Tests for VisualResolver.resolve_fill."""

    def test_user_override_wins(self):
        attrs = {V_FILL: "#E02A2A"}
        assert VisualResolver.resolve_fill(attrs, "entity") == "#E02A2A"

    def test_entity_hard_fallback(self):
        assert VisualResolver.resolve_fill({}, "entity") == DEFAULT_ENTITY_COLOR

    def test_event_hard_fallback(self):
        assert VisualResolver.resolve_fill({}, "event") == DEFAULT_EVENT_COLOR

    def test_empty_string_override_ignored(self):
        """Empty string should fall through to fallback."""
        assert VisualResolver.resolve_fill({V_FILL: ""}, "entity") != ""

    def test_non_string_override_ignored(self):
        """Non-string values should be ignored."""
        result = VisualResolver.resolve_fill({V_FILL: 12345}, "entity")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# VisualResolver – Border Color
# ---------------------------------------------------------------------------


class TestResolveBorderColor:
    """Tests for VisualResolver.resolve_border_color."""

    def test_user_override_wins(self):
        attrs = {V_BORDER: "#00FF00"}
        assert VisualResolver.resolve_border_color(attrs) == "#00FF00"

    def test_hard_fallback(self):
        assert VisualResolver.resolve_border_color({}) == DEFAULT_BORDER_COLOR


# ---------------------------------------------------------------------------
# VisualResolver – Size / Scale
# ---------------------------------------------------------------------------


class TestResolveSize:
    """Tests for VisualResolver.resolve_size and resolve_scale."""

    def test_default_size_equals_base(self):
        assert VisualResolver.resolve_size({}) == BASE_SIZE

    def test_scale_multiplies_base(self):
        attrs = {V_SIZE_SCALE: 1.5}
        assert VisualResolver.resolve_size(attrs) == int(BASE_SIZE * 1.5)

    def test_scale_clamped_above_zero(self):
        """Scale should be at least 0.1."""
        attrs = {V_SIZE_SCALE: -5.0}
        assert VisualResolver.resolve_scale(attrs) == 0.1

    def test_default_scale_is_1(self):
        assert VisualResolver.resolve_scale({}) == BASE_SCALE

    def test_invalid_scale_uses_default(self):
        attrs = {V_SIZE_SCALE: "not_a_number"}
        assert VisualResolver.resolve_scale(attrs) == BASE_SCALE

    def test_none_scale_uses_default(self):
        attrs = {V_SIZE_SCALE: None}
        assert VisualResolver.resolve_scale(attrs) == BASE_SCALE


# ---------------------------------------------------------------------------
# VisualResolver – Border Width
# ---------------------------------------------------------------------------


class TestResolveBorderWidth:
    """Tests for VisualResolver.resolve_border_width."""

    def test_default_border_width(self):
        assert VisualResolver.resolve_border_width({}) == BASE_BORDER_WIDTH

    def test_user_override(self):
        attrs = {V_BORDER_WIDTH: 4}
        assert VisualResolver.resolve_border_width(attrs) == 4

    def test_clamped_at_zero(self):
        attrs = {V_BORDER_WIDTH: -3}
        assert VisualResolver.resolve_border_width(attrs) == 0

    def test_invalid_value_uses_default(self):
        attrs = {V_BORDER_WIDTH: "bad"}
        assert VisualResolver.resolve_border_width(attrs) == BASE_BORDER_WIDTH


# ---------------------------------------------------------------------------
# VisualResolver – Integration with Entity / Event
# ---------------------------------------------------------------------------


class TestResolverWithDataModels:
    """Tests that VisualResolver works with Entity and Event attributes."""

    def test_entity_with_visual_overrides(self):
        entity = Entity(
            name="Stronghold",
            type="location",
            attributes={V_FILL: "#E02A2A", V_SIZE_SCALE: 1.5, V_BORDER_WIDTH: 4},
        )
        assert VisualResolver.resolve_fill(entity.attributes, "entity") == "#E02A2A"
        assert VisualResolver.resolve_size(entity.attributes) == 36  # 24 * 1.5
        assert VisualResolver.resolve_border_width(entity.attributes) == 4

    def test_event_with_no_overrides(self):
        event = Event(name="Battle", lore_date=100.0)
        assert VisualResolver.resolve_fill(event.attributes, "event") in (
            DEFAULT_EVENT_COLOR,
            "#FF9900",  # theme may override
            "#E68A00",
        )
        assert VisualResolver.resolve_size(event.attributes) == BASE_SIZE


# ---------------------------------------------------------------------------
# UpdateMarkerAttributeCommand
# ---------------------------------------------------------------------------


class TestUpdateMarkerAttributeCommand:
    """Tests for UpdateMarkerAttributeCommand undo/redo."""

    @pytest.fixture
    def mock_db(self):
        from src.services.db_service import DatabaseService

        return MagicMock(spec=DatabaseService)

    @pytest.fixture
    def sample_marker(self):
        return Marker(
            map_id="map1",
            object_id="obj1",
            object_type="entity",
            x=0.5,
            y=0.5,
            id="marker1",
            attributes={"icon": "castle.svg"},
        )

    def test_execute_merges_attributes(self, mock_db, sample_marker):
        from src.commands.marker_commands import UpdateMarkerAttributeCommand

        mock_db.get_marker.return_value = sample_marker
        cmd = UpdateMarkerAttributeCommand(
            "marker1", {V_SIZE_SCALE: 1.5, V_BORDER_WIDTH: 4}
        )
        result = cmd.execute(mock_db)

        assert result.success
        args, _ = mock_db.insert_marker.call_args
        updated = args[0]
        assert updated.attributes[V_SIZE_SCALE] == 1.5
        assert updated.attributes[V_BORDER_WIDTH] == 4
        assert updated.attributes["icon"] == "castle.svg"  # preserved

    def test_undo_restores_previous(self, mock_db, sample_marker):
        from src.commands.marker_commands import UpdateMarkerAttributeCommand

        mock_db.get_marker.return_value = sample_marker
        cmd = UpdateMarkerAttributeCommand("marker1", {V_SIZE_SCALE: 2.0})
        cmd.execute(mock_db)
        cmd.undo(mock_db)

        assert mock_db.insert_marker.call_count == 2
        args, _ = mock_db.insert_marker.call_args
        restored = args[0]
        assert V_SIZE_SCALE not in restored.attributes

    def test_not_found_returns_failure(self, mock_db):
        from src.commands.marker_commands import UpdateMarkerAttributeCommand

        mock_db.get_marker.return_value = None
        cmd = UpdateMarkerAttributeCommand("missing", {V_FILL: "#000"})
        result = cmd.execute(mock_db)

        assert not result.success
        assert "not found" in result.message

    def test_serialization_roundtrip(self):
        from src.commands.marker_commands import UpdateMarkerAttributeCommand

        cmd = UpdateMarkerAttributeCommand("m1", {V_SIZE_SCALE: 1.5})
        data = cmd.to_dict()
        restored = UpdateMarkerAttributeCommand.from_dict(data)
        assert restored.marker_id == "m1"
        assert restored.updates == {V_SIZE_SCALE: 1.5}


# ---------------------------------------------------------------------------
# GraphBuilder integration
# ---------------------------------------------------------------------------


class TestGraphBuilderVisualResolver:
    """Tests that GraphBuilder.prepare_node uses VisualResolver."""

    def test_node_with_visual_overrides(self):
        from src.gui.widgets.graph_view.graph_builder import GraphBuilder

        node = {
            "id": "n1",
            "name": "Stronghold",
            "object_type": "entity",
            "type": "location",
            "attributes": {V_FILL: "#E02A2A", V_SIZE_SCALE: 1.5, V_BORDER_WIDTH: 4},
        }
        result = GraphBuilder.prepare_node(node, "#CCC", "#AAA")

        assert result["color"]["background"] == "#E02A2A"
        assert result["size"] == 36  # 24 * 1.5
        assert result["borderWidth"] == 4

    def test_node_without_overrides_uses_defaults(self):
        from src.gui.widgets.graph_view.graph_builder import GraphBuilder

        node = {
            "id": "n2",
            "name": "Village",
            "object_type": "entity",
            "type": "location",
            "attributes": {},
        }
        result = GraphBuilder.prepare_node(node, "#CCC", "#AAA")

        assert result["size"] == BASE_SIZE
        assert result["borderWidth"] == BASE_BORDER_WIDTH
        assert result["color"]["border"] == DEFAULT_BORDER_COLOR

    def test_node_color_is_dict_with_background_and_border(self):
        from src.gui.widgets.graph_view.graph_builder import GraphBuilder

        node = {"id": "n3", "name": "X", "object_type": "entity"}
        result = GraphBuilder.prepare_node(node, "#CCC", "#AAA")

        assert isinstance(result["color"], dict)
        assert "background" in result["color"]
        assert "border" in result["color"]


# ---------------------------------------------------------------------------
# GraphDataService integration
# ---------------------------------------------------------------------------


class TestGraphDataServiceAttributes:
    """Tests that _entity_to_node / _event_to_node include attributes."""

    def test_entity_node_includes_attributes(self):
        from src.services.graph_data_service import GraphDataService

        svc = GraphDataService.__new__(GraphDataService)
        entity = Entity(
            name="Test",
            type="character",
            attributes={V_FILL: "#FF0000"},
        )
        node = svc._entity_to_node(entity)
        assert "attributes" in node
        assert node["attributes"][V_FILL] == "#FF0000"

    def test_event_node_includes_attributes(self):
        from src.services.graph_data_service import GraphDataService

        svc = GraphDataService.__new__(GraphDataService)
        event = Event(
            name="Battle",
            lore_date=100.0,
            attributes={V_SIZE_SCALE: 2.0},
        )
        node = svc._event_to_node(event)
        assert "attributes" in node
        assert node["attributes"][V_SIZE_SCALE] == 2.0
