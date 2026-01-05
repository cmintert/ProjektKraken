from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QCursor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QGraphicsPathItem, QMenu

# Constants for visuals
HANDLE_SIZE = 16  # Increased from 8 for easier clicking
COLOR_START = QColor("#2ECC71")  # Green
COLOR_END = QColor("#E74C3C")  # Red
COLOR_PATH_NODE = QColor("#BDC3C7")  # Grey/White
COLOR_PATH_LINE = QColor("#BDC3C7")
COLOR_SELECTED = QColor("#F1C40F")  # Yellow highlight


class HandleItem(QGraphicsObject):
    """
    Visual handle for a single keyframe on the motion path.
    Interactive: Can be dragged to adjust spatial position.
    """

    # Signals
    position_changed = Signal(float, float, float)  # t, new_x, new_y
    duplicate_requested = Signal(float, float, float)  # original_t, new_x, new_y
    delete_requested = Signal(float)  # t
    double_clicked = Signal(float)  # t
    clicked = Signal(object)  # Emits self

    def __init__(
        self,
        t: float,
        x: float,
        y: float,
        kf_type: str = "path",
        parent: Optional[QGraphicsItem] = None,
    ) -> None:
        super().__init__(parent)
        self.t = t
        self.x = x
        self.y = y
        self.kf_type = kf_type

        # Configure flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)

        self.setAcceptHoverEvents(True)
        self._is_hovered = False

        # Set cursor to indicate draggability
        self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))

    def boundingRect(self) -> QRectF:
        # Return a square bounding rect centered at 0,0
        half = HANDLE_SIZE / 2
        return QRectF(-half, -half, HANDLE_SIZE, HANDLE_SIZE)

    def paint(
        self, painter: QPainter, option: Any, widget: Optional[Any] = None
    ) -> None:
        """Draws the handle as a diamond."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Determine color based on type and state
        if self.kf_type == "start":
            color = COLOR_START
        elif self.kf_type == "end":
            color = COLOR_END
        else:
            color = COLOR_PATH_NODE

        if self.isSelected() or self._is_hovered:
            color = color.lighter(130)

        # Draw Diamond
        painter.setBrush(QBrush(color))
        # Highlight border if selected
        if self.isSelected():
            painter.setPen(QPen(Qt.GlobalColor.white, 2))
        else:
            painter.setPen(QPen(Qt.GlobalColor.darkGray, 1))

        # Draw rotated rect (diamond)
        painter.save()
        painter.rotate(45)
        r = HANDLE_SIZE / 2
        painter.drawRect(-r, -r, HANDLE_SIZE, HANDLE_SIZE)
        painter.restore()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        """Handle item changes to redraw path during drag."""
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            # Redraw path line during drag (don't emit signals - that happens on release)
            parent = self.parentItem()
            if parent and hasattr(parent, "_redraw_path_from_handles"):
                # Call parent's redraw method to update path visually
                parent._redraw_path_from_handles()
        return super().itemChange(change, value)

    def mousePressEvent(self, event: Any) -> None:
        super().mousePressEvent(event)
        self.clicked.emit(self)

    def mouseReleaseEvent(self, event: Any) -> None:
        super().mouseReleaseEvent(event)
        # Calculate new normalized position
        if self.scene() and self.parentItem():
            # Parent is MotionPathItem.
            # HandleItem doesn't inherently know normalized coords.
            # We emit scene position and 't', let View/Widget normalize.

            scene_pos = self.scenePos()

            # Check for modifiers (Ctrl+Drag to duplicate)
            modifiers = event.modifiers()
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                self.duplicate_requested.emit(self.t, scene_pos.x(), scene_pos.y())
            else:
                self.position_changed.emit(self.t, scene_pos.x(), scene_pos.y())

    def mouseDoubleClickEvent(self, event: Any) -> None:
        """Handle double click to edit."""
        super().mouseDoubleClickEvent(event)
        self.double_clicked.emit(self.t)

    def contextMenuEvent(self, event: Any) -> None:
        """Handle context menu for deleting keyframes."""
        menu = QMenu()
        edit_action = menu.addAction("Edit Keyframe")
        menu.addSeparator()
        delete_action = menu.addAction("Delete Keyframe")

        action = menu.exec(event.screenPos())
        if action == delete_action:
            self.delete_requested.emit(self.t)
        elif action == edit_action:
            self.double_clicked.emit(self.t)


class MotionPathItem(QObject, QGraphicsPathItem):
    """
    Visualizes the temporal path of a marker using a dotted line.
    Manages child HandleItems.

    Note: Inherits from QObject first to enable Signal support, then
    QGraphicsPathItem for drawing capabilities.
    """

    # Signals
    keyframe_moved = Signal(str, float, float, float)  # marker_id, t, scene_x, scene_y
    # Duplicate signal assumes implicit create-at-current-time logic in drag, but
    # Ctrl+Drag usually implies duplication.
    # Actually, duplicated keyframe time is not determined by drag?
    # No, typically Ctrl+Drag moves the *copy* to the new spatial location.
    # But what is the TIME of the new keyframe?
    # If we are dragging spatially, we are usually at the same time?
    # Ah, standard motion path editors (After Effects etc) let you drag spatially.
    # But keyframes are temporal points.
    # If I drag a handle (which exists at T=100) and hold Ctrl, I probably
    # want to create a NEW keyframe at ... some other time?
    # Actually, in MapWidget "Record Mode", dragging *creates* a keyframe
    # at current_time. If I drag a *handle*, I am editing a keyframe at
    # `handle.t`. If I Ctrl+Drag a handle, maybe I want to Clone it to
    # `current_time`? Yes, that makes the most sense: "Copy this pose to NOW".

    keyframe_duplicated = Signal(
        str, float, float, float
    )  # marker_id, source_t, scene_x, scene_y
    keyframe_deleted = Signal(str, float)  # marker_id, t
    keyframe_double_clicked = Signal(str, float)  # marker_id, t

    def __init__(self, marker_id: str, parent: Optional[QGraphicsItem] = None) -> None:
        QObject.__init__(self)
        QGraphicsPathItem.__init__(self, parent)
        self.marker_id = marker_id
        self.setZValue(5)  # Draw above map (0) but below markers (10)

        # Setup Pen
        pen = QPen(COLOR_PATH_LINE, 2)
        pen.setStyle(Qt.PenStyle.DashLine)
        self.setPen(pen)

        self.handles: List[HandleItem] = []

    def update_path(
        self,
        keyframes: List[Dict[str, Any]],
        map_width: float,
        map_height: float,
    ) -> None:
        """
        Rebuilds the path and handles based on keyframes.

        Args:
            keyframes: List of dicts {t, x, y, type}
            map_width: Scene width to denormalize coords
            map_height: Scene height to denormalize coords
        """
        path = QPainterPath()

        # Clear existing handles
        scene = self.scene()
        for h in self.handles:
            if scene:
                scene.removeItem(h)
            else:
                h.setParentItem(None)  # Safety

        self.handles.clear()

        if not keyframes:
            self.setPath(path)
            return

        # Prepare first point
        first = keyframes[0]
        start_pt = QPointF(first["x"] * map_width, first["y"] * map_height)
        path.moveTo(start_pt)
        self._create_handle(first, start_pt)

        # Add segments
        for kf in keyframes[1:]:
            pt = QPointF(kf["x"] * map_width, kf["y"] * map_height)
            path.lineTo(pt)
            self._create_handle(kf, pt)

        self.setPath(path)

    def _create_handle(self, kf: Dict[str, Any], pos: QPointF) -> None:
        """Helper to create and position a handle."""
        handle = HandleItem(
            t=kf["t"],
            x=kf["x"],
            y=kf["y"],
            kf_type=kf.get("type", "path"),
            parent=self,
        )
        # HandleItem is a child of MotionPathItem.
        handle.setPos(pos)

        # Connect signals
        handle.position_changed.connect(self._on_handle_moved)
        handle.duplicate_requested.connect(self._on_handle_duplicated)
        handle.delete_requested.connect(self._on_handle_deleted)
        handle.double_clicked.connect(self._on_handle_double_clicked)

        self.handles.append(handle)

    def _on_handle_moved(self, t: float, scene_x: float, scene_y: float) -> None:
        """
        Forward handle movement with marker_id for database update.
        Path redrawing happens in HandleItem.itemChange during drag.
        """
        # Forward signal for database update (on mouse release)
        self.keyframe_moved.emit(self.marker_id, t, scene_x, scene_y)

    def _redraw_path_from_handles(self) -> None:
        """Rebuild the path line from current handle positions without recreating handles."""
        if not self.handles:
            return

        path = QPainterPath()
        # Sort handles by time
        sorted_handles = sorted(self.handles, key=lambda h: h.t)

        # Start path at first handle's current scene position
        first_pos = sorted_handles[0].scenePos()
        path.moveTo(self.mapFromScene(first_pos))

        # Add lines to subsequent handles
        for handle in sorted_handles[1:]:
            handle_pos = handle.scenePos()
            path.lineTo(self.mapFromScene(handle_pos))

        self.setPath(path)

    def _on_handle_duplicated(self, t: float, scene_x: float, scene_y: float) -> None:
        """Forward duplication request."""
        # Semantics: Copy keyframe from 't', but using new spatial coords 'scene_x/y'.
        self.keyframe_duplicated.emit(self.marker_id, t, scene_x, scene_y)

    def _on_handle_deleted(self, t: float) -> None:
        """Forward deletion request."""
        self.keyframe_deleted.emit(self.marker_id, t)

    def _on_handle_double_clicked(self, t: float) -> None:
        """Forward double click (edit) request."""
        self.keyframe_double_clicked.emit(self.marker_id, t)
