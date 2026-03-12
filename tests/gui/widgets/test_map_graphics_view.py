import pytest
from PySide6.QtWidgets import QGraphicsView

from src.gui.widgets.map.map_graphics_view import MapGraphicsView


def test_map_view_uses_full_viewport_update(qapp):
    """MapGraphicsView should use FullViewportUpdate to avoid scale-bar smear.

    The scale bar is painted in device-space inside drawForeground() after
    resetting the painter transform. With SmartViewportUpdate only the
    newly-exposed scene strip is repainted during pan, leaving stale
    overlay pixels. Using FullViewportUpdate forces a full repaint and
    prevents the smear.
    """
    view = MapGraphicsView()
    assert (
        view.viewportUpdateMode()
        == QGraphicsView.ViewportUpdateMode.FullViewportUpdate
    ), (
        "MapGraphicsView must use FullViewportUpdate to prevent scale-bar "
        "smearing during pan"
    )
    view.close()
