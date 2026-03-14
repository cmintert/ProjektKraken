"""RED tests for M3: map drawing tool and interaction_handler must use theme colors.

These tests fail before the fix because drawing_tool.py uses hardcoded
hex strings rather than ThemeManager color tokens.
"""

from unittest.mock import MagicMock

import pytest

from PySide6.QtCore import QPointF
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
    view.scene = scene
    snapping = MagicMock()
    tool = DrawingTool(view, snapping)
    yield tool
    # clean up items so QGraphicsScene can be released safely
    scene.clear()


# ---------------------------------------------------------------------------
# M3a – drawing_tool.py vertex dot fill uses theme["error"]
# ---------------------------------------------------------------------------


def test_drawing_vertex_dot_fill_uses_theme_error(drawing_tool):
    """Vertex dot brush must equal theme["error"], not the hardcoded red."""
    theme = ThemeManager().get_theme()
    expected = theme.get("error", "#e74c3c")

    drawing_tool._drawing_mode = "path"
    drawing_tool._add_drawing_vertex(QPointF(10.0, 10.0))

    dots = [
        it
        for it in drawing_tool._view.scene.items()
        if isinstance(it, QGraphicsEllipseItem)
    ]
    assert dots, "Expected at least one ellipse item (vertex dot) in scene"
    assert dots[0].brush().color().name() == expected.lower(), (
        f"Dot fill is {dots[0].brush().color().name()!r}, expected theme error "
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
        for it in drawing_tool._view.scene.items()
        if isinstance(it, QGraphicsEllipseItem)
    ]
    assert dots, "Expected at least one ellipse item (vertex dot) in scene"
    assert dots[0].pen().color().name() == expected.lower(), (
        f"Dot outline is {dots[0].pen().color().name()!r}, expected theme surface "
        f"color {expected.lower()!r}"
    )


# ---------------------------------------------------------------------------
# M3b – drawing_tool.py preview path pen uses theme["error"]
# ---------------------------------------------------------------------------


def test_drawing_preview_pen_uses_theme_error(drawing_tool):
    """Drawing-preview path pen color must equal theme["error"]."""
    theme = ThemeManager().get_theme()
    expected = theme.get("error", "#e74c3c")

    drawing_tool._drawing_mode = "path"
    drawing_tool._add_drawing_vertex(QPointF(0.0, 0.0))
    # Second call gives a proper rubber-band line
    drawing_tool._update_drawing_preview(QPointF(50.0, 50.0))

    paths = [
        it
        for it in drawing_tool._view.scene.items()
        if isinstance(it, QGraphicsPathItem)
    ]
    assert paths, "Expected a QGraphicsPathItem preview in scene"
    pen_color = paths[0].pen().color().name()
    assert pen_color == expected.lower(), (
        f"Preview pen color is {pen_color!r}, expected theme error color {expected.lower()!r}"
    )


def test_drawing_region_fill_uses_theme_error_with_alpha(drawing_tool):
    """Region preview brush alpha channel must be 40, color base = theme["error"]."""
    theme = ThemeManager().get_theme()
    expected_base = theme.get("error", "#e74c3c")

    drawing_tool._drawing_mode = "region"
    drawing_tool._add_drawing_vertex(QPointF(0.0, 0.0))
    drawing_tool._add_drawing_vertex(QPointF(100.0, 0.0))
    drawing_tool._update_drawing_preview(QPointF(50.0, 50.0))

    paths = [
        it
        for it in drawing_tool._view.scene.items()
        if isinstance(it, QGraphicsPathItem)
    ]
    assert paths, "Expected a QGraphicsPathItem region preview in scene"
    fill = paths[0].brush().color()
    # Alpha should be 40
    assert fill.alpha() == 40, f"Region fill alpha is {fill.alpha()}, expected 40"
    # RGB base color should match theme error (ignoring alpha)
    fill.setAlpha(255)
    assert fill.name() == expected_base.lower(), (
        f"Region fill base color is {fill.name()!r}, expected {expected_base.lower()!r}"
    )


# ---------------------------------------------------------------------------
# M3c – interaction_handler._safe_color_css uses theme["text_dim"] as fallback
# ---------------------------------------------------------------------------


def test_safe_color_css_returns_valid_color_unchanged():
    """A valid CSS color string must pass through unchanged."""
    assert _safe_color_css("#ff0000") == "#ff0000"


def test_safe_color_css_invalid_uses_theme_text_dim():
    """An invalid color string must return theme["text_dim"], not hardcoded grey."""
    theme = ThemeManager().get_theme()
    expected = theme.get("text_dim", "#808080")

    result = _safe_color_css("not-a-color")
    assert result == expected.lower(), (
        f"_safe_color_css fallback is {result!r}, expected theme text_dim "
        f"color {expected.lower()!r}"
    )
