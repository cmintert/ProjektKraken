import pytest
from PySide6.QtCore import QMimeData, QPoint, QRectF, Qt
from PySide6.QtGui import (
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QImage,
    QPixmap,
)
from PySide6.QtWidgets import QGraphicsPixmapItem

from src.gui.widgets.map.map_graphics_view import MapGraphicsView
from src.gui.widgets.unified_list import KRAKEN_ITEM_MIME_TYPE


@pytest.fixture
def view(qtbot):
    view = MapGraphicsView()
    qtbot.addWidget(view)

    # Create test pixmap
    test_image = QImage(100, 100, QImage.Format.Format_RGB32)
    test_image.fill(Qt.GlobalColor.white)
    pixmap = QPixmap.fromImage(test_image)

    # Add pixmap to scene
    view.pixmap_item = QGraphicsPixmapItem(pixmap)
    view.scene.addItem(view.pixmap_item)
    view.coord_system.set_scene_rect(QRectF(0, 0, 100, 100))
    view.show()

    return view


def test_drag_overlay_visibility(view, qtbot):
    """Test that the blue overlay shows and hides correctly during drag-and-drop."""
    # Initially hidden
    assert view._drop_hint_overlay.isHidden() is True

    # Mock contains to ensure we stay in bounds for the first part
    view.pixmap_item.contains = lambda p: True

    # Simulate drag enter with correct MIME type
    mime_data = QMimeData()
    mime_data.setData(
        KRAKEN_ITEM_MIME_TYPE, b'{"id": "1", "type": "entity", "name": "Test"}'
    )

    enter_event = QDragEnterEvent(
        QPoint(10, 10),
        Qt.DropAction.MoveAction,
        mime_data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    view.dragEnterEvent(enter_event)

    # Should be visible
    assert view._drop_hint_overlay.isHidden() is False

    # Simulate drag move inside map
    move_event = QDragMoveEvent(
        QPoint(50, 50),
        Qt.DropAction.MoveAction,
        mime_data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    view.dragMoveEvent(move_event)
    assert view._drop_hint_overlay.isHidden() is False

    # Simulate drag move outside map bounds logic
    view.pixmap_item.contains = lambda p: False  # Force out of bounds
    view.dragMoveEvent(move_event)
    assert view._drop_hint_overlay.isHidden() is True

    # Back in bounds
    view.pixmap_item.contains = lambda p: True
    view.dragMoveEvent(move_event)
    assert view._drop_hint_overlay.isHidden() is False

    # Drag leave
    leave_event = QDragLeaveEvent()
    view.dragLeaveEvent(leave_event)
    assert view._drop_hint_overlay.isHidden() is True

    # Drop event
    view.dragEnterEvent(enter_event)
    assert view._drop_hint_overlay.isHidden() is False

    drop_event = QDropEvent(
        QPoint(50, 50),
        Qt.DropAction.MoveAction,
        mime_data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    view.dropEvent(drop_event)
    assert view._drop_hint_overlay.isHidden() is True
