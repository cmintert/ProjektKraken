"""Small reusable graphics handles for direct geometry editing."""

import math
from typing import Any, Callable, Generic, TypeVar

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem

from src.app.constants import (
    MAP_LAYER_Z_UI_OVERLAY,
    MAP_MIDPOINT_GHOST_OPACITY,
    MAP_MIDPOINT_HANDLE_BORDER_COLOR,
    MAP_MIDPOINT_HANDLE_COLOR,
    MAP_MIDPOINT_HANDLE_RADIUS,
    MAP_MIDPOINT_HOVER_OPACITY,
    MAP_SNAP_RADIUS_PX,
    MAP_VERTEX_HANDLE_BORDER_COLOR,
    MAP_VERTEX_HANDLE_COLOR,
    MAP_VERTEX_HANDLE_RADIUS,
)

HandleIdT = TypeVar("HandleIdT")


class DraggableEditHandle(QGraphicsEllipseItem, Generic[HandleIdT]):
    """Draggable point handle with optional selection and deletion callbacks."""

    def __init__(
        self,
        handle_id: HandleIdT,
        move_callback: Callable[[HandleIdT, QPointF], None],
        delete_callback: Callable[[HandleIdT], None],
        *,
        select_callback: Callable[[HandleIdT], None] | None = None,
        fill_color: str = MAP_VERTEX_HANDLE_COLOR,
        border_color: str = MAP_VERTEX_HANDLE_BORDER_COLOR,
    ) -> None:
        """Create a transform-independent point handle."""
        radius = MAP_VERTEX_HANDLE_RADIUS
        super().__init__(-radius, -radius, radius * 2, radius * 2)
        self.handle_id = handle_id
        self.index = handle_id
        self._move_callback = move_callback
        self._delete_callback = delete_callback
        self._select_callback = select_callback
        self._notifications_enabled = False
        self.setBrush(QBrush(QColor(fill_color)))
        self.setPen(QPen(QColor(border_color), 1))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setAcceptedMouseButtons(
            Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton
        )
        self.setZValue(MAP_LAYER_Z_UI_OVERLAY + 1)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        """Notify the editor whenever the handle position changes."""
        if (
            change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged
            and self._notifications_enabled
        ):
            self._move_callback(self.handle_id, self.pos())
        return super().itemChange(change, value)

    def set_notifications_enabled(self, enabled: bool) -> None:
        """Control callbacks during programmatic position synchronization."""
        self._notifications_enabled = enabled

    def mousePressEvent(self, event: Any) -> None:
        """Select on left-click or request deletion on right-click."""
        if event.button() == Qt.MouseButton.RightButton:
            self._delete_callback(self.handle_id)
            event.accept()
            return
        if self._select_callback is not None:
            self._select_callback(self.handle_id)
        super().mousePressEvent(event)


class MidpointEditHandle(QGraphicsEllipseItem, Generic[HandleIdT]):
    """Draggable ghost handle that promotes a segment midpoint on release."""

    def __init__(
        self,
        segment_id: HandleIdT,
        insert_callback: Callable[[HandleIdT, QPointF], None],
    ) -> None:
        """Create a transform-independent midpoint insertion handle."""
        radius = MAP_MIDPOINT_HANDLE_RADIUS
        super().__init__(-radius, -radius, radius * 2, radius * 2)
        self.segment_id = segment_id
        self.segment_index = segment_id
        self._insert_callback = insert_callback
        self.setBrush(QBrush(QColor(MAP_MIDPOINT_HANDLE_COLOR)))
        self.setPen(QPen(QColor(MAP_MIDPOINT_HANDLE_BORDER_COLOR), 1))
        self.setOpacity(MAP_MIDPOINT_GHOST_OPACITY)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setZValue(MAP_LAYER_Z_UI_OVERLAY)

    def hoverEnterEvent(self, event: Any) -> None:
        """Highlight the insertion handle on hover."""
        self.setOpacity(MAP_MIDPOINT_HOVER_OPACITY)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: Any) -> None:
        """Restore ghost opacity when hover ends."""
        self.setOpacity(MAP_MIDPOINT_GHOST_OPACITY)
        super().hoverLeaveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        """Promote the midpoint at its final spatial position."""
        super().mouseReleaseEvent(event)
        self._insert_callback(self.segment_id, self.scenePos())


def snap_to_edit_handles(
    moving_id: HandleIdT,
    scene_pos: QPointF,
    handles: list[DraggableEditHandle[HandleIdT]],
    view_scale: float,
) -> QPointF:
    """Snap to another edit handle using the established screen-pixel radius."""
    scale = view_scale if view_scale > 0 else 1.0
    snap_radius = MAP_SNAP_RADIUS_PX / scale
    best_distance = snap_radius
    best_position = QPointF(scene_pos)
    for handle in handles:
        if handle.handle_id == moving_id:
            continue
        delta_x = handle.pos().x() - scene_pos.x()
        delta_y = handle.pos().y() - scene_pos.y()
        distance = math.hypot(delta_x, delta_y)
        if distance < best_distance:
            best_distance = distance
            best_position = QPointF(handle.pos())
    return best_position
