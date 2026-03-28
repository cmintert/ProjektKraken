import pytest
from PySide6.QtWidgets import QGraphicsView

from src.gui.widgets.map.map_graphics_view import MapGraphicsView


def test_map_view_uses_minimal_viewport_update(qapp):
    """MapGraphicsView should use MinimalViewportUpdate for performance.

    The scale bar is a viewport-space overlay child widget (ScaleBarOverlay),
    not drawn via drawForeground(). Therefore MinimalViewportUpdate is safe
    and preferred — only the scene strips that actually changed are repainted.
    """
    view = MapGraphicsView()
    assert (
        view.viewportUpdateMode()
        == QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate
    ), (
        "MapGraphicsView must use MinimalViewportUpdate; the scale bar is a "
        "viewport overlay widget and does not use drawForeground()"
    )
    view.close()
