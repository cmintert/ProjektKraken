"""Tests for the visual styling integration fixes.

Verifies:
- Graph nodes with _v_fill override are not clobbered by lexicon color
- DataHandler triggers marker reload for visual update commands
- Lexicon preview forces full rebuild
"""

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

from src.core.style_constants import V_BORDER_WIDTH, V_FILL, V_SIZE_SCALE
from src.gui.widgets.graph_view.graph_builder import GraphBuilder


@pytest.fixture(scope="session", autouse=True)
def qapp():
    """Ensure a QApplication exists for widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# Fix 2: Lexicon respects per-entity _v_fill user overrides
# ---------------------------------------------------------------------------


class TestLexiconVsFillOverride:
    """Ensure per-entity _v_fill takes priority over lexicon type color."""

    def test_user_v_fill_takes_priority_over_lexicon(self) -> None:
        """Entity with _v_fill should NOT be overridden by lexicon color."""
        node = {
            "id": "n1",
            "name": "Red Castle",
            "type": "Location",
            "object_type": "entity",
            "attributes": {V_FILL: "#E02A2A"},
        }
        lexicon = {"Location": {"color": "#0000FF", "shape": "dot"}}

        result = GraphBuilder.prepare_node(node, "#AAA", "#BBB", lexicon=lexicon)

        # User override should win
        assert result["color"]["background"] == "#E02A2A"
        # Shape should still come from lexicon
        assert result["shape"] == "dot"

    def test_lexicon_color_applied_when_no_user_override(self) -> None:
        """Entity without _v_fill should use lexicon color."""
        node = {
            "id": "n2",
            "name": "Blue Village",
            "type": "Location",
            "object_type": "entity",
            "attributes": {},
        }
        lexicon = {"Location": {"color": "#0000FF", "shape": "star"}}

        result = GraphBuilder.prepare_node(node, "#AAA", "#BBB", lexicon=lexicon)

        # Lexicon color should apply
        assert result["color"]["background"] == "#0000FF"
        assert result["shape"] == "star"

    def test_lexicon_color_applied_when_attributes_missing(self) -> None:
        """Entity with no attributes dict should still use lexicon color."""
        node = {
            "id": "n3",
            "name": "Unknown Place",
            "type": "Location",
            "object_type": "entity",
        }
        lexicon = {"Location": {"color": "#00FF00"}}

        result = GraphBuilder.prepare_node(node, "#AAA", "#BBB", lexicon=lexicon)
        assert result["color"]["background"] == "#00FF00"

    def test_no_lexicon_uses_resolver(self) -> None:
        """Without lexicon, VisualResolver fallback applies."""
        node = {
            "id": "n4",
            "name": "Plain Entity",
            "type": "Location",
            "object_type": "entity",
            "attributes": {V_FILL: "#FF00FF"},
        }

        result = GraphBuilder.prepare_node(node, "#AAA", "#BBB", lexicon=None)
        assert result["color"]["background"] == "#FF00FF"

    def test_user_v_fill_with_other_visual_attrs(self) -> None:
        """Entity with _v_fill and other visual attrs keeps all overrides."""
        node = {
            "id": "n5",
            "name": "Scaled Castle",
            "type": "Location",
            "object_type": "entity",
            "attributes": {
                V_FILL: "#E02A2A",
                V_SIZE_SCALE: 1.5,
                V_BORDER_WIDTH: 4,
            },
        }
        lexicon = {"Location": {"color": "#0000FF"}}

        result = GraphBuilder.prepare_node(node, "#AAA", "#BBB", lexicon=lexicon)

        assert result["color"]["background"] == "#E02A2A"
        assert result["size"] == 36  # 24 * 1.5
        assert result["borderWidth"] == 4


# ---------------------------------------------------------------------------
# Fix 1b: DataHandler triggers marker reload for visual commands
# ---------------------------------------------------------------------------


class TestDataHandlerMarkerVisualReload:
    """Ensure visual update commands trigger marker reload."""

    @pytest.fixture
    def data_handler(self):
        from src.app.data_handler import DataHandler

        handler = DataHandler()
        return handler

    @pytest.fixture
    def success_result(self):
        from src.commands.base_command import CommandResult

        return CommandResult

    def test_update_marker_attribute_triggers_reload(
        self, data_handler, success_result
    ):
        """UpdateMarkerAttributeCommand should trigger reload_markers."""
        spy = MagicMock()
        data_handler.reload_markers_for_current_map.connect(spy)

        result = success_result(
            success=True,
            message="OK",
            command_name="UpdateMarkerAttributeCommand",
        )
        data_handler.on_command_finished(result)

        spy.assert_called()

    def test_update_marker_color_triggers_reload(self, data_handler, success_result):
        """UpdateMarkerColorCommand should trigger reload_markers."""
        spy = MagicMock()
        data_handler.reload_markers_for_current_map.connect(spy)

        result = success_result(
            success=True,
            message="OK",
            command_name="UpdateMarkerColorCommand",
        )
        data_handler.on_command_finished(result)

        spy.assert_called()

    def test_update_marker_icon_triggers_reload(self, data_handler, success_result):
        """UpdateMarkerIconCommand should trigger reload_markers."""
        spy = MagicMock()
        data_handler.reload_markers_for_current_map.connect(spy)

        result = success_result(
            success=True,
            message="OK",
            command_name="UpdateMarkerIconCommand",
        )
        data_handler.on_command_finished(result)

        spy.assert_called()

    def test_update_marker_position_does_not_trigger_reload(
        self, data_handler, success_result
    ):
        """UpdateMarkerCommand (position) should NOT trigger reload_markers."""
        spy = MagicMock()
        data_handler.reload_markers_for_current_map.connect(spy)

        result = success_result(
            success=True,
            message="OK",
            command_name="UpdateMarkerCommand",
        )
        data_handler.on_command_finished(result)

        spy.assert_not_called()


# ---------------------------------------------------------------------------
# Fix 3: Lexicon preview forces full rebuild
# ---------------------------------------------------------------------------


class TestLexiconPreviewForcesRebuild:
    """Ensure _on_lexicon_preview_requested sets _is_renderer_ready=False."""

    def test_preview_resets_renderer_ready(self, qapp):
        """Lexicon preview must force full HTML rebuild."""
        from src.gui.widgets.graph_view.graph_widget import GraphWidget

        widget = GraphWidget()
        widget._is_renderer_ready = True

        # Call preview with a minimal config
        widget._on_lexicon_preview_requested({"nodes": {}, "edges": {}})

        assert widget._is_renderer_ready is False
        widget.close()
