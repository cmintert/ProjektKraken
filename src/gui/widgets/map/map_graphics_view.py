"""Map Graphics View Module.

Provides the MapGraphicsView class for rendering and interacting with the map.
"""

import json
import logging
import math
from typing import Any, Callable, Dict, Optional

from PySide6.QtCore import (
    Property,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSettings,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QContextMenuEvent,
    QCursor,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QResizeEvent,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsObject,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSceneHoverEvent,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QStyleOptionGraphicsItem,
    QVBoxLayout,
    QWidget,
)

from src.app.constants import (
    MAP_DEFAULT_WIDTH_METERS,
    MAP_EDIT_DASH_PATTERN,
    MAP_EDIT_STROKE_COLOR,
    MAP_EDIT_STROKE_WIDTH,
    MAP_MIDPOINT_GHOST_OPACITY,
    MAP_MIDPOINT_HANDLE_BORDER_COLOR,
    MAP_MIDPOINT_HANDLE_COLOR,
    MAP_MIDPOINT_HANDLE_RADIUS,
    MAP_MIDPOINT_HOVER_OPACITY,
    MAP_SNAP_RADIUS_PX,
    MAP_VERTEX_HANDLE_BORDER_COLOR,
    MAP_VERTEX_HANDLE_COLOR,
    MAP_VERTEX_HANDLE_RADIUS,
    MAP_ZOOM_IN_FACTOR,
)
from src.core.marker import FEATURE_TYPE_PATH, FEATURE_TYPE_POINT, FEATURE_TYPE_REGION
from src.core.theme_manager import ThemeManager
from src.core.trajectory import KEYFRAME_TIME_EPSILON
from src.gui.widgets.map.coordinate_system import MapCoordinateSystem
from src.gui.widgets.map.feature_items import PathItem, RegionItem
from src.gui.widgets.map.icon_picker_dialog import IconPickerDialog
from src.gui.widgets.map.marker_item import MarkerItem
from src.gui.widgets.map.scale_bar_painter import ScaleBarPainter

logger = logging.getLogger(__name__)

# Layer Z-Values
LAYER_MAP_BG = 0
LAYER_TRAJECTORIES = 5
LAYER_MARKERS = 10
LAYER_UI_OVERLAY = 100

# Colors
KEYFRAME_COLOR_DEFAULT = "#f1c40f"  # Yellow
KEYFRAME_COLOR_SELECTED = "#e74c3c"  # Red
KEYFRAME_LABEL_COLOR = "#000000"  # Black
TRAJECTORY_PATH_COLOR = "#3498db"  # Blue
GIZMO_TEXT_COLOR = "#ffffff"  # White

# Layout Constants
GIZMO_SIZE = 6
GIZMO_FONT_FAMILY = "Segoe UI"
GIZMO_FONT_SIZE = 6

KEYFRAME_LABEL_FONT_FAMILY = "Segoe UI"
KEYFRAME_LABEL_FONT_SIZE = 12
KEYFRAME_LABEL_OFFSET_X = -10
KEYFRAME_LABEL_OFFSET_Y = 10
KEYFRAME_LABEL_MIN_SIZE_PT = 8
KEYFRAME_LABEL_MAX_SIZE_PT = 10

# Drawing mode constants
NORMALIZED_COORD_PRECISION = 6  # decimal places for normalized coordinates


class KeyframeGizmo(QGraphicsItemGroup):
    """Hover gizmo for keyframe actions: Clock Mode and Delete.
    Shows clickable icons for temporal editing (clock) and deletion (red X).
    """

    def __init__(
        self, keyframe_item: "KeyframeItem", parent: Optional[QGraphicsItem] = None
    ) -> None:
        """Initialize the keyframe gizmo.

        Args:
            keyframe_item: The parent keyframe item this gizmo belongs to.
            parent: Optional parent graphics item.
        """
        super().__init__(parent)
        self.keyframe_item = keyframe_item
        self.setZValue(LAYER_UI_OVERLAY)
        self.setAcceptHoverEvents(True)

        # Create Clock icon (left)
        self.clock_icon = self._create_icon("🕐", 0, GIZMO_TEXT_COLOR)
        self.addToGroup(self.clock_icon)

        # Create Delete icon (right) - red X
        self.delete_icon = self._create_icon("✕", GIZMO_SIZE + 4, "#FF4444")
        self.addToGroup(self.delete_icon)

        # Position gizmo to Northeast of keyframe (Right and Up)
        self.setPos(3, -8)

    def _create_icon(self, text: str, x_offset: float, color: str) -> QGraphicsRectItem:
        """Create a clickable icon button.

        Args:
            text: Unicode character to display as icon.
            x_offset: Horizontal offset in pixels.
            color: Hex color code for the icon.

        Returns:
            QGraphicsRectItem containing the styled icon.
        """
        from PySide6.QtCore import Qt

        # Background rect (smaller)
        size = GIZMO_SIZE
        rect = QGraphicsRectItem(x_offset, 0, size, size)
        rect.setBrush(Qt.NoBrush)
        rect.setPen(Qt.NoPen)
        rect.setZValue(LAYER_UI_OVERLAY)

        # Icon text (smaller font)
        label = QGraphicsSimpleTextItem(text, rect)
        label.setPos(x_offset + 1, -3)
        label.setBrush(QBrush(QColor(color)))
        font = QFont(GIZMO_FONT_FAMILY, GIZMO_FONT_SIZE)
        label.setFont(font)

        # Make clickable
        rect.setAcceptHoverEvents(True)
        rect.setCursor(Qt.CursorShape.PointingHandCursor)

        return rect

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        """Keep gizmo visible while hovering over it.

        Args:
            event: The hover enter event.
        """
        super().hoverEnterEvent(event)
        self.keyframe_item._gizmo_hovered = True

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        """Remove gizmo when mouse leaves.

        Args:
            event: The hover leave event.
        """
        super().hoverLeaveEvent(event)
        self.keyframe_item._gizmo_hovered = False
        if not self.keyframe_item.isUnderMouse():
            self.keyframe_item._cleanup_gizmo()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle icon clicks - clock for Clock Mode, X for delete.

        Args:
            event: The mouse press event.
        """
        # Determine which icon was clicked based on local position
        click_x = event.position().x()

        if click_x < GIZMO_SIZE + 1:
            # Clock icon clicked - enter Clock Mode
            logger.info(f"Clock icon clicked for marker {self.keyframe_item.marker_id}")
            self.keyframe_item.set_mode("clock")
        else:
            # Delete icon clicked - request keyframe deletion
            logger.info(
                f"Delete icon clicked for keyframe {self.keyframe_item.marker_id} "
                f"at t={self.keyframe_item.t}"
            )
            self.keyframe_item.request_delete()
        event.accept()


class KeyframeItem(QGraphicsObject):
    """A draggable keyframe dot on the trajectory.

    Represents a temporal keyframe for a marker's position on the map.
    Supports transform and clock modes for editing position and time.
    """

    def __init__(
        self,
        marker_id: str,
        t: float,
        x: float,
        y: float,
        rect: QRectF,
        on_drop_callback: Callable[["KeyframeItem"], None],
        on_drag_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        """Initialize the keyframe item.

        Args:
            marker_id: Unique identifier for the associated marker.
            t: Time value for this keyframe (normalized).
            x: X coordinate (normalized 0-1).
            y: Y coordinate (normalized 0-1).
            rect: Bounding rectangle for the keyframe dot.
            on_drop_callback: Callback invoked when keyframe is dropped after drag.
            on_drag_callback: Optional callback invoked during dragging.
        """
        super().__init__()
        self._rect = rect
        self.marker_id = marker_id
        self.t = t
        self.original_x = x  # Normalized X
        self.original_y = y  # Normalized Y
        self.on_drop_callback = on_drop_callback
        self.on_drag_callback = on_drag_callback

        # Mode state
        self.mode: str = "transform"  # "transform" or "clock"
        self.is_pinned: bool = False

        # Visuals
        self._brush = QBrush(QColor(KEYFRAME_COLOR_DEFAULT))
        self._pen = QPen(Qt.PenStyle.NoPen)

        # Gizmo (mode selector)
        self.gizmo: Optional[KeyframeGizmo] = None
        self._gizmo_hovered: bool = False

        # Enable interaction
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)

    def boundingRect(self) -> QRectF:
        """Return the bounding rectangle for the keyframe dot.

        Returns:
            QRectF defining the bounds of this graphics item.
        """
        return self._rect

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        """Paint the keyframe dot.

        Args:
            painter: QPainter to use for drawing.
            option: Style options for the graphics item.
            widget: Optional widget being painted on.
        """
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(self._brush)
        painter.setPen(self._pen)
        painter.drawEllipse(self._rect)

    def setBrush(self, brush: QBrush) -> None:
        """Set the brush for the keyframe dot.

        Args:
            brush: QBrush to use for filling the dot.
        """
        self._brush = brush
        self.update()

    def brush(self) -> QBrush:
        """Get the current brush.

        Returns:
            QBrush used for filling the dot.
        """
        return self._brush

    @Property(float)
    def scale_val(self) -> float:
        """Get the scale value for animation.

        Returns:
            Current scale factor.
        """
        return self.scale()

    @scale_val.setter
    def scale_val(self, value: float) -> None:
        """Set the scale value for animation.

        Args:
            value: New scale factor.
        """
        self.setScale(value)
        self.update()

    def setPen(self, pen: QPen) -> None:
        """Set the pen for the keyframe dot border.

        Args:
            pen: QPen to use for drawing the dot border.
        """
        self._pen = pen
        self.update()

    def pen(self) -> QPen:
        """Get the current pen.

        Returns:
            QPen used for drawing the dot border.
        """
        return self._pen

    def set_mode(self, mode: str) -> None:
        """Switch between transform and clock modes.

        Args:
            mode: Mode to switch to ('transform' or 'clock').
        """
        logger.info(f"Keyframe {self.marker_id} mode set to: {mode}")
        self.mode = mode
        if mode == "clock":
            # Emit signal to enter Clock Mode
            view = self.scene().views()[0] if self.scene() else None
            if view and hasattr(view, "keyframe_clock_mode_requested"):
                view.keyframe_clock_mode_requested.emit(self.marker_id, self.t)
        # Hide gizmo after selection
        self._cleanup_gizmo()

    def set_pinned(self, pinned: bool) -> None:
        """Set visual state for pinned keyframe (Clock Mode).

        Args:
            pinned: True if keyframe is pinned in Clock Mode.
        """
        self.is_pinned = pinned
        color = KEYFRAME_COLOR_SELECTED if pinned else KEYFRAME_COLOR_DEFAULT
        pen_width = 3 if pinned else 1

        self.setPen(QPen(QColor(color), pen_width))
        self.setBrush(QBrush(QColor(color)))

    def request_delete(self) -> None:
        """Request deletion of this keyframe by emitting signal to view."""
        view = self.scene().views()[0] if self.scene() else None
        if view and hasattr(view, "keyframe_delete_requested"):
            logger.info(
                f"Requesting delete for keyframe {self.marker_id} at t={self.t}"
            )
            view.keyframe_delete_requested.emit(self.marker_id, self.t)
        # Cleanup gizmo after action
        self._cleanup_gizmo()

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        """Show gizmo when hovering over keyframe.

        Args:
            event: The hover enter event.
        """
        super().hoverEnterEvent(event)
        if not self.gizmo and not self.is_pinned:
            self.gizmo = KeyframeGizmo(self)
            self.gizmo.setParentItem(self)  # Auto-cleanup when parent deleted
            self.gizmo.setVisible(True)
        elif self.gizmo:
            self.gizmo.setVisible(True)

        if self.mode == "transform":
            self.setCursor(Qt.CursorShape.SizeAllCursor)

        # Show Hint Tooltip if first-use
        self._show_hover_hint()

    def _show_hover_hint(self) -> None:
        """Show a one-time hint tooltip for first-time users."""
        settings = QSettings()
        if not settings.value("map/onboarding_hover_hint_shown", False, type=bool):
            self.setToolTip("💡 Tip: Hover keyframes to edit position or time")
            # We can't easily dismiss it with "Don't show again" inside a native
            # tooltip, but we can mark it as shown if it stays for a while.
            # Using QToolTip.showText or similar might be better for floating UI.
            # For now, let's use the standard tooltip and mark it as seen.
            settings.setValue("map/onboarding_hover_hint_shown", True)

    def _cleanup_gizmo(self) -> None:
        """Remove gizmo if not being hovered."""
        # Additional guard: check if gizmo itself thinks it's under mouse
        # This handles the race condition where we leave keyframe but enter gizmo
        gizmo_under_mouse = self.gizmo and self.gizmo.isUnderMouse()

        if (
            self.gizmo
            and not self._gizmo_hovered
            and not self.is_pinned
            and not gizmo_under_mouse
        ):
            self.gizmo.setVisible(False)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        """Hide gizmo when leaving keyframe.

        Args:
            event: The hover leave event.
        """
        super().hoverLeaveEvent(event)
        self.unsetCursor()
        # Attempt cleanup when leaving the keyframe dot
        self._cleanup_gizmo()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Clear any existing selection before starting drag.

        Args:
            event: The mouse press event.
        """
        if self.scene():
            self.scene().clearSelection()
        # Hide gizmo immediately when starting drag
        if self.gizmo and self.mode == "transform":
            self.gizmo.setVisible(False)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle drop event after dragging.

        Args:
            event: The mouse release event.
        """
        super().mouseReleaseEvent(event)
        if self.on_drop_callback:
            self.on_drop_callback(self)

    def itemChange(
        self, change: QGraphicsEllipseItem.GraphicsItemChange, value: Any
    ) -> Any:
        """Handle position changes during drag.

        Args:
            change: The type of change occurring.
            value: The new value for the change.

        Returns:
            The processed value for the change.
        """
        if (
            change == QGraphicsEllipseItem.GraphicsItemChange.ItemPositionHasChanged
            and self.on_drag_callback
        ):
            self.on_drag_callback()
        return super().itemChange(change, value)


class _VertexHandle(QGraphicsEllipseItem):
    """Draggable handle displayed on a feature vertex during editing.

    Each handle is a small circle that the user can drag to reshape
    a path or region. On release, the callback fires with the new position.
    Right-clicking the handle removes the vertex.

    The handle scales inversely with the view zoom so it maintains a
    constant screen-pixel size, enabling precise work at high zoom.

    Args:
        index: The vertex index this handle represents.
        on_moved: Callback ``(index, QPointF)`` invoked when dragging finishes.
        on_delete: Optional callback ``(index,)`` invoked on right-click delete.

    """

    def __init__(
        self,
        index: int,
        on_moved: "Callable[[int, QPointF], None]",
        on_delete: "Optional[Callable[[int], None]]" = None,
    ) -> None:
        r = MAP_VERTEX_HANDLE_RADIUS
        super().__init__(-r, -r, r * 2, r * 2)
        self.index = index
        self._on_moved = on_moved
        self._on_delete = on_delete
        self.setBrush(QBrush(QColor(MAP_VERTEX_HANDLE_COLOR)))
        self.setPen(QPen(QColor(MAP_VERTEX_HANDLE_BORDER_COLOR), 1))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True
        )
        self.setAcceptHoverEvents(True)
        self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        self.setZValue(LAYER_UI_OVERLAY + 1)

    def itemChange(
        self, change: QGraphicsItem.GraphicsItemChange, value: Any
    ) -> Any:
        """Notifies parent when the handle position changes.

        Args:
            change: The type of change.
            value: The new value.

        Returns:
            The processed value.

        """
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self._on_moved(self.index, self.pos())
        return super().itemChange(change, value)

    def mousePressEvent(self, event: "QGraphicsSceneMouseEvent") -> None:
        """Handles right-click to delete the vertex.

        Args:
            event: The mouse press event.

        """
        if event.button() == Qt.MouseButton.RightButton and self._on_delete:
            self._on_delete(self.index)
            event.accept()
            return
        super().mousePressEvent(event)


class _MidpointHandle(QGraphicsEllipseItem):
    """Ghost handle on the midpoint of a segment for inserting new vertices.

    Displayed as a semi-transparent circle between two consecutive vertex
    handles. When dragged, it converts into a real vertex by invoking the
    ``on_insert`` callback with the segment index and the new position.

    The handle scales inversely with the view zoom so it maintains a
    constant screen-pixel size.

    Args:
        segment_index: Index of the segment (vertex *before* the midpoint).
        on_insert: Callback ``(segment_index, QPointF)`` invoked on drag.

    """

    def __init__(
        self,
        segment_index: int,
        on_insert: "Callable[[int, QPointF], None]",
    ) -> None:
        r = MAP_MIDPOINT_HANDLE_RADIUS
        super().__init__(-r, -r, r * 2, r * 2)
        self.segment_index = segment_index
        self._on_insert = on_insert
        self._activated = False
        self.setBrush(QBrush(QColor(MAP_MIDPOINT_HANDLE_COLOR)))
        self.setPen(QPen(QColor(MAP_MIDPOINT_HANDLE_BORDER_COLOR), 1))
        self.setOpacity(MAP_MIDPOINT_GHOST_OPACITY)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True
        )
        self.setAcceptHoverEvents(True)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        self.setZValue(LAYER_UI_OVERLAY)

    def hoverEnterEvent(self, event: "QGraphicsSceneHoverEvent") -> None:
        """Highlights the ghost handle on hover.

        Args:
            event: The hover enter event.

        """
        self.setOpacity(MAP_MIDPOINT_HOVER_OPACITY)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: "QGraphicsSceneHoverEvent") -> None:
        """Resets ghost handle opacity on hover leave.

        Args:
            event: The hover leave event.

        """
        if not self._activated:
            self.setOpacity(MAP_MIDPOINT_GHOST_OPACITY)
        super().hoverLeaveEvent(event)

    def mouseMoveEvent(self, event: "QGraphicsSceneMouseEvent") -> None:
        """On first drag, insert the vertex.

        Args:
            event: The mouse move event.

        """
        if not self._activated:
            self._activated = True
            self.setOpacity(1.0)
            self._on_insert(self.segment_index, self.pos())
        super().mouseMoveEvent(event)


class MapGraphicsView(QGraphicsView):
    """Graphics view for displaying a map image with draggable markers.

    Signals:
        marker_moved: Emitted when a marker is dragged to a new position.
                     Args: (marker_id: str, x: float, y: float)
                     Coordinates are normalized [0.0, 1.0] relative to map image.
    """

    marker_moved = Signal(str, float, float)
    marker_clicked = Signal(str, str)  # marker_id, object_type
    add_marker_requested = Signal(float, float)  # x, y (normalized)
    delete_marker_requested = Signal(str)  # marker_id
    change_marker_icon_requested = Signal(str, str)  # marker_id, new_icon
    change_marker_color_requested = Signal(str, str)  # marker_id, new_color_hex
    marker_drop_requested = Signal(str, str, str, float, float)  # id, type, name, x, y
    mouse_coordinates_changed = Signal(
        float, float, bool
    )  # x, y (normalized), in_bounds
    keyframe_moved = Signal(str, float, float, float)  # marker_id, t, new_x, new_y
    keyframe_clock_mode_requested = Signal(str, float)  # marker_id, t
    keyframe_delete_requested = Signal(str, float)  # marker_id, t
    keyframe_edit_requested = Signal(str, float, float, float)  # marker_id, t, x, y
    calibration_completed = Signal(float)  # emitted with pixel distance
    # Drawing mode signals
    drawing_finished = Signal(str, list)  # feature_type, geometry (normalized coords)
    drawing_cancelled = Signal()  # Emitted when drawing is cancelled
    # Feature editing signals
    feature_style_changed = Signal(str, dict)  # marker_id, new_style dict
    feature_geometry_changed = Signal(str, list)  # marker_id, new geometry list

    # Visual style for the feature being edited
    _EDIT_DASH_PATTERN = MAP_EDIT_DASH_PATTERN
    _EDIT_STROKE_COLOR = MAP_EDIT_STROKE_COLOR
    _EDIT_STROKE_WIDTH = MAP_EDIT_STROKE_WIDTH

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initializes the MapGraphicsView.

        Args:
            parent: Parent widget.

        """
        super().__init__(parent)

        # Initialize Coordinate System
        self.coord_system = MapCoordinateSystem()

        # Calibration State
        self.calibration_mode = False
        self.calibration_points: list[QPointF] = []

        # Set OpenGL Viewport (Safe Fallback)
        import os

        force_software = os.environ.get("KRAKEN_NO_OPENGL", "").lower() in (
            "1",
            "true",
            "yes",
        )

        if not force_software:
            try:
                from PySide6.QtOpenGLWidgets import QOpenGLWidget

                self.setViewport(QOpenGLWidget())

            except ImportError:
                logger.warning(
                    "QtOpenGLWidgets not available. Requesting software rendering."
                )
            except Exception as e:
                logger.warning(
                    f"Failed to initialize OpenGL viewport: {e}. "
                    "Falling back to software rendering."
                )
        else:
            logger.info(
                "OpenGL disabled via KRAKEN_NO_OPENGL. Using software rendering."
            )

        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        # View settings
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMouseTracking(True)  # Enable mouse tracking for coordinates

        # Disable scrollbars for infinite canvas feel
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Map and markers
        self.pixmap_item: Optional[QGraphicsPixmapItem] = None
        self.markers: Dict[str, MarkerItem] = {}
        self.feature_items: Dict[str, QGraphicsObject] = {}  # path/region items

        # Theme
        self.tm = ThemeManager()
        self.tm.theme_changed.connect(self._update_theme)
        self._update_theme(self.tm.get_theme())

        # Enable drop support for drag-from-explorer
        self.setAcceptDrops(True)

        # Drop Hint Overlay (blue dashed box)
        self._drop_hint_overlay = QLabel(self.viewport())
        from src.gui.utils.style_helper import StyleHelper

        self._drop_hint_overlay.setStyleSheet(StyleHelper.get_drag_overlay_style())
        self._drop_hint_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drop_hint_overlay.setText("Drop to Place Marker")
        self._drop_hint_overlay.hide()

        # Temporal state (for future trajectory animation)
        self._current_time: float = 0.0

        # Drawing Mode state
        self._drawing_mode: Optional[str] = None  # None, "path", or "region"
        self._drawing_vertices: list[QPointF] = []  # scene coordinates
        self._drawing_preview_item: Optional[QGraphicsPathItem] = None
        self._drawing_dots: list[QGraphicsItem] = []  # vertex dots

        # Vertex Editing state
        self._editing_feature_id: Optional[str] = None
        self._vertex_handles: list[QGraphicsEllipseItem] = []
        self._midpoint_handles: list[QGraphicsEllipseItem] = []
        self._editing_original_style: Optional[Dict[str, Any]] = None

        # Trajectory Visualization
        self.trajectory_path_item: Optional[QGraphicsPathItem] = None
        self.keyframe_items: list[KeyframeItem] = []
        self.keyframe_label_items: list[QGraphicsSimpleTextItem] = []
        self._calendar_converter: Optional[object] = None  # CalendarConverter instance
        self.trigger_first_use_animation: bool = False
        self._animations: list[QPropertyAnimation] = []  # Keep references

    def minimumSizeHint(self) -> QSize:
        """Override minimum size hint to allow resizing below map image size.

        By default, QGraphicsView uses the scene rect to determine
        its minimum size, which prevents the dock from being resized
        smaller than the map image. We override this to allow free resizing.

        Returns:
            QSize: A small minimum size (200x150) to allow shrinking.

        """
        from PySide6.QtCore import QSize

        return QSize(200, 150)

    def _update_theme(self, theme: dict) -> None:
        """Updates the scene background."""
        self.scene.setBackgroundBrush(QBrush(QColor(theme["app_bg"])))

        # Scale Bar
        self.scale_bar_painter = ScaleBarPainter()
        self.map_width_meters = MAP_DEFAULT_WIDTH_METERS  # Default 1000km

        # Calibration State
        self.calibration_mode = False
        self.calibration_points: list[QPointF] = []

    def load_map(self, image_path: str) -> bool:
        """Loads a map image into the view.

        Args:
            image_path: Path to the image file.

        Returns:
            bool: True if successful, False otherwise.

        """
        try:
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                logger.error(f"Failed to load map image: {image_path}")
                return False

            # Clear existing map
            if self.pixmap_item:
                self.scene.removeItem(self.pixmap_item)

            # Add new map
            # Add new map
            self.pixmap_item = QGraphicsPixmapItem(pixmap)
            self.pixmap_item.setZValue(LAYER_MAP_BG)
            self.scene.addItem(self.pixmap_item)

            # Update coordinate system bounds
            self.coord_system.set_scene_rect(self.pixmap_item.boundingRect())

            # Fit view to map
            self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
            self.scene.setSceneRect(self.pixmap_item.boundingRect())

            logger.info(f"Loaded map: {image_path}")
            return True

        except Exception as e:
            logger.error(f"Error loading map: {e}")
            return False

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Handle resize events.

        Note: We no longer auto-fit here to allow the user to maintain zoom level.
        """
        super().resizeEvent(event)
        if hasattr(self, "_drop_hint_overlay") and self._drop_hint_overlay:
            # Match the viewport size precisely
            self._drop_hint_overlay.setGeometry(self.viewport().rect())

    def sizeHint(self) -> QSize:
        """Return a stable preferred size to prevent dock layout jitter.

        Returns:
            QSize: A reasonable default size that doesn't fight the layout.

        """
        return QSize(400, 300)

    def fit_to_view(self) -> None:
        """Fits the map to the current view size."""
        if self.pixmap_item:
            self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press to implement Smart Drag, Calibration, and Drawing."""
        # Handle Drawing Mode
        if self._drawing_mode and self.pixmap_item:
            if event.button() == Qt.MouseButton.LeftButton:
                pos = event.position().toPoint()
                scene_pos = self.mapToScene(pos)
                item_pos = self.pixmap_item.mapFromScene(scene_pos)
                if self.pixmap_item.contains(item_pos):
                    self._add_drawing_vertex(scene_pos)
                return  # Consume event

        # Handle Calibration Mode
        if self.calibration_mode and self.pixmap_item:
            pos = event.position().toPoint()
            scene_pos = self.mapToScene(pos)
            item_pos = self.pixmap_item.mapFromScene(scene_pos)

            if self.pixmap_item.contains(item_pos):
                self.calibration_points.append(scene_pos)
                self.viewport().update()  # Trigger redraw for line

                # If we have 2 points, finish
                if len(self.calibration_points) >= 2:
                    p1 = self.calibration_points[0]
                    p2 = self.calibration_points[1]

                    # Use accurate euclidean for real calc
                    import math

                    dx = p2.x() - p1.x()
                    dy = p2.y() - p1.y()
                    dist = math.sqrt(dx * dx + dy * dy)

                    self.calibration_mode = False
                    self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
                    self.setCursor(Qt.ArrowCursor)  # Reset cursor
                    self.calibration_completed.emit(dist)

                return  # Consume event

        # Normal handling
        if self.calibration_mode:
            return  # Prevent drag in calibration mode

        pos = event.position().toPoint()
        item = self.itemAt(pos)

        if isinstance(item, MarkerItem):
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
        else:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Reset drag mode on release."""
        super().mouseReleaseEvent(event)
        if not self.calibration_mode:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move to track coordinates, drawing preview, and cursor.

        Updates cursor to crosshair during drawing mode and pointer when
        hovering over editable feature items in vertex editing mode.
        """
        super().mouseMoveEvent(event)

        if self._drawing_mode:
            self.setCursor(Qt.CursorShape.CrossCursor)
            if self._drawing_vertices:
                scene_pos = self.mapToScene(event.position().toPoint())
                self._update_drawing_preview(scene_pos)
        elif self._editing_feature_id:
            # Show pointer cursor over the edited feature, crosshair elsewhere
            pos = event.position().toPoint()
            item_under = self.itemAt(pos)
            if isinstance(item_under, (_VertexHandle, _MidpointHandle)):
                pass  # Handle sets its own cursor
            elif (
                item_under
                and hasattr(item_under, "marker_id")
                and item_under.marker_id == self._editing_feature_id
            ):
                self.setCursor(Qt.CursorShape.CrossCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

        if self.calibration_mode:
            self.setCursor(Qt.CrossCursor)  # Enforce cursor
            self.viewport().update()  # Redraw for rubber band line

        if self.pixmap_item:
            # map view pos to scene pos
            pos = event.position().toPoint()
            scene_pos = self.mapToScene(pos)

            # Check if within map bounds (convert to item-local coordinates)
            item_pos = self.pixmap_item.mapFromScene(scene_pos)
            if self.pixmap_item.contains(item_pos):
                norm_pos = self.coord_system.to_normalized(scene_pos)
                self.mouse_coordinates_changed.emit(norm_pos[0], norm_pos[1], True)
            else:
                self.mouse_coordinates_changed.emit(0.0, 0.0, False)

    def add_marker(
        self,
        marker_id: str,
        object_type: str,
        label: str,
        x: float,
        y: float,
        icon: Optional[str] = None,
        color: Optional[str] = None,
        description: Optional[str] = None,
        lore_date: Optional[float] = None,
        feature_type: str = "point",
        geometry: Optional[list] = None,
        style: Optional[dict] = None,
    ) -> None:
        """Adds a marker or feature to the map at normalized coordinates.

        Uses a factory pattern: point features become MarkerItem, path
        features become PathItem, and region features become RegionItem.

        Args:
            marker_id: Unique identifier for the marker.
            object_type: Type of object ('entity' or 'event').
            label: Marker label text.
            x: Normalized X coordinate [0.0, 1.0] (anchor).
            y: Normalized Y coordinate [0.0, 1.0] (anchor).
            icon: Optional icon filename (e.g., 'castle.svg').
            color: Optional color hex string.
            description: Optional description for tooltip.
            lore_date: Optional lore timestamp for temporal filtering.
            feature_type: 'point', 'path', or 'region'.
            geometry: Optional list of coordinate dicts for paths/regions.
            style: Optional visual override dict.

        """
        if not self.pixmap_item:
            logger.warning("Cannot add marker: no map loaded")
            return

        # Remove existing marker/feature if present
        if marker_id in self.markers:
            self.scene.removeItem(self.markers[marker_id])
            del self.markers[marker_id]
        if marker_id in self.feature_items:
            self.scene.removeItem(self.feature_items[marker_id])
            del self.feature_items[marker_id]

        # Factory: route by feature_type
        if feature_type == FEATURE_TYPE_PATH and geometry:
            item = PathItem(
                marker_id=marker_id,
                object_type=object_type,
                label=label,
                pixmap_item=self.pixmap_item,
                geometry=geometry,
                anchor_x=x,
                anchor_y=y,
                style=style,
                description=description,
                lore_date=lore_date,
                map_width_meters=self.map_width_meters,
            )
            self.scene.addItem(item)
            self.feature_items[marker_id] = item
            item.clicked.connect(self.marker_clicked.emit)
            return

        if feature_type == FEATURE_TYPE_REGION and geometry:
            item = RegionItem(
                marker_id=marker_id,
                object_type=object_type,
                label=label,
                pixmap_item=self.pixmap_item,
                geometry=geometry,
                anchor_x=x,
                anchor_y=y,
                style=style,
                description=description,
                lore_date=lore_date,
                map_width_meters=self.map_width_meters,
            )
            self.scene.addItem(item)
            self.feature_items[marker_id] = item
            item.clicked.connect(self.marker_clicked.emit)
            return

        # Default: point marker (backward compatible)
        marker = MarkerItem(
            marker_id,
            object_type,
            label,
            self.pixmap_item,
            icon,
            color,
            description,
            lore_date,
        )

        # Convert normalized to scene coordinates
        scene_pos = self.coord_system.to_scene(x, y)
        marker.setPos(scene_pos)
        marker.setZValue(LAYER_MARKERS)

        # Add to scene and track
        self.scene.addItem(marker)
        self.markers[marker_id] = marker

        # Connect click signal
        marker.clicked.connect(self.marker_clicked.emit)

    def update_marker_position(self, marker_id: str, x: float, y: float) -> None:
        """Update a marker's position to new normalized coordinates.

        Args:
            marker_id: Unique identifier for the marker to update.
            x: New X coordinate (normalized 0-1).
            y: New Y coordinate (normalized 0-1).
        """
        if marker_id not in self.markers:
            logger.warning(f"Cannot update: marker {marker_id} not found")
            return

        marker = self.markers[marker_id]
        scene_pos = self.coord_system.to_scene(x, y)
        marker.setPos(scene_pos)

        # Remove spammy log
        # logger.debug(f"Updated marker {marker_id} to normalized ({x:.3f}, {y:.3f})")

    def remove_marker(self, marker_id: str) -> None:
        """Remove a marker or feature from the map.

        Args:
            marker_id: Unique identifier for the marker to remove.
        """
        if marker_id in self.markers:
            self.scene.removeItem(self.markers[marker_id])
            del self.markers[marker_id]
            logger.debug(f"Removed marker {marker_id}")
        if marker_id in self.feature_items:
            self.scene.removeItem(self.feature_items[marker_id])
            del self.feature_items[marker_id]
            logger.debug(f"Removed feature {marker_id}")

    def clear_markers(self) -> None:
        """Remove all markers and features from the map."""
        for marker in list(self.markers.values()):
            self.scene.removeItem(marker)
        self.markers.clear()
        for item in list(self.feature_items.values()):
            self.scene.removeItem(item)
        self.feature_items.clear()

    def update_markers_temporal_state(
        self, playhead_time: float, current_time: float
    ) -> None:
        """Updates the temporal visual state of all markers and features."""
        all_items = list(self.markers.values()) + list(self.feature_items.values())
        for item in all_items:
            if item.lore_date is None:
                item.set_temporal_state(is_future=False, is_past=False)
                continue
            is_future = item.lore_date > playhead_time
            is_past = item.lore_date <= playhead_time
            item.set_temporal_state(is_future=is_future, is_past=is_past)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel for zooming."""
        zoom_out_factor = 1 / MAP_ZOOM_IN_FACTOR

        # Check zoom direction
        factor = MAP_ZOOM_IN_FACTOR if event.angleDelta().y() > 0 else zoom_out_factor

        self.scale(factor, factor)
        self._update_label_scales()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept drag events with our custom MIME type."""
        from src.gui.widgets.unified_list import KRAKEN_ITEM_MIME_TYPE

        if event.mimeData().hasFormat(KRAKEN_ITEM_MIME_TYPE):
            event.acceptProposedAction()
            self._show_drop_hint()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Allow drop only over the map pixmap."""
        from src.gui.widgets.unified_list import KRAKEN_ITEM_MIME_TYPE

        if not event.mimeData().hasFormat(KRAKEN_ITEM_MIME_TYPE):
            event.ignore()
            return

        if not self.pixmap_item:
            event.ignore()
            return

        # Check if over map (convert to item-local coordinates)
        scene_pos = self.mapToScene(event.position().toPoint())
        item_pos = self.pixmap_item.mapFromScene(scene_pos)
        if self.pixmap_item.contains(item_pos):
            event.acceptProposedAction()
            self._show_drop_hint()
        else:
            event.ignore()
            self._hide_drop_hint()

    def dragLeaveEvent(self, event: "QDragLeaveEvent") -> None:
        """Handle drag leave event.

        Args:
            event: The drag leave event.
        """
        super().dragLeaveEvent(event)
        self._hide_drop_hint()

    def _show_drop_hint(self) -> None:
        """Show the blue drag-and-drop overlay indicating valid drop zone."""
        if self._drop_hint_overlay:
            self._drop_hint_overlay.setGeometry(self.viewport().rect())
            self._drop_hint_overlay.show()
            self._drop_hint_overlay.raise_()

    def _hide_drop_hint(self) -> None:
        """Hide the blue drag-and-drop overlay."""
        if self._drop_hint_overlay:
            self._drop_hint_overlay.hide()

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle drop of item from Project Explorer to create a marker.

        Parses the dropped MIME data and creates a new marker at the drop position.

        Args:
            event: The drop event containing MIME data.
        """
        self._hide_drop_hint()
        from src.gui.widgets.unified_list import KRAKEN_ITEM_MIME_TYPE

        if not event.mimeData().hasFormat(KRAKEN_ITEM_MIME_TYPE):
            event.ignore()
            return

        if not self.pixmap_item:
            event.ignore()
            return

        # Get drop position
        scene_pos = self.mapToScene(event.position().toPoint())

        # Check if within map bounds (convert to item-local coordinates)
        item_pos = self.pixmap_item.mapFromScene(scene_pos)
        if not self.pixmap_item.contains(item_pos):
            event.ignore()
            return

        # Calculate normalized coordinates
        # Calculate normalized coordinates
        norm_x, norm_y = self.coord_system.to_normalized(scene_pos)
        norm_x, norm_y = self.coord_system.clamp_normalized(norm_x, norm_y)

        # Parse MIME data
        if not self._handle_drop_data(event, norm_x, norm_y):
            event.ignore()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Handle context menu events for adding/removing markers and features.

        Args:
            event: The context menu event.
        """
        if not self.pixmap_item:
            return

        # Suppress context menu during drawing mode
        if self._drawing_mode:
            return

        # Check if we clicked on a marker or feature
        pos = event.pos()
        item = self.itemAt(pos)
        if isinstance(item, MarkerItem):
            self._show_marker_context_menu(item, event.globalPos())
        elif isinstance(item, (PathItem, RegionItem)):
            self._show_feature_context_menu(item, event.globalPos())
        else:
            # Clicked on map (or empty space)
            scene_pos = self.mapToScene(pos)
            item_pos = self.pixmap_item.mapFromScene(scene_pos)
            if self.pixmap_item.contains(item_pos):
                self._show_map_background_context_menu(scene_pos, event.globalPos())

    def set_map_width_meters(self, width_meters: float) -> None:
        """Sets the real-world width of the map for scale calculation.

        Args:
            width_meters: Width of the map image in meters.

        """
        if width_meters <= 0:
            logger.warning(f"Invalid map width: {width_meters}. Ignoring.")
            return

        self.map_width_meters = width_meters
        # Trigger repaint to update scale bar
        self.viewport().update()

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        """Draw overlay elements on top of the scene.

        Using drawForeground allows us to hook into the render loop correctly, even with
        an OpenGL viewport. We reset the transform to draw in window coordinates.
        """
        super().drawForeground(painter, rect)

        # Draw calibration line
        if self.calibration_mode and len(self.calibration_points) > 0:
            painter.save()

            theme = ThemeManager().get_theme()
            pen = QPen(QColor(theme.get("destructive", "#e74c3c")))
            pen.setWidth(2)
            pen.setStyle(Qt.DashLine)
            painter.setPen(pen)

            start_pos = self.calibration_points[0]
            end_pos = None

            if len(self.calibration_points) > 1:
                end_pos = self.calibration_points[1]
            else:
                # Use current mouse pos mapped to scene
                view_pos = self.mapFromGlobal(self.cursor().pos())
                end_pos = self.mapToScene(view_pos)

            if start_pos and end_pos:
                painter.drawLine(start_pos, end_pos)

                # Draw distance hint
                mid = (start_pos + end_pos) / 2
                import math

                dx = end_pos.x() - start_pos.x()
                dy = end_pos.y() - start_pos.y()
                dist_px = math.sqrt(dx * dx + dy * dy)

                # Draw text with backing
                text = f"{dist_px:.0f} px"
                font = painter.font()
                font.setBold(True)
                painter.setFont(font)
                fm = painter.fontMetrics()
                t_rect = fm.boundingRect(text)
                t_rect.moveCenter(mid.toPoint())
                t_rect.adjust(-4, -2, 4, 2)

                painter.setBrush(QColor(0, 0, 0, 180))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(t_rect, 4, 4)

                painter.setPen(Qt.white)
                painter.drawText(t_rect, Qt.AlignCenter, text)

            painter.restore()

        # Draw Scale Bar Overlay
        if self.pixmap_item and self.map_width_meters > 0:
            # Use pixmap bounding rect width for calculation to rely on image size,
            # not dynamic scene rect which can expand.
            image_width_px = self.pixmap_item.boundingRect().width()
            if image_width_px > 0:
                # Calculate resolution: meters per scene unit (pixel)
                # Calculate resolution: meters per scene unit (pixel)
                base_resolution = self.map_width_meters / image_width_px

                # Adjust for current view zoom (m11 is horizontal scale)
                view_scale = self.transform().m11()

                if view_scale > 0:
                    current_resolution = base_resolution / view_scale

                    # Save painter state (Scene coordinates)
                    painter.save()

                    # Reset transform to draw in Viewport (Pixel) coordinates
                    painter.resetTransform()

                    # Draw Scale Bar
                    self.scale_bar_painter.paint(
                        painter, QRectF(self.viewport().rect()), current_resolution
                    )

                    # Restore painter state
                    painter.restore()

    def start_calibration(self) -> None:
        """Enters calibration mode."""
        self.calibration_mode = True
        self.calibration_points.clear()
        self.setDragMode(QGraphicsView.DragMode.NoDrag)  # Prevent hand cursor
        self.setCursor(Qt.CrossCursor)
        self.viewport().update()

    def cancel_calibration(self) -> None:
        """Exits calibration mode."""
        self.calibration_mode = False
        self.calibration_points.clear()
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)  # Restore normal
        self.setCursor(Qt.ArrowCursor)
        self.viewport().update()

    def _show_icon_picker(self, marker_item: MarkerItem) -> None:
        """Shows the icon picker dialog for a marker.

        Args:
            marker_item: The marker to change the icon for.

        """
        dialog = IconPickerDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and (
            selected_icon := dialog.selected_icon
        ):
            marker_item.set_icon(selected_icon)
            self.change_marker_icon_requested.emit(marker_item.marker_id, selected_icon)

    def _show_color_picker(self, marker_item: MarkerItem) -> None:
        """Shows the color picker dialog for a marker.

        Args:
            marker_item: The marker to change the color for.

        """
        initial_color = marker_item.get_color() or "#FFFFFF"
        color = QColorDialog.getColor(
            QColor(initial_color), self, "Select Marker Color"
        )

        if color.isValid():
            color_hex = color.name().upper()
            marker_item.set_color(color_hex)
            self.change_marker_color_requested.emit(marker_item.marker_id, color_hex)

    def _handle_drop_data(
        self, event: QDropEvent, norm_x: float, norm_y: float
    ) -> bool:
        """Parses drop data and emits marker request."""
        from src.gui.widgets.unified_list import KRAKEN_ITEM_MIME_TYPE

        try:
            data_bytes = event.mimeData().data(KRAKEN_ITEM_MIME_TYPE).data()
            data = json.loads(data_bytes.decode("utf-8"))

            item_id = data.get("id")
            item_type = data.get("type")
            item_name = data.get("name", "Unknown")

            if item_id and item_type:
                self.marker_drop_requested.emit(
                    item_id, item_type, item_name, norm_x, norm_y
                )
                event.acceptProposedAction()
                logger.info(
                    f"Dropped {item_type} '{item_name}' at ({norm_x:.3f}, {norm_y:.3f})"
                )
                return True
        except Exception as e:
            logger.error(f"Failed to parse drop data: {e}")

        return False

    def _show_marker_context_menu(self, item: MarkerItem, global_pos: QPoint) -> None:
        """Shows context menu for a marker."""
        menu = QMenu(self)

        # Change Icon action
        change_icon_action = QAction(self)
        change_icon_action.setText("Change Icon...")
        change_icon_action.triggered.connect(lambda: self._show_icon_picker(item))
        menu.addAction(change_icon_action)

        # Change Color action
        change_color_action = QAction(self)
        change_color_action.setText("Change Color...")
        change_color_action.triggered.connect(lambda: self._show_color_picker(item))
        menu.addAction(change_color_action)

        menu.addSeparator()

        # Delete action
        delete_action = QAction(self)
        delete_action.setText("Delete Marker")
        delete_action.triggered.connect(
            lambda: self.delete_marker_requested.emit(item.marker_id)
        )
        menu.addAction(delete_action)
        menu.exec(global_pos)

    def _show_map_background_context_menu(
        self, scene_pos: QPointF, global_pos: QPoint
    ) -> None:
        """Shows context menu for adding features at a specific location."""
        norm_x, norm_y = self.coord_system.to_normalized(scene_pos)
        menu = QMenu(self)

        add_action = QAction(self)
        add_action.setText("Add Marker Here")
        add_action.triggered.connect(
            lambda: self.add_marker_requested.emit(norm_x, norm_y)
        )
        menu.addAction(add_action)

        menu.addSeparator()

        draw_path_action = QAction(self)
        draw_path_action.setText("Draw Path Here...")
        draw_path_action.triggered.connect(lambda: self.start_drawing("path"))
        menu.addAction(draw_path_action)

        draw_region_action = QAction(self)
        draw_region_action.setText("Draw Region Here...")
        draw_region_action.triggered.connect(lambda: self.start_drawing("region"))
        menu.addAction(draw_region_action)

        menu.exec(global_pos)

    def _show_feature_context_menu(
        self, item: QGraphicsObject, global_pos: QPoint
    ) -> None:
        """Shows context menu for a path or region feature.

        Args:
            item: The PathItem or RegionItem.
            global_pos: Global screen position for the menu.

        """
        menu = QMenu(self)

        feature_label = "Path" if isinstance(item, PathItem) else "Region"

        # Edit Style action
        edit_style_action = QAction(self)
        edit_style_action.setText(f"Edit {feature_label} Style...")
        edit_style_action.triggered.connect(
            lambda: self._show_feature_style_dialog(item)
        )
        menu.addAction(edit_style_action)

        # Edit Vertices action
        edit_vertices_action = QAction(self)
        edit_vertices_action.setText("Edit Vertices...")
        edit_vertices_action.triggered.connect(
            lambda: self._start_vertex_editing(item)
        )
        menu.addAction(edit_vertices_action)

        menu.addSeparator()

        # Delete action
        delete_action = QAction(self)
        delete_action.setText(f"Delete {feature_label}")
        delete_action.triggered.connect(
            lambda: self.delete_marker_requested.emit(item.marker_id)
        )
        menu.addAction(delete_action)
        menu.exec(global_pos)

    # ------------------------------------------------------------------
    # Drawing Mode
    # ------------------------------------------------------------------

    def start_drawing(self, feature_type: str) -> None:
        """Enters drawing mode for paths or regions.

        Click to add vertices; double-click to finish; Escape to cancel.

        Args:
            feature_type: 'path' or 'region'.

        """
        self._drawing_mode = feature_type
        self._drawing_vertices.clear()
        self._clear_drawing_preview()
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setCursor(Qt.CursorShape.CrossCursor)
        logger.info(f"Drawing mode started: {feature_type}")

    def cancel_drawing(self) -> None:
        """Exits drawing mode without saving."""
        self._drawing_mode = None
        self._drawing_vertices.clear()
        self._clear_drawing_preview()
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.drawing_cancelled.emit()
        logger.info("Drawing cancelled")

    def finish_drawing(self) -> None:
        """Completes the current drawing and emits the geometry.

        Converts scene-coordinate vertices to normalized coordinates
        and emits ``drawing_finished(feature_type, geometry)``.
        """
        if not self._drawing_mode or not self.pixmap_item:
            self.cancel_drawing()
            return

        min_points = 2 if self._drawing_mode == "path" else 3
        if len(self._drawing_vertices) < min_points:
            logger.warning(
                f"Need at least {min_points} points for {self._drawing_mode}"
            )
            self.cancel_drawing()
            return

        # Convert scene coords to normalized
        geometry = []
        for sp in self._drawing_vertices:
            nx, ny = self.coord_system.to_normalized(sp)
            nx, ny = self.coord_system.clamp_normalized(nx, ny)
            geometry.append({
                "x": round(nx, NORMALIZED_COORD_PRECISION),
                "y": round(ny, NORMALIZED_COORD_PRECISION),
            })

        feature_type = self._drawing_mode
        logger.info(
            f"Drawing finished: {feature_type} with {len(geometry)} vertices"
        )

        # Clean up drawing state
        self._drawing_mode = None
        self._drawing_vertices.clear()
        self._clear_drawing_preview()
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setCursor(Qt.CursorShape.ArrowCursor)

        self.drawing_finished.emit(feature_type, geometry)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Handle double-click to finish drawing.

        Args:
            event: The mouse double-click event.

        """
        if self._drawing_mode:
            self.finish_drawing()
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: "QKeyEvent") -> None:
        """Handle key presses for drawing/editing modes (Escape to cancel/finish).

        Args:
            event: The key press event.

        """
        if event.key() == Qt.Key.Key_Escape:
            if self._drawing_mode:
                self.cancel_drawing()
                return
            if self._editing_feature_id:
                self._finish_vertex_editing()
                return
        super().keyPressEvent(event)

    def _add_drawing_vertex(self, scene_pos: QPointF) -> None:
        """Adds a vertex to the current drawing.

        Args:
            scene_pos: The vertex position in scene coordinates.

        """
        self._drawing_vertices.append(scene_pos)

        # Add visible dot
        from PySide6.QtWidgets import QGraphicsEllipseItem

        dot = QGraphicsEllipseItem(-3, -3, 6, 6)
        dot.setPos(scene_pos)
        dot.setBrush(QBrush(QColor("#e74c3c")))
        dot.setPen(QPen(QColor("#FFFFFF"), 1))
        dot.setZValue(LAYER_UI_OVERLAY)
        self.scene.addItem(dot)
        self._drawing_dots.append(dot)

        self._update_drawing_preview(scene_pos)

    def _update_drawing_preview(self, mouse_pos: QPointF) -> None:
        """Updates the rubber-band preview path during drawing.

        Args:
            mouse_pos: Current mouse position in scene coordinates.

        """
        if not self._drawing_vertices:
            return

        # Remove old preview
        if self._drawing_preview_item:
            self.scene.removeItem(self._drawing_preview_item)
            self._drawing_preview_item = None

        path = QPainterPath()
        path.moveTo(self._drawing_vertices[0])
        for pt in self._drawing_vertices[1:]:
            path.lineTo(pt)
        # Rubber band to mouse
        path.lineTo(mouse_pos)
        # Close for region preview
        if self._drawing_mode == "region" and len(self._drawing_vertices) >= 2:
            path.lineTo(self._drawing_vertices[0])

        self._drawing_preview_item = QGraphicsPathItem(path)
        pen = QPen(QColor("#e74c3c"), 2)
        pen.setCosmetic(True)
        pen.setStyle(Qt.PenStyle.DashLine)
        self._drawing_preview_item.setPen(pen)
        if self._drawing_mode == "region":
            self._drawing_preview_item.setBrush(QBrush(QColor(231, 76, 60, 40)))
        self._drawing_preview_item.setZValue(LAYER_UI_OVERLAY)
        self.scene.addItem(self._drawing_preview_item)

    def _clear_drawing_preview(self) -> None:
        """Removes all drawing preview items from the scene."""
        if self._drawing_preview_item:
            self.scene.removeItem(self._drawing_preview_item)
            self._drawing_preview_item = None
        for dot in self._drawing_dots:
            self.scene.removeItem(dot)
        self._drawing_dots.clear()

    @property
    def is_drawing(self) -> bool:
        """True when the view is in drawing mode.

        Returns:
            bool: Whether drawing mode is active.

        """
        return self._drawing_mode is not None

    @property
    def drawing_mode(self) -> Optional[str]:
        """Returns the current drawing mode type.

        Returns:
            Optional[str]: 'path', 'region', or None.

        """
        return self._drawing_mode

    # ------------------------------------------------------------------
    # Feature Style Editing
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_color_css(color_str: str) -> str:
        """Validates a color string for safe use in QSS stylesheets.

        Returns the validated hex color or a safe fallback.

        Args:
            color_str: A candidate color string (e.g. '#FF0000').

        Returns:
            A validated hex color safe for use in CSS.

        """
        c = QColor(color_str)
        if c.isValid():
            return c.name()
        return "#808080"  # safe grey fallback

    def _show_feature_style_dialog(self, item: "_FeatureItemBase") -> None:
        """Opens an inline dialog to edit a feature's visual style.

        Args:
            item: The PathItem or RegionItem to edit.

        """
        from PySide6.QtWidgets import (
            QDialog,
            QDialogButtonBox,
            QDoubleSpinBox,
            QFormLayout,
        )
        from src.gui.widgets.map.feature_items import (
            DEFAULT_REGION_FILL_COLOR,
            DEFAULT_STROKE_COLOR,
            DEFAULT_STROKE_WIDTH,
        )

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit {item.label} Style")
        dialog.setMinimumWidth(300)
        layout = QFormLayout(dialog)

        # Stroke color
        stroke_init = self._safe_color_css(
            item._style.get("stroke_color", DEFAULT_STROKE_COLOR)
        )
        stroke_btn = QPushButton(stroke_init)
        stroke_btn.setStyleSheet(
            f"background-color: {stroke_init}; color: white; padding: 4px 12px;"
        )
        _stroke_color = [stroke_init]

        def _pick_stroke() -> None:
            c = QColorDialog.getColor(QColor(_stroke_color[0]), dialog, "Stroke Color")
            if c.isValid():
                safe = c.name()
                _stroke_color[0] = safe
                stroke_btn.setText(safe)
                stroke_btn.setStyleSheet(
                    f"background-color: {safe}; color: white; padding: 4px 12px;"
                )

        stroke_btn.clicked.connect(_pick_stroke)
        layout.addRow("Stroke Color:", stroke_btn)

        # Stroke width
        width_spin = QDoubleSpinBox()
        width_spin.setRange(0.5, 20.0)
        width_spin.setSingleStep(0.5)
        width_spin.setValue(item._style.get("stroke_width", DEFAULT_STROKE_WIDTH))
        layout.addRow("Stroke Width:", width_spin)

        # Fill color (regions only)
        fill_btn: Optional[QPushButton] = None
        _fill_color: list = [None]
        if isinstance(item, RegionItem):
            fill_init = self._safe_color_css(
                item._style.get("fill_color", DEFAULT_REGION_FILL_COLOR)
            )
            fill_btn = QPushButton(fill_init)
            fill_btn.setStyleSheet(
                f"background-color: {fill_init}; color: white; padding: 4px 12px;"
            )
            _fill_color = [fill_init]

            def _pick_fill() -> None:
                c = QColorDialog.getColor(
                    QColor(_fill_color[0]),
                    dialog,
                    "Fill Color",
                    QColorDialog.ColorDialogOption.ShowAlphaChannel,
                )
                if c.isValid():
                    safe = c.name()
                    _fill_color[0] = c.name(QColor.NameFormat.HexArgb)
                    fill_btn.setText(_fill_color[0])
                    fill_btn.setStyleSheet(
                        f"background-color: {safe}; color: white; "
                        f"padding: 4px 12px;"
                    )

            fill_btn.clicked.connect(_pick_fill)
            layout.addRow("Fill Color:", fill_btn)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_style = dict(item._style)
            new_style["stroke_color"] = _stroke_color[0]
            new_style["stroke_width"] = width_spin.value()
            if isinstance(item, RegionItem) and _fill_color[0]:
                new_style["fill_color"] = _fill_color[0]

            item._style = new_style
            item.update()  # Repaint
            self.feature_style_changed.emit(item.marker_id, new_style)
            logger.info(f"Style updated for {item.marker_id}: {new_style}")

    # ------------------------------------------------------------------
    # Vertex Editing
    # ------------------------------------------------------------------

    def _start_vertex_editing(self, item: "_FeatureItemBase") -> None:
        """Enters vertex editing mode for a feature.

        Shows draggable handles on each vertex and ghost midpoint handles
        on each segment. Handles can be moved to reshape the feature.
        Right-click a vertex handle to delete it. Press Escape to finish.

        Args:
            item: The PathItem or RegionItem to edit.

        """
        self._finish_vertex_editing()  # Clean up any previous session
        self._editing_feature_id = item.marker_id

        geometry = item._geometry
        if not geometry or not self.pixmap_item:
            return

        # Save original style and apply editing visual feedback
        self._editing_original_style = dict(item._style)
        item._style["dash_pattern"] = self._EDIT_DASH_PATTERN
        item._style["stroke_color"] = self._EDIT_STROKE_COLOR
        item._style["stroke_width"] = self._EDIT_STROKE_WIDTH
        item.update()

        rect = self.pixmap_item.sceneBoundingRect()
        for i, pt in enumerate(geometry):
            sx = rect.left() + pt["x"] * rect.width()
            sy = rect.top() + pt["y"] * rect.height()
            handle = _VertexHandle(i, self._on_vertex_moved, self._on_vertex_deleted)
            handle.setPos(sx, sy)
            handle.setZValue(LAYER_UI_OVERLAY + 1)
            self.scene.addItem(handle)
            self._vertex_handles.append(handle)

        self._rebuild_midpoint_handles()
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        logger.info(
            f"Vertex editing started for {item.marker_id} "
            f"({len(geometry)} vertices)"
        )

    def _rebuild_midpoint_handles(self) -> None:
        """Rebuilds ghost midpoint handles between each pair of vertices.

        Called after vertex insert/delete to keep midpoints in sync.
        """
        # Remove old midpoint handles
        for mh in self._midpoint_handles:
            self.scene.removeItem(mh)
        self._midpoint_handles.clear()

        item = self.feature_items.get(self._editing_feature_id or "")
        if not item or not item._geometry or not self.pixmap_item:
            return

        rect = self.pixmap_item.sceneBoundingRect()
        geometry = item._geometry
        n = len(geometry)
        is_region = isinstance(item, RegionItem)
        seg_count = n if is_region else n - 1

        for i in range(seg_count):
            j = (i + 1) % n
            pt_a = geometry[i]
            pt_b = geometry[j]
            mx = (pt_a["x"] + pt_b["x"]) / 2.0
            my = (pt_a["y"] + pt_b["y"]) / 2.0
            sx = rect.left() + mx * rect.width()
            sy = rect.top() + my * rect.height()

            mh = _MidpointHandle(i, self._on_midpoint_insert)
            mh.setPos(sx, sy)
            self.scene.addItem(mh)
            self._midpoint_handles.append(mh)

    def _update_midpoint_positions(self) -> None:
        """Repositions existing midpoint handles without recreating them.

        Called during interactive vertex drag to keep green segment
        markers in sync with the moving geometry.  This is cheaper
        than a full ``_rebuild_midpoint_handles`` because it avoids
        scene add/remove overhead.
        """
        item = self.feature_items.get(self._editing_feature_id or "")
        if not item or not item._geometry or not self.pixmap_item:
            return

        rect = self.pixmap_item.sceneBoundingRect()
        geometry = item._geometry
        n = len(geometry)
        is_region = isinstance(item, RegionItem)
        seg_count = n if is_region else n - 1

        for idx, mh in enumerate(self._midpoint_handles):
            if idx >= seg_count:
                break
            j = (idx + 1) % n
            pt_a = geometry[idx]
            pt_b = geometry[j]
            mx = (pt_a["x"] + pt_b["x"]) / 2.0
            my = (pt_a["y"] + pt_b["y"]) / 2.0
            sx = rect.left() + mx * rect.width()
            sy = rect.top() + my * rect.height()
            mh.setPos(sx, sy)

    def _on_vertex_moved(self, index: int, new_scene_pos: QPointF) -> None:
        """Callback when a vertex handle is dragged to a new position.

        Applies optional snapping to nearby existing vertices,
        then updates the underlying feature geometry in real time
        and repositions midpoint handles so green segment markers
        stay in sync.

        Args:
            index: The vertex index that was moved.
            new_scene_pos: The new scene position.

        """
        if not self._editing_feature_id or not self.pixmap_item:
            return

        item = self.feature_items.get(self._editing_feature_id)
        if not item:
            return

        # --- Snapping ---
        snap_pos = self._snap_to_nearby_vertex(index, new_scene_pos)

        # Convert scene pos → normalized
        rect = self.pixmap_item.sceneBoundingRect()
        nx = (snap_pos.x() - rect.left()) / rect.width()
        ny = (snap_pos.y() - rect.top()) / rect.height()
        nx = max(0.0, min(1.0, nx))
        ny = max(0.0, min(1.0, ny))

        if index < len(item._geometry):
            # Update in-place to avoid allocations during interactive drag
            pt = item._geometry[index]
            pt["x"] = round(nx, 6)
            pt["y"] = round(ny, 6)
            # Rebuild visual
            if isinstance(item, PathItem):
                item._build_path()
                item._position_label()
            elif isinstance(item, RegionItem):
                item._build_polygon()
                item._position_label()
            item.prepareGeometryChange()
            item.update()

            # Reposition midpoint handles to keep segment markers in sync
            self._update_midpoint_positions()

    def _snap_to_nearby_vertex(
        self, moving_index: int, scene_pos: QPointF
    ) -> QPointF:
        """Snaps a position to the nearest existing vertex within snap radius.

        Args:
            moving_index: Index of the vertex being moved (excluded from snap targets).
            scene_pos: Current scene position of the handle.

        Returns:
            Snapped scene position, or the original if no nearby vertex found.

        """
        # Convert snap radius from screen pixels to scene units
        view_scale = self.transform().m11() if self.transform().m11() > 0 else 1.0
        snap_radius_scene = MAP_SNAP_RADIUS_PX / view_scale

        best_dist = snap_radius_scene
        best_pos = scene_pos

        for handle in self._vertex_handles:
            if handle.index == moving_index:
                continue
            dx = handle.pos().x() - scene_pos.x()
            dy = handle.pos().y() - scene_pos.y()
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < best_dist:
                best_dist = dist
                best_pos = handle.pos()

        return best_pos

    def _on_vertex_deleted(self, index: int) -> None:
        """Removes a vertex from the feature being edited.

        Called when the user right-clicks a vertex handle. Enforces
        minimum vertex counts (2 for paths, 3 for regions).

        Args:
            index: The index of the vertex to remove.

        """
        item = self.feature_items.get(self._editing_feature_id or "")
        if not item or not item._geometry:
            return

        min_verts = 3 if isinstance(item, RegionItem) else 2
        if len(item._geometry) <= min_verts:
            logger.warning(
                f"Cannot delete vertex: minimum {min_verts} vertices required"
            )
            return

        # Remove the vertex from geometry
        del item._geometry[index]

        # Rebuild visual
        if isinstance(item, PathItem):
            item._build_path()
            item._position_label()
        elif isinstance(item, RegionItem):
            item._build_polygon()
            item._position_label()
        item.prepareGeometryChange()
        item.update()

        # Rebuild all handles (indices have shifted)
        self._rebuild_vertex_handles(item)
        self._rebuild_midpoint_handles()
        logger.info(f"Deleted vertex {index}, {len(item._geometry)} remaining")

    def _on_midpoint_insert(self, segment_index: int, scene_pos: QPointF) -> None:
        """Inserts a new vertex at the midpoint of a segment.

        Called when the user drags a midpoint ghost handle. The ghost
        handle is converted into a real vertex.

        Args:
            segment_index: Index of the segment (vertex before the midpoint).
            scene_pos: Scene position of the new vertex.

        """
        item = self.feature_items.get(self._editing_feature_id or "")
        if not item or not item._geometry or not self.pixmap_item:
            return

        # Convert scene pos → normalized
        rect = self.pixmap_item.sceneBoundingRect()
        nx = (scene_pos.x() - rect.left()) / rect.width()
        ny = (scene_pos.y() - rect.top()) / rect.height()
        nx = max(0.0, min(1.0, nx))
        ny = max(0.0, min(1.0, ny))

        new_pt = {"x": round(nx, 6), "y": round(ny, 6)}
        item._geometry.insert(segment_index + 1, new_pt)

        # Rebuild visual
        if isinstance(item, PathItem):
            item._build_path()
            item._position_label()
        elif isinstance(item, RegionItem):
            item._build_polygon()
            item._position_label()
        item.prepareGeometryChange()
        item.update()

        # Rebuild all handles (indices have shifted)
        self._rebuild_vertex_handles(item)
        self._rebuild_midpoint_handles()
        logger.info(
            f"Inserted vertex after index {segment_index}, "
            f"{len(item._geometry)} total"
        )

    def _rebuild_vertex_handles(self, item: "_FeatureItemBase") -> None:
        """Removes and recreates all vertex handles for the current feature.

        Called after vertex insertion or deletion to keep handle indices
        synchronised with the geometry array.

        Args:
            item: The feature item whose handles need rebuilding.

        """
        for handle in self._vertex_handles:
            self.scene.removeItem(handle)
        self._vertex_handles.clear()

        if not item._geometry or not self.pixmap_item:
            return

        rect = self.pixmap_item.sceneBoundingRect()
        for i, pt in enumerate(item._geometry):
            sx = rect.left() + pt["x"] * rect.width()
            sy = rect.top() + pt["y"] * rect.height()
            handle = _VertexHandle(i, self._on_vertex_moved, self._on_vertex_deleted)
            handle.setPos(sx, sy)
            handle.setZValue(LAYER_UI_OVERLAY + 1)
            self.scene.addItem(handle)
            self._vertex_handles.append(handle)

    def _finish_vertex_editing(self) -> None:
        """Commits vertex edits and removes handles.

        Restores the original feature style and emits
        ``feature_geometry_changed`` with the updated normalized
        coordinates so the command layer can persist the change.
        """
        finished_id: Optional[str] = None
        finished_geometry: Optional[list] = None

        if self._editing_feature_id:
            item = self.feature_items.get(self._editing_feature_id)
            if item:
                # Restore original style
                if self._editing_original_style is not None:
                    item._style = self._editing_original_style
                    self._editing_original_style = None
                    item.update()
                if item._geometry:
                    finished_id = self._editing_feature_id
                    finished_geometry = list(item._geometry)

        # Clear editing state BEFORE emitting signal so that
        # is_editing_vertices returns False when _update_mode_indicator
        # is called from the connected slot.
        self._editing_feature_id = None
        for handle in self._vertex_handles:
            self.scene.removeItem(handle)
        self._vertex_handles.clear()
        for mh in self._midpoint_handles:
            self.scene.removeItem(mh)
        self._midpoint_handles.clear()
        if not self._drawing_mode:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        # Emit after state is fully cleared
        if finished_id and finished_geometry:
            self.feature_geometry_changed.emit(finished_id, finished_geometry)
            logger.info(f"Vertex editing finished for {finished_id}")

    @property
    def is_editing_vertices(self) -> bool:
        """True when vertex editing mode is active.

        Returns:
            bool: Whether a feature's vertices are being edited.

        """
        return self._editing_feature_id is not None

    def show_trajectory(self, marker_id: str, keyframes: list) -> None:
        """Visualizes the trajectory path and keyframes.

        Args:
            marker_id: The ID of the marker owning this trajectory.
            keyframes: List of Keyframe objects.

        """
        self.clear_trajectory()
        if not keyframes or len(keyframes) < 2:
            return

        # Create Keyframe Dots (store them first, then draw path)
        # Scale with zoom: target 6px on screen, minimum 3 scene units for clickability
        view_scale = self.transform().m11() if self.transform().m11() > 0 else 1.0
        dot_radius = max(3.0 / view_scale, 3.0)

        for kf in keyframes:
            pos = self.coord_system.to_scene(kf.x, kf.y)
            # Create interactive item
            dot = KeyframeItem(
                marker_id,
                kf.t,
                kf.x,
                kf.y,
                QRectF(-dot_radius, -dot_radius, dot_radius * 2, dot_radius * 2),
                self._on_keyframe_dropped,
                self._update_trajectory_path,  # Live update callback
            )
            dot.setPos(pos)
            dot.setBrush(QBrush(QColor(KEYFRAME_COLOR_DEFAULT)))  # Yellow dots
            dot.setPen(QPen(Qt.PenStyle.NoPen))
            dot.setZValue(LAYER_MARKERS + 1)  # Above markers for editability
            self.scene.addItem(dot)
            self.keyframe_items.append(dot)

            # Add date label if calendar converter is available
            if self._calendar_converter:
                try:
                    date_str = self._calendar_converter.format_date(kf.t)
                except Exception as e:
                    logger.warning(
                        f"Calendar formatting failed for keyframe at {kf.t}: {e}"
                    )
                    date_str = f"{kf.t:.0f}"
            else:
                date_str = f"{kf.t:.0f}"

            label = QGraphicsSimpleTextItem(date_str)
            # Position at the dot center (scene coords)
            label.setPos(pos)
            label.setBrush(QBrush(QColor(KEYFRAME_LABEL_COLOR)))
            font = QFont(KEYFRAME_LABEL_FONT_FAMILY, KEYFRAME_LABEL_FONT_SIZE)
            label.setFont(font)
            label.setZValue(LAYER_MARKERS + 2)
            # Ignore transformations to keep constant screen size
            label.setFlag(
                QGraphicsSimpleTextItem.GraphicsItemFlag.ItemIgnoresTransformations
            )
            # Apply offset in screen pixels via transform
            label.setTransform(
                QTransform().translate(KEYFRAME_LABEL_OFFSET_X, KEYFRAME_LABEL_OFFSET_Y)
            )
            self.scene.addItem(label)
            self.keyframe_label_items.append(label)

        # Draw path initially
        self._update_trajectory_path()
        self._update_label_scales()

        # Pulsing Animation on first use
        if self.trigger_first_use_animation:
            logger.debug(
                f"Triggering pulsing animation for {len(self.keyframe_items)} keyframes"
            )
            self.trigger_first_use_animation = False
            for dot in self.keyframe_items:
                self._pulse_item(dot)

    def _pulse_item(self, item: QGraphicsObject) -> None:
        """Pulses the given item 3 times (scale 1.0 -> 1.1 -> 1.0)."""
        # Ensure transformation origin is centered for scaling
        item.setTransformOriginPoint(0, 0)

        animation = QPropertyAnimation(item, b"scale_val")
        animation.setDuration(600)
        animation.setStartValue(1.0)
        animation.setKeyValueAt(0.5, 1.1)
        animation.setEndValue(1.0)
        animation.setLoopCount(3)

        # Store animation to prevent garbage collection before it finishes
        self._animations.append(animation)
        animation.finished.connect(lambda: self._animations.remove(animation))

        animation.start()  # Keep alive until removal from self._animations

    def _show_edit_keyframe_dialog(self, item: KeyframeItem) -> None:
        """Shows a dialog to edit keyframe properties manually."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Keyframe")
        layout = QVBoxLayout(dialog)

        # Position (X)
        x_layout = QHBoxLayout()
        x_layout.addWidget(QLabel("Position X:"))
        x_input = QLineEdit(f"{item.original_x:.3f}")
        x_layout.addWidget(x_input)
        layout.addLayout(x_layout)

        # Position (Y)
        y_layout = QHBoxLayout()
        y_layout.addWidget(QLabel("Position Y:"))
        y_input = QLineEdit(f"{item.original_y:.3f}")
        y_layout.addWidget(y_input)
        layout.addLayout(y_layout)

        # Time
        t_layout = QHBoxLayout()
        t_layout.addWidget(QLabel("Time:"))
        t_input = QLineEdit(f"{item.t:.1f}")
        t_layout.addWidget(t_input)
        layout.addLayout(t_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        if dialog.exec() == QDialog.Accepted:
            try:
                new_x = float(x_input.text())
                new_y = float(y_input.text())
                new_t = float(t_input.text())
                # Emit request to parent (MapWidget -> Controller)
                # Since MapGraphicsView is internal, we can emit a signal
                # and let MapWidget handle it.
                self.keyframe_edit_requested.emit(item.marker_id, new_t, new_x, new_y)
            except ValueError:
                logger.error("Invalid input for keyframe edit")

    def _update_label_scales(self) -> None:
        """Updates the scale of keyframe labels based on current zoom level.

        Logic:
        - Scale < 1 (Zoom Out): Keep constant screen size (s=1.0).
        - Scale > 1 (Zoom In): Grow with map (s=scale), but cap at MAX_SCALE.
        """
        view_scale = self.transform().m11()
        if view_scale <= 0:
            return

        # Calculate limits for scale factor s:
        # eff_size = Base * s  =>  s = eff_size / Base
        min_s = KEYFRAME_LABEL_MIN_SIZE_PT / KEYFRAME_LABEL_FONT_SIZE
        max_s = KEYFRAME_LABEL_MAX_SIZE_PT / KEYFRAME_LABEL_FONT_SIZE

        # Clamp view_scale within these bounds
        s = max(min_s, min(view_scale, max_s))

        transform = (
            QTransform()
            .translate(KEYFRAME_LABEL_OFFSET_X, KEYFRAME_LABEL_OFFSET_Y)
            .scale(s, s)
        )

        for label in self.keyframe_label_items:
            label.setTransform(transform)

    def _update_trajectory_path(self) -> None:
        """Re-draws the trajectory path based on current keyframe positions."""
        if not self.keyframe_items or len(self.keyframe_items) < 2:
            if self.trajectory_path_item:
                self.scene.removeItem(self.trajectory_path_item)
                self.trajectory_path_item = None
            return

        # Sort items by time to ensure correct path order
        sorted_items = sorted(self.keyframe_items, key=lambda item: item.t)

        path = QPainterPath()
        start = sorted_items[0].scenePos()
        path.moveTo(start)

        for i in range(1, len(sorted_items)):
            path.lineTo(sorted_items[i].scenePos())

        # If path item doesn't exist, create it
        if not self.trajectory_path_item:
            self.trajectory_path_item = self._create_trajectory_item(path)
            self.scene.addItem(self.trajectory_path_item)
        else:
            # Update existing item
            self.trajectory_path_item.setPath(path)

    def _create_trajectory_item(self, path: QPainterPath) -> QGraphicsPathItem:
        """Creates and configures the trajectory path item."""
        item = QGraphicsPathItem(path)
        pen = QPen(QColor(TRAJECTORY_PATH_COLOR), 1)  # Blue path, thin line
        pen.setStyle(Qt.PenStyle.DashLine)
        item.setPen(pen)
        item.setZValue(LAYER_TRAJECTORIES)
        return item

    def _on_keyframe_dropped(self, item: KeyframeItem) -> None:
        """Callback when a keyframe dot is released after dragging."""
        scene_pos = item.scenePos()
        norm_pos = self.coord_system.to_normalized(scene_pos)
        x, y = norm_pos

        logger.info(
            f"Keyframe dropped for {item.marker_id} at t={item.t}: ({x:.3f}, {y:.3f})"
        )
        self.keyframe_moved.emit(item.marker_id, item.t, x, y)

    def clear_trajectory(self) -> None:
        """Clears the rendered trajectory path, keyframes, and labels."""
        if self.trajectory_path_item:
            self.scene.removeItem(self.trajectory_path_item)
            self.trajectory_path_item = None

        for item in self.keyframe_items:
            self.scene.removeItem(item)
        self.keyframe_items.clear()

        for label in self.keyframe_label_items:
            self.scene.removeItem(label)
        self.keyframe_label_items.clear()

    def set_calendar_converter(self, converter: object) -> None:
        """Sets the calendar converter for formatting keyframe date labels."""
        self._calendar_converter = converter

    def set_keyframe_pinned(self, marker_id: str, t: float, pinned: bool) -> None:
        """Set visual pinned state for a specific keyframe."""
        for item in self.keyframe_items:
            if (
                isinstance(item, KeyframeItem)
                and item.marker_id == marker_id
                and abs(item.t - t) < KEYFRAME_TIME_EPSILON
            ):
                item.set_pinned(pinned)
                logger.debug(f"Set keyframe {marker_id} at t={t} pinned={pinned}")
                return

    def update_keyframe_label(self, marker_id: str, t: float, new_time: float) -> None:
        """Updates the label of a specific keyframe to show a new time/date.

        Used for live feedback during Clock Mode.
        """
        for i, item in enumerate(self.keyframe_items):
            if (
                isinstance(item, KeyframeItem)
                and item.marker_id == marker_id
                and abs(item.t - t) < KEYFRAME_TIME_EPSILON
            ):
                # Found the item, update corresponding label
                if i < len(self.keyframe_label_items):
                    label = self.keyframe_label_items[i]
                    if self._calendar_converter:
                        try:
                            text = self._calendar_converter.format_date(new_time)
                        except Exception as e:
                            logger.warning(
                                f"Calendar formatting failed for time {new_time}: {e}"
                            )
                            text = f"{new_time:.0f}"
                    else:
                        text = f"{new_time:.0f}"
                    label.setText(text)
                return
