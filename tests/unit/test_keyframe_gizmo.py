from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QGraphicsSceneMouseEvent

# We need to import KeyframeGizmo, but it is inside map_graphics_view.py
# and it might not be exported in __all__, but we can import it directly.
from src.gui.widgets.map.map_graphics_view import (
    GIZMO_SIZE,
    KeyframeGizmo,
    KeyframeItem,
)


@pytest.fixture
def keyframe_item():
    item = MagicMock(spec=KeyframeItem)
    item.marker_id = "test_marker"
    item.t = 0.5
    return item


@pytest.fixture
def gizmo(keyframe_item, qapp):
    return KeyframeGizmo(keyframe_item)


def test_gizmo_mouse_press_clock_icon(gizmo):
    """Test clicking the clock icon on the gizmo."""
    # Simulate clicking on the clock icon (x < GIZMO_SIZE + 1)
    event = MagicMock(spec=QGraphicsSceneMouseEvent)
    # We mock pos() to return a QPointF
    event.pos.return_value = QPointF(GIZMO_SIZE - 2, 5)
    event.button.return_value = Qt.MouseButton.LeftButton

    # Call the event handler
    gizmo.mousePressEvent(event)

    # Check that pos() was called (implicit verification of the fix)
    event.pos.assert_called_once()

    # Should call set_mode("clock") on keyframe_item
    gizmo.keyframe_item.set_mode.assert_called_with("clock")


def test_gizmo_mouse_press_delete_icon(gizmo):
    """Test clicking the delete icon on the gizmo."""
    # Simulate clicking on delete icon (x > GIZMO_SIZE + 1)
    event = MagicMock(spec=QGraphicsSceneMouseEvent)
    # x=10 is > 6+1=7
    event.pos.return_value = QPointF(GIZMO_SIZE + 4, 5)
    event.button.return_value = Qt.MouseButton.LeftButton

    # Call the event handler
    gizmo.mousePressEvent(event)

    # Should call request_delete() on keyframe_item
    gizmo.keyframe_item.request_delete.assert_called_once()
