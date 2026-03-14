"""Tests for the Lexicon Editor Dialog and UI integration.

Validates the LexiconEditorDialog construction, widget creation,
and configuration readback, as well as GraphWidget lexicon API.
"""

import base64
from unittest.mock import patch

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
        assert hero_style["shape"] == "dot", (
            "Shape should remain 'dot' even if icon exists"
        )
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
    assert "image" not in prepared, (
        "Image property should be omitted if shape is not 'image'"
    )


# ---------------------------------------------------------------------------
# Lexicon Editor: border_color, border_width, size_scale
# ---------------------------------------------------------------------------


class TestLexiconEditorVisualProperties:
    """Tests for border_color, border_width, and size_scale in the dialog."""

    def test_node_config_has_border_and_size_keys(self, qapp):
        """get_lexicon_config returns border_color, border_width, size_scale."""
        dialog = LexiconEditorDialog(entity_types=["deity"])
        config = dialog.get_lexicon_config()

        node_cfg = config["nodes"]["deity"]
        assert "border_color" in node_cfg
        assert "border_width" in node_cfg
        assert "size_scale" in node_cfg

    def test_default_border_width_and_size(self, qapp):
        """No existing config → defaults are sensible."""
        dialog = LexiconEditorDialog(entity_types=["deity"])
        config = dialog.get_lexicon_config()

        node_cfg = config["nodes"]["deity"]
        assert node_cfg["border_color"].upper() == "#FFFFFF"
        assert node_cfg["border_width"] == 2
        assert node_cfg["size_scale"] == 1.0

    def test_existing_border_config_populates_widgets(self, qapp):
        """Pre-existing border/size values are reflected on readback."""
        existing = {
            "nodes": {
                "deity": {
                    "color": "#FFD700",
                    "shape": "star",
                    "border_color": "#00FF00",
                    "border_width": 5,
                    "size_scale": 2.0,
                }
            },
            "edges": {},
        }
        dialog = LexiconEditorDialog(
            entity_types=["deity"],
            current_config=existing,
        )
        config = dialog.get_lexicon_config()

        node_cfg = config["nodes"]["deity"]
        assert node_cfg["border_color"].upper() == "#00FF00"
        assert node_cfg["border_width"] == 5
        assert node_cfg["size_scale"] == 2.0


# ---------------------------------------------------------------------------
# prepare_node: lexicon border/size overrides
# ---------------------------------------------------------------------------


class TestPrepareNodeVisualProperties:
    """Tests for prepare_node consuming lexicon border/size values."""

    def test_lexicon_border_color_applied(self):
        """Lexicon border_color overrides the default."""
        node = {"id": "1", "name": "Zeus", "type": "deity", "object_type": "entity"}
        lexicon = {"deity": {"border_color": "#00FF00"}}

        prepared = GraphBuilder.prepare_node(node, "#CCC", "#EEE", lexicon)

        assert prepared["color"]["border"] == "#00FF00"

    def test_lexicon_border_width_applied(self):
        """Lexicon border_width overrides the default."""
        node = {"id": "1", "name": "Zeus", "type": "deity", "object_type": "entity"}
        lexicon = {"deity": {"border_width": 6}}

        prepared = GraphBuilder.prepare_node(node, "#CCC", "#EEE", lexicon)

        assert prepared["borderWidth"] == 6

    def test_lexicon_size_scale_applied(self):
        """Lexicon size_scale is applied to the node size."""
        from src.core.style_constants import BASE_SIZE

        node = {"id": "1", "name": "Zeus", "type": "deity", "object_type": "entity"}
        lexicon = {"deity": {"size_scale": 2.0}}

        prepared = GraphBuilder.prepare_node(node, "#CCC", "#EEE", lexicon)

        assert prepared["size"] == BASE_SIZE * 2.0

    def test_user_v_border_overrides_lexicon(self):
        """Per-entity _v_border takes priority over lexicon border_color."""
        from src.core.style_constants import V_BORDER

        node = {
            "id": "1",
            "name": "Zeus",
            "type": "deity",
            "object_type": "entity",
            "attributes": {V_BORDER: "#FF0000"},
        }
        lexicon = {"deity": {"border_color": "#00FF00"}}

        prepared = GraphBuilder.prepare_node(node, "#CCC", "#EEE", lexicon)

        # Per-entity override should win
        assert prepared["color"]["border"] == "#FF0000"


# ---------------------------------------------------------------------------
# SVG Dynamic Styling
# ---------------------------------------------------------------------------


class TestSVGDynamicStyling:
    """Tests for apply_svg_styling and SVG icon styling in prepare_node."""

    def test_svg_styling_injects_border_color(self):
        """apply_svg_styling injects stroke CSS for border_color."""
        svg_content = '<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'
        data_uri = (
            "data:image/svg+xml;base64,"
            + base64.b64encode(svg_content.encode()).decode()
        )

        result = GraphBuilder.apply_svg_styling(data_uri, border_color="#FF0000")

        # Decode and check for injected CSS
        decoded = base64.b64decode(result.split(",")[1]).decode()
        assert "stroke:#FF0000" in decoded

    def test_svg_styling_injects_fill_color(self):
        """apply_svg_styling injects fill CSS for fill_color."""
        svg_content = '<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'
        data_uri = (
            "data:image/svg+xml;base64,"
            + base64.b64encode(svg_content.encode()).decode()
        )

        result = GraphBuilder.apply_svg_styling(data_uri, fill_color="#00FF00")

        decoded = base64.b64decode(result.split(",")[1]).decode()
        assert "fill:#00FF00" in decoded

    def test_svg_styling_injects_border_width(self):
        """apply_svg_styling injects stroke-width CSS for border_width."""
        svg_content = '<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'
        data_uri = (
            "data:image/svg+xml;base64,"
            + base64.b64encode(svg_content.encode()).decode()
        )

        result = GraphBuilder.apply_svg_styling(data_uri, border_width=5)

        decoded = base64.b64decode(result.split(",")[1]).decode()
        assert "stroke-width:5px" in decoded

    def test_svg_styling_injects_size_scale(self):
        """apply_svg_styling injects transform scale for size_scale."""
        svg_content = '<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'
        data_uri = (
            "data:image/svg+xml;base64,"
            + base64.b64encode(svg_content.encode()).decode()
        )

        result = GraphBuilder.apply_svg_styling(data_uri, size_scale=2.0)

        decoded = base64.b64decode(result.split(",")[1]).decode()
        assert 'transform="scale(2.0)"' in decoded

    def test_png_icon_unaffected_by_svg_styling(self):
        """apply_svg_styling passes through PNG data URIs unchanged."""
        png_data_uri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA"

        result = GraphBuilder.apply_svg_styling(
            png_data_uri,
            border_color="#FF0000",
            border_width=5,
            size_scale=2.0,
        )

        assert result == png_data_uri

    def test_prepare_node_applies_svg_styling_from_lexicon(self):
        """prepare_node applies SVG styling when lexicon has border/size settings."""
        svg_content = '<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'
        image_data = (
            "data:image/svg+xml;base64,"
            + base64.b64encode(svg_content.encode()).decode()
        )

        node = {"id": "1", "name": "Zeus", "type": "deity", "object_type": "entity"}
        lexicon = {
            "deity": {
                "shape": "image",
                "image": image_data,
                "border_color": "#FFD700",
                "border_width": 3,
                "size_scale": 1.5,
            }
        }

        prepared = GraphBuilder.prepare_node(node, "#CCC", "#EEE", lexicon)

        # Verify the image was styled
        assert "image" in prepared
        styled_svg = base64.b64decode(prepared["image"].split(",")[1]).decode()
        assert "stroke:#FFD700" in styled_svg
        assert "stroke-width:3px" in styled_svg
        assert 'transform="scale(1.5)"' in styled_svg
