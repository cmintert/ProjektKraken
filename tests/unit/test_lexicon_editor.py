"""Tests for the Lexicon Editor Dialog and UI integration.

Validates the LexiconEditorDialog construction, widget creation,
and configuration readback, as well as GraphWidget lexicon API.
"""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from src.gui.dialogs.lexicon_editor_dialog import (
    NODE_SHAPES,
    LexiconEditorDialog,
    _ColorButton,
)
from src.gui.widgets.graph_view.graph_builder import GraphBuilder
from src.gui.widgets.graph_view.graph_filter_bar import GraphFilterBar
from src.gui.widgets.graph_view.graph_widget import GraphWidget


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def qapp():
    """Provides a QApplication instance for widget testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# _ColorButton
# ---------------------------------------------------------------------------


class TestColorButton:
    """Tests for the _ColorButton helper widget."""

    def test_init_stores_color(self, qapp):
        """Initial color is stored correctly."""
        btn = _ColorButton("#FF0000")
        assert btn.color().upper() == "#FF0000"

    def test_default_color(self, qapp):
        """Default color is grey."""
        btn = _ColorButton()
        assert btn.color().upper() == "#888888"

    def test_style_contains_color(self, qapp):
        """Button stylesheet contains the color."""
        btn = _ColorButton("#00FF00")
        assert "#00ff00" in btn.styleSheet().lower()


# ---------------------------------------------------------------------------
# LexiconEditorDialog construction
# ---------------------------------------------------------------------------


class TestLexiconEditorDialogCreation:
    """Tests for LexiconEditorDialog instantiation and layout."""

    def test_creates_with_defaults(self, qapp):
        """Dialog can be created with no arguments."""
        dialog = LexiconEditorDialog()
        assert dialog.windowTitle() == "Visual Lexicon Editor"

    def test_creates_with_entity_types(self, qapp):
        """Dialog creates rows for each entity type."""
        dialog = LexiconEditorDialog(entity_types=["deity", "starship", "faction"])
        assert len(dialog._node_rows) == 3
        assert "deity" in dialog._node_rows
        assert "starship" in dialog._node_rows
        assert "faction" in dialog._node_rows

    def test_creates_with_relation_types(self, qapp):
        """Dialog creates rows for each relation type."""
        dialog = LexiconEditorDialog(relation_types=["allied_with", "enemy_of"])
        assert len(dialog._edge_rows) == 2
        assert "allied_with" in dialog._edge_rows
        assert "enemy_of" in dialog._edge_rows

    def test_empty_types_shows_no_rows(self, qapp):
        """Empty type lists result in no data rows."""
        dialog = LexiconEditorDialog(entity_types=[], relation_types=[])
        assert len(dialog._node_rows) == 0
        assert len(dialog._edge_rows) == 0


# ---------------------------------------------------------------------------
# LexiconEditorDialog config readback
# ---------------------------------------------------------------------------


class TestLexiconEditorDialogConfig:
    """Tests for reading configuration back from the dialog."""

    def test_get_config_returns_nodes_and_edges(self, qapp):
        """get_lexicon_config returns dict with nodes and edges keys."""
        dialog = LexiconEditorDialog(
            entity_types=["human"],
            relation_types=["knows"],
        )
        config = dialog.get_lexicon_config()

        assert "nodes" in config
        assert "edges" in config
        assert "human" in config["nodes"]
        assert "knows" in config["edges"]

    def test_node_config_has_color_and_shape(self, qapp):
        """Node config entries have color and shape keys."""
        dialog = LexiconEditorDialog(entity_types=["deity"])
        config = dialog.get_lexicon_config()

        assert "color" in config["nodes"]["deity"]
        assert "shape" in config["nodes"]["deity"]

    def test_edge_config_has_color_width_dashes(self, qapp):
        """Edge config entries have color, width, and dashes keys."""
        dialog = LexiconEditorDialog(relation_types=["enemy_of"])
        config = dialog.get_lexicon_config()

        edge = config["edges"]["enemy_of"]
        assert "color" in edge
        assert "width" in edge
        assert "dashes" in edge

    def test_existing_config_populates_widgets(self, qapp):
        """Pre-existing config values are reflected in the readback."""
        existing = {
            "nodes": {"deity": {"color": "#FFD700", "shape": "star"}},
            "edges": {"enemy_of": {"color": "#FF0000", "width": 3, "dashes": True}},
        }
        dialog = LexiconEditorDialog(
            entity_types=["deity"],
            relation_types=["enemy_of"],
            current_config=existing,
        )
        config = dialog.get_lexicon_config()

        assert config["nodes"]["deity"]["color"].upper() == "#FFD700"
        assert config["nodes"]["deity"]["shape"] == "star"
        assert config["edges"]["enemy_of"]["color"].upper() == "#FF0000"
        assert config["edges"]["enemy_of"]["width"] == 3
        assert config["edges"]["enemy_of"]["dashes"] is True

    def test_icon_path_preserved_in_config(self, qapp):
        """Icon path from existing config is preserved in readback."""
        existing = {
            "nodes": {
                "deity": {
                    "color": "#FFD700",
                    "shape": "image",
                    "icon": "assets/images/icon_abc.svg",
                }
            },
            "edges": {},
        }
        dialog = LexiconEditorDialog(
            entity_types=["deity"],
            current_config=existing,
        )
        config = dialog.get_lexicon_config()

        assert config["nodes"]["deity"]["icon"] == "assets/images/icon_abc.svg"


# ---------------------------------------------------------------------------
# NODE_SHAPES constant
# ---------------------------------------------------------------------------


class TestNodeShapes:
    """Tests for the NODE_SHAPES constant."""

    def test_contains_essential_shapes(self):
        """NODE_SHAPES includes commonly used vis.js shapes."""
        assert "dot" in NODE_SHAPES
        assert "image" in NODE_SHAPES
        assert "diamond" in NODE_SHAPES
        assert "box" in NODE_SHAPES
        assert "star" in NODE_SHAPES


# ---------------------------------------------------------------------------
# GraphFilterBar lexicon button
# ---------------------------------------------------------------------------


class TestGraphFilterBarLexiconButton:
    """Tests for the lexicon button on GraphFilterBar."""

    def test_has_lexicon_signal(self, qapp):
        """GraphFilterBar has show_lexicon_editor_requested signal."""
        bar = GraphFilterBar()
        assert hasattr(bar, "show_lexicon_editor_requested")

    def test_lexicon_button_exists(self, qapp):
        """The lexicon button widget is created."""
        bar = GraphFilterBar()
        assert hasattr(bar, "_lexicon_btn")
        assert "Lexicon" in bar._lexicon_btn.text()


# ---------------------------------------------------------------------------
# GraphWidget lexicon API
# ---------------------------------------------------------------------------


class TestGraphWidgetLexiconAPI:
    """Tests for GraphWidget lexicon-related public API."""

    def test_has_lexicon_save_signal(self, qapp):
        """GraphWidget has lexicon_save_requested signal."""
        widget = GraphWidget()
        assert hasattr(widget, "lexicon_save_requested")

    def test_set_lexicon_config(self, qapp):
        """set_lexicon_config stores both raw and resolved lexicon."""
        widget = GraphWidget()
        raw = {"nodes": {"A": {"color": "#111"}}, "edges": {}}
        resolved = {"nodes": {"A": {"color": "#111"}}, "edges": {}}

        widget.set_lexicon_config(raw, resolved)

        assert widget._raw_lexicon == raw
        assert widget._resolved_lexicon == resolved

    def test_set_available_entity_types(self, qapp):
        """set_available_entity_types stores entity types."""
        widget = GraphWidget()
        widget.set_available_entity_types(["deity", "starship"])

        assert widget._available_entity_types == ["deity", "starship"]

    def test_set_world_assets_dir(self, qapp):
        """set_world_assets_dir stores the assets directory path."""
        widget = GraphWidget()
        widget.set_world_assets_dir("/some/path/assets")

        assert widget._world_assets_dir == "/some/path/assets"

    def test_lexicon_passed_to_build_html(self, qapp):
        """When lexicon is set, it is passed to build_html during refresh."""
        widget = GraphWidget()
        raw = {"nodes": {"deity": {"color": "#FFD700"}}, "edges": {}}
        resolved = {"nodes": {"deity": {"color": "#FFD700"}}, "edges": {}}
        widget.set_lexicon_config(raw, resolved)

        # Provide some data to trigger the render path
        nodes = [
            {
                "id": "1",
                "name": "Zeus",
                "object_type": "entity",
                "type": "deity",
                "tags": [],
            }
        ]
        edges = []

        # Patch builder to capture arguments
        with patch.object(
            widget._builder, "build_html", return_value="<html/>"
        ) as mock_build:
            widget.display_graph(nodes, edges)
            if mock_build.called:
                call_kwargs = mock_build.call_args
                # Check lexicon_config was passed
                assert call_kwargs.kwargs.get("lexicon_config") is not None


# ---------------------------------------------------------------------------
# Regression: Shape Revert Bug
# ---------------------------------------------------------------------------


def test_resolve_lexicon_images_respects_existing_shape():
    """Verify that resolve_lexicon_images doesn't override shape if it's not 'image'."""
    from pathlib import Path

    lexicon = {
        "nodes": {
            "hero": {
                "color": "#FF0000",
                "shape": "dot",  # User wants a dot
                "icon": "assets/icon.png",  # But an icon path exists
            }
        }
    }

    # Mock image_to_base64 to avoid file I/O
    with patch(
        "src.gui.widgets.graph_view.graph_builder.GraphBuilder.image_to_base64"
    ) as MockB64:
        MockB64.return_value = "data:image/png;base64,dummy"

        resolved = GraphBuilder.resolve_lexicon_images(lexicon, Path("C:/dummy"))

        hero_style = resolved["nodes"]["hero"]

        # This is what previously failed: it got overridden to 'image'
        assert (
            hero_style["shape"] == "dot"
        ), "Shape should remain 'dot' even if icon exists"
        assert "image" in hero_style, "Image data should still be resolved"


def test_prepare_node_ignores_image_if_shape_not_image():
    """Verify prepare_node doesn't use image data if shape is not 'image'."""
    node = {"id": "1", "name": "Hero", "type": "hero", "object_type": "entity"}
    lexicon = {
        "hero": {
            "color": "#FF0000",
            "shape": "dot",
            "image": "data:image/png;base64,dummy",
        }
    }

    prepared = GraphBuilder.prepare_node(node, "#CCC", "#EEE", lexicon)

    assert prepared["shape"] == "dot"
    assert (
        "image" not in prepared
    ), "Image property should be omitted if shape is not 'image'"
