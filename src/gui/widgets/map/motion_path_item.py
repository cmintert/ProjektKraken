from typing import Any, Dict, List, Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QGraphicsPathItem

# Constants for visuals
HANDLE_SIZE = 8
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
        if (
            change == QGraphicsItem.GraphicsItemChange.ItemPositionChange
            and self.scene()
        ):
            # Notify parent/scene of movement
            # We emitted normalized coordinates? No, handles are in SCENE coords usually.
            # But the logic expects normalized.
            # The View will handle the translation of Scene Pos -> Normalized.
            pass
        return super().itemChange(change, value)

    def mousePressEvent(self, event: Any) -> None:
        super().mousePressEvent(event)
        self.clicked.emit(self)

    def hoverEnterEvent(self, event: Any) -> None:
        self._is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: Any) -> None:
        self._is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)


class MotionPathItem(QGraphicsPathItem):
    """
    Visualizes the temporal path of a marker using a dotted line.
    Manages child HandleItems.
    """

    def __init__(self, parent: Optional[QGraphicsItem] = None) -> None:
        super().__init__(parent)
        self.setZValue(-1)  # Draw behind the marker itself

        # Setup Pen
        pen = QPen(COLOR_PATH_LINE, 2)
        pen.setStyle(Qt.PenStyle.DashLine)
        self.setPen(pen)

        self.handles: List[HandleItem] = []

    def update_path(
        self, keyframes: List[Dict[str, Any]], map_width: float, map_height: float
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
        # If MotionPathItem is at 0,0 in scene, then handle pos is scene pos.
        handle.setPos(pos)
        self.handles.append(handle)
