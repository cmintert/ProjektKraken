"""Theme roles for map drawing overlays and interaction styles."""

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsScene

from src.core.theme_manager import ThemeManager
from src.gui.widgets.map.drawing_tool import DrawingTool
from src.gui.widgets.map.interaction_handler import _safe_color_css

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def drawing_tool(qapp):
    """DrawingTool wired to a real QGraphicsScene via a mock view."""
    scene = QGraphicsScene()
    view = MagicMock()
    view.graphics_scene = scene
    snapping = MagicMock()
    tool = DrawingTool(view, snapping)
    yield tool
    # clean up items so QGraphicsScene can be released safely
    scene.clear()


# ---------------------------------------------------------------------------
# Drawing vertex
# ---------------------------------------------------------------------------


def test_drawing_vertex_dot_fill_uses_theme_selection(drawing_tool):
    """A vertex uses the same selection role as its geometry preview."""
    theme = ThemeManager().get_theme()
    expected = theme["selection_bg"]

    drawing_tool._drawing_mode = "path"
    drawing_tool._add_drawing_vertex(QPointF(10.0, 10.0))

    dots = [
        it
        for it in drawing_tool._view.graphics_scene.items()
        if isinstance(it, QGraphicsEllipseItem)
    ]
    assert dots, "Expected at least one ellipse item (vertex dot) in scene"
    assert dots[0].brush().color().name() == expected.lower(), (
        f"Dot fill is {dots[0].brush().color().name()!r}, expected selection "
        f"color {expected.lower()!r}"
    )


def test_drawing_vertex_dot_outline_uses_theme_surface(drawing_tool):
    """Vertex dot outline pen must equal theme["surface"] (not hardcoded #FFFFFF)."""
    theme = ThemeManager().get_theme()
    expected = theme.get("surface", "#1A1A1A")

    drawing_tool._drawing_mode = "path"
    drawing_tool._add_drawing_vertex(QPointF(10.0, 10.0))

    dots = [
        it
        for it in drawing_tool._view.graphics_scene.items()
        if isinstance(it, QGraphicsEllipseItem)
    ]
    assert dots, "Expected at least one ellipse item (vertex dot) in scene"
    assert dots[0].pen().color().name() == expected.lower(), (
        f"Dot outline is {dots[0].pen().color().name()!r}, expected theme surface "
        f"color {expected.lower()!r}"
    )


# ---------------------------------------------------------------------------
# Drawing preview
# ---------------------------------------------------------------------------


def test_drawing_preview_pen_uses_theme_selection(drawing_tool):
    """A preview path uses the selection color with a dashed stroke."""
    theme = ThemeManager().get_theme()
    expected = theme["selection_bg"]

    drawing_tool._drawing_mode = "path"
    drawing_tool._add_drawing_vertex(QPointF(0.0, 0.0))
    # Second call gives a proper rubber-band line
    drawing_tool._update_drawing_preview(QPointF(50.0, 50.0))

    paths = [
        it
        for it in drawing_tool._view.graphics_scene.items()
        if isinstance(it, QGraphicsPathItem)
    ]
    assert paths, "Expected a QGraphicsPathItem preview in scene"
    pen_color = paths[0].pen().color().name()
    assert pen_color == expected.lower(), (
        f"Preview pen color is {pen_color!r}, expected selection color {expected.lower()!r}"
    )
    assert paths[0].pen().style() == Qt.PenStyle.DashLine


def test_drawing_region_fill_uses_patterned_theme_selection(drawing_tool):
    """The selection-colored pattern leaves the underlying map visible."""
    theme = ThemeManager().get_theme()
    expected_base = theme["selection_bg"]

    drawing_tool._drawing_mode = "region"
    drawing_tool._add_drawing_vertex(QPointF(0.0, 0.0))
    drawing_tool._add_drawing_vertex(QPointF(100.0, 0.0))
    drawing_tool._update_drawing_preview(QPointF(50.0, 50.0))

    paths = [
        it
        for it in drawing_tool._view.graphics_scene.items()
        if isinstance(it, QGraphicsPathItem)
    ]
    assert paths, "Expected a QGraphicsPathItem region preview in scene"
    brush = paths[0].brush()
    assert brush.style() == Qt.BrushStyle.Dense6Pattern
    assert brush.color().name() == expected_base.lower()


# ---------------------------------------------------------------------------
# M3c – interaction_handler._safe_color_css uses theme["text_dim"] as fallback
# ---------------------------------------------------------------------------


def test_safe_color_css_returns_valid_color_unchanged():
    """A valid CSS color string must pass through unchanged."""
    assert _safe_color_css("#ff0000") == "#ff0000"


def test_safe_color_css_preserves_alpha_when_requested():
    """Region style editing must not turn a translucent fill opaque."""
    assert _safe_color_css("#403498db", preserve_alpha=True) == "#403498db"


def test_safe_color_css_invalid_uses_theme_text_dim():
    """An invalid color string must return theme["text_dim"], not hardcoded grey."""
    theme = ThemeManager().get_theme()
    expected = theme.get("text_dim", "#808080")

    result = _safe_color_css("not-a-color")
    assert result == expected.lower(), (
        f"_safe_color_css fallback is {result!r}, expected theme text_dim "
        f"color {expected.lower()!r}"
    )
