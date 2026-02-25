from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QGraphicsScene, QGraphicsSceneMouseEvent

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
    scene = QGraphicsScene()
    g = KeyframeGizmo(keyframe_item)
    scene.addItem(g)
    g._test_scene = scene  # prevent GC
    return g


def test_gizmo_mouse_press_clock_icon(gizmo):
    """Test clicking the clock icon on the gizmo."""
    # Use the clock icon's actual scene position for a valid hit
    clock_center = gizmo.clock_icon.mapToScene(
        gizmo.clock_icon.rect().center()
    )
    event = MagicMock(spec=QGraphicsSceneMouseEvent)
    event.scenePos.return_value = clock_center
    event.button.return_value = Qt.MouseButton.LeftButton
    event.accept = MagicMock()

    gizmo.mousePressEvent(event)

    gizmo.keyframe_item.set_mode.assert_called_with("clock")
    event.accept.assert_called_once()


def test_gizmo_mouse_press_delete_icon(gizmo):
    """Test clicking the delete icon on the gizmo."""
    # Use the delete icon's actual scene position for a valid hit
    delete_center = gizmo.delete_icon.mapToScene(
        gizmo.delete_icon.rect().center()
    )
    event = MagicMock(spec=QGraphicsSceneMouseEvent)
    event.scenePos.return_value = delete_center
    event.button.return_value = Qt.MouseButton.LeftButton
    event.accept = MagicMock()

    gizmo.mousePressEvent(event)

    gizmo.keyframe_item.request_delete.assert_called_once()
    event.accept.assert_called_once()
