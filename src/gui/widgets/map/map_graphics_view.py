"""Map Graphics View Module.

Provides the MapGraphicsView class for rendering and interacting with
the map.  MapGraphicsView acts as a thin coordinator that delegates to
focused sub-components:

* :class:`~src.gui.widgets.map.drawing_tool.DrawingTool`
* :class:`~src.gui.widgets.map.vertex_editor.VertexEditor`
* :class:`~src.gui.widgets.map.marker_manager.MarkerManager`
* :class:`~src.gui.widgets.map.trajectory_renderer.TrajectoryRenderer`
* :class:`~src.gui.widgets.map.interaction_handler.InteractionHandler`
"""

import logging
import math
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from PySide6.QtCore import (
    Property,
    QPointF,
    QRectF,
    QSettings,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QContextMenuEvent,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QFont,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsObject,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSceneHoverEvent,
    QGraphicsSceneMouseEvent,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QLabel,
    QSizePolicy,
    QStyleOptionGraphicsItem,
    QWidget,
)

from src.app.constants import (
    MAP_DEFAULT_WIDTH_METERS,
    MAP_LAYER_Z_MAP_BG,
    MAP_LAYER_Z_MARKERS,
    MAP_LAYER_Z_TRAJECTORIES,
    MAP_LAYER_Z_UI_OVERLAY,
    MAP_SNAP_INDICATOR_BORDER_COLOR,
    MAP_SNAP_INDICATOR_BORDER_WIDTH,
    MAP_SNAP_INDICATOR_EDGE_COLOR,
    MAP_SNAP_INDICATOR_RADIUS,
    MAP_SNAP_INDICATOR_VERTEX_COLOR,
    MAP_ZOOM_IN_FACTOR,
)
from src.core.theme_manager import ThemeManager
from src.gui.widgets.map.coordinate_system import MapCoordinateSystem
from src.gui.widgets.map.drawing_tool import DrawingTool
from src.gui.widgets.map.feature_items import PathItem, RegionItem
from src.gui.widgets.map.interaction_handler import InteractionHandler
from src.gui.widgets.map.label_manager import LabelManager
from src.gui.widgets.map.marker_item import MarkerItem
from src.gui.widgets.map.marker_manager import MarkerManager
from src.gui.widgets.map.scale_bar_painter import ScaleBarPainter
from src.gui.widgets.map.snapping_manager import SnappingManager, SnapType
from src.gui.widgets.map.trajectory_renderer import TrajectoryRenderer
from src.gui.widgets.map.vertex_editor import VertexEditor

if TYPE_CHECKING:
    from src.gui.widgets.map.map_layer_model import MapLayerModel

logger = logging.getLogger(__name__)

# Layer Z-Values (backward-compatible aliases for constants)
LAYER_MAP_BG = MAP_LAYER_Z_MAP_BG
LAYER_TRAJECTORIES = MAP_LAYER_Z_TRAJECTORIES
LAYER_MARKERS = MAP_LAYER_Z_MARKERS
LAYER_UI_OVERLAY = MAP_LAYER_Z_UI_OVERLAY

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

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Handle icon clicks - clock for Clock Mode, X for delete.

        Args:
            event: The mouse press event.
        """
        # Determine which icon was clicked based on local position
        click_x = event.pos().x()

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
            self.setToolTip(
                "<div style='width: 150px;'>"
                "💡 Tip: Hover keyframes to edit position or time"
                "</div>"
            )
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


class MapGraphicsView(QGraphicsView):
    """Graphics view for displaying a map image with draggable markers.

    Acts as a thin coordinator that delegates to focused sub-components:

    * :class:`DrawingTool` — Path/region drawing mode
    * :class:`VertexEditor` — Vertex editing with handles and snapping
    * :class:`MarkerManager` — CRUD for markers and features
    * :class:`TrajectoryRenderer` — Trajectory path and keyframes
    * :class:`InteractionHandler` — Context menus, drag-drop, dialogs

    Signals:
        marker_moved: Emitted when a marker is dragged to a new position.
                     Args: (marker_id: str, x: float, y: float)
                     Coordinates are normalized [0.0, 1.0] relative to map.
    """

    # -- Marker signals --
    marker_moved = Signal(str, float, float)
    marker_clicked = Signal(str, str)  # marker_id, object_type
    add_marker_requested = Signal(float, float)  # x, y (normalized)
    delete_marker_requested = Signal(str)  # marker_id
    change_marker_icon_requested = Signal(str, str)  # marker_id, new_icon
    change_marker_color_requested = Signal(str, str)  # marker_id, new_color_hex
    marker_drop_requested = Signal(str, str, str, float, float)

    # -- Coordinate signal --
    mouse_coordinates_changed = Signal(float, float, bool)

    # -- Keyframe signals --
    keyframe_moved = Signal(str, float, float, float)
    keyframe_clock_mode_requested = Signal(str, float)
    keyframe_delete_requested = Signal(str, float)
    keyframe_edit_requested = Signal(str, float, float, float)

    # -- Calibration --
    calibration_completed = Signal(float)

    # -- Drawing mode signals --
    drawing_finished = Signal(str, list)
    drawing_cancelled = Signal()

    # -- Feature editing signals --
    feature_style_changed = Signal(str, dict)
    feature_geometry_changed = Signal(str, list)

    # -- Visual styling signal (marker_id, style_overrides_dict) --
    marker_visual_style_changed = Signal(str, dict)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initializes the MapGraphicsView.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)

        # Expanding policy ensures the view fills available dock space and
        # prevents collapse when the parent dock is resized.
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

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
                    "QtOpenGLWidgets not available. " "Requesting software rendering."
                )
            except Exception as e:
                logger.warning(
                    f"Failed to initialize OpenGL viewport: {e}. "
                    "Falling back to software rendering."
                )
        else:
            logger.info(
                "OpenGL disabled via KRAKEN_NO_OPENGL. " "Using software rendering."
            )

        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        # View settings
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMouseTracking(True)

        # Disable scrollbars for infinite canvas feel
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Map background
        self.pixmap_item: Optional[QGraphicsPixmapItem] = None

        # Theme
        self.tm = ThemeManager()
        self.tm.theme_changed.connect(self._update_theme)
        self._update_theme(self.tm.get_theme())

        # Enable drop support
        self.setAcceptDrops(True)

        # Drop Hint Overlay
        self._drop_hint_overlay = QLabel(self.viewport())
        from src.gui.utils.style_helper import StyleHelper

        self._drop_hint_overlay.setStyleSheet(StyleHelper.get_drag_overlay_style())
        self._drop_hint_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drop_hint_overlay.setText("Drop to Place Marker")
        self._drop_hint_overlay.hide()

        # Temporal state
        self._current_time: float = 0.0

        # -- Sub-components --
        self._snapping_manager = SnappingManager(self.scene)
        self._snap_indicator: Optional[QGraphicsEllipseItem] = None

        self._drawing_tool = DrawingTool(self, self._snapping_manager)
        self._vertex_editor = VertexEditor(self, self._snapping_manager)
        self._marker_manager = MarkerManager(self)
        self._trajectory = TrajectoryRenderer(self)
        self._interaction = InteractionHandler(self)

        # Label layout engine (Greedy PAL-Lite)
        self.label_manager = LabelManager()
        self._layout_debounce_timer = QTimer(self)
        self._layout_debounce_timer.setSingleShot(True)
        self._layout_debounce_timer.setInterval(50)
        self._layout_debounce_timer.timeout.connect(self._execute_label_layout)

        # Hierarchical Layer Model
        self._layer_model: Optional["MapLayerModel"] = None

        # Track loaded map image
        self.current_image_path: Optional[str] = None

        # World root (set when a world is opened)
        self._world_root: Optional[str] = None

    # ------------------------------------------------------------------
    # Backward-compatible property aliases for sub-component state
    # ------------------------------------------------------------------

    @property
    def markers(self) -> Dict[str, MarkerItem]:
        """Marker items dictionary (delegated to MarkerManager)."""
        return self._marker_manager.markers

    @property
    def feature_items(self) -> Dict[str, QGraphicsObject]:
        """Feature items dictionary (delegated to MarkerManager)."""
        return self._marker_manager.feature_items

    @property
    def trajectory_path_item(self) -> Optional[QGraphicsPathItem]:
        """Trajectory path item (delegated to TrajectoryRenderer)."""
        return self._trajectory.trajectory_path_item

    @property
    def keyframe_items(self) -> list:
        """Keyframe items (delegated to TrajectoryRenderer)."""
        return self._trajectory.keyframe_items

    @property
    def keyframe_label_items(self) -> list:
        """Keyframe label items (delegated to TrajectoryRenderer)."""
        return self._trajectory.keyframe_label_items

    @property
    def trigger_first_use_animation(self) -> bool:
        """Whether to trigger pulsing animation on first trajectory."""
        return self._trajectory.trigger_first_use_animation

    @trigger_first_use_animation.setter
    def trigger_first_use_animation(self, value: bool) -> None:
        self._trajectory.trigger_first_use_animation = value

    def set_world_root(self, world_root: Optional[str]) -> None:
        """Sets the world root directory for icon import support.

        Args:
            world_root: Absolute path to the world directory, or None.
        """
        self._world_root = world_root

    @property
    def _drawing_mode(self) -> Optional[str]:
        """Backward-compatible alias for drawing mode state."""
        return self._drawing_tool._drawing_mode

    @_drawing_mode.setter
    def _drawing_mode(self, value: Optional[str]) -> None:
        self._drawing_tool._drawing_mode = value

    @property
    def _drawing_vertices(self) -> list:
        """Backward-compatible alias for drawing vertices."""
        return self._drawing_tool._drawing_vertices

    @property
    def _drawing_preview_item(self) -> Optional[QGraphicsPathItem]:
        """Backward-compatible alias for drawing preview item."""
        return self._drawing_tool._drawing_preview_item

    @property
    def _drawing_dots(self) -> list:
        """Backward-compatible alias for drawing dots."""
        return self._drawing_tool._drawing_dots

    @property
    def _editing_feature_id(self) -> Optional[str]:
        """Backward-compatible alias for editing feature ID."""
        return self._vertex_editor._editing_feature_id

    @_editing_feature_id.setter
    def _editing_feature_id(self, value: Optional[str]) -> None:
        self._vertex_editor._editing_feature_id = value

    @property
    def _vertex_handles(self) -> list:
        """Backward-compatible alias for vertex handles."""
        return self._vertex_editor._vertex_handles

    @property
    def _midpoint_handles(self) -> list:
        """Backward-compatible alias for midpoint handles."""
        return self._vertex_editor._midpoint_handles

    @property
    def _editing_original_style(self) -> Optional[Dict[str, Any]]:
        """Backward-compatible alias for editing original style."""
        return self._vertex_editor._editing_original_style

    @_editing_original_style.setter
    def _editing_original_style(self, value: Optional[Dict[str, Any]]) -> None:
        self._vertex_editor._editing_original_style = value

    @property
    def _animations(self) -> list:
        """Backward-compatible alias for trajectory animations."""
        return self._trajectory._animations

    # ------------------------------------------------------------------
    # Backward-compatible method aliases for sub-component methods
    # ------------------------------------------------------------------

    def _start_vertex_editing(self, item: "PathItem | RegionItem") -> None:
        """Backward-compatible alias for VertexEditor.start_vertex_editing."""
        self._vertex_editor.start_vertex_editing(item)

    def _finish_vertex_editing(self) -> None:
        """Backward-compatible alias for VertexEditor.finish_vertex_editing."""
        self._vertex_editor.finish_vertex_editing()

    def _add_drawing_vertex(self, scene_pos: QPointF) -> None:
        """Backward-compatible alias for DrawingTool._add_drawing_vertex."""
        self._drawing_tool._add_drawing_vertex(scene_pos)

    def _update_drawing_preview(self, mouse_pos: QPointF) -> None:
        """Backward-compatible alias for DrawingTool._update_drawing_preview."""
        self._drawing_tool._update_drawing_preview(mouse_pos)

    def _clear_drawing_preview(self) -> None:
        """Backward-compatible alias for DrawingTool._clear_drawing_preview."""
        self._drawing_tool._clear_drawing_preview()

    def _on_vertex_moved(self, index: int, new_pos: QPointF) -> None:
        """Backward-compatible alias for VertexEditor._on_vertex_moved."""
        self._vertex_editor._on_vertex_moved(index, new_pos)

    def _on_vertex_deleted(self, index: int) -> None:
        """Backward-compatible alias for VertexEditor._on_vertex_deleted."""
        self._vertex_editor._on_vertex_deleted(index)

    def _on_midpoint_insert(self, segment_index: int, scene_pos: QPointF) -> None:
        """Backward-compatible alias for VertexEditor._on_midpoint_insert."""
        self._vertex_editor._on_midpoint_insert(segment_index, scene_pos)

    def _rebuild_midpoint_handles(self) -> None:
        """Backward-compatible alias for VertexEditor._rebuild_midpoint_handles."""
        self._vertex_editor._rebuild_midpoint_handles()

    def _show_edit_keyframe_dialog(self, item: Any) -> None:
        """Backward-compatible alias for InteractionHandler."""
        self._interaction.show_edit_keyframe_dialog(item)

    def _show_feature_style_dialog(self, item: "PathItem | RegionItem") -> None:
        """Backward-compatible alias for InteractionHandler."""
        self._interaction.show_feature_style_dialog(item)

    def _update_label_scales(self) -> None:
        """Backward-compatible alias for TrajectoryRenderer."""
        self._trajectory.update_label_scales()

    def _update_trajectory_path(self) -> None:
        """Backward-compatible alias for TrajectoryRenderer."""
        self._trajectory._update_trajectory_path()

    def _show_icon_picker(self, marker_item: MarkerItem) -> None:
        """Backward-compatible alias for InteractionHandler."""
        self._interaction.show_icon_picker(marker_item)

    def _show_color_picker(self, marker_item: MarkerItem) -> None:
        """Backward-compatible alias for InteractionHandler."""
        self._interaction.show_color_picker(marker_item)

    # ------------------------------------------------------------------
    # Size hints & lifecycle
    # ------------------------------------------------------------------

    def minimumSizeHint(self) -> QSize:
        """Override minimum size hint to allow resizing below map image size.

        Returns:
            QSize: A small minimum size (200x150) to allow shrinking.
        """
        return QSize(200, 150)

    def _update_theme(self, theme: dict) -> None:
        """Updates the scene background."""
        self.scene.setBackgroundBrush(QBrush(QColor(theme["app_bg"])))

        # Scale Bar
        self.scale_bar_painter = ScaleBarPainter()
        self.map_width_meters = MAP_DEFAULT_WIDTH_METERS

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

            if self.pixmap_item:
                self.scene.removeItem(self.pixmap_item)

            self.pixmap_item = QGraphicsPixmapItem(pixmap)
            self.pixmap_item.setZValue(LAYER_MAP_BG)
            self.scene.addItem(self.pixmap_item)

            self.coord_system.set_scene_rect(self.pixmap_item.boundingRect())

            self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
            self.scene.setSceneRect(self.pixmap_item.boundingRect())

            self.current_image_path = image_path

            logger.info(f"Loaded map: {image_path}")
            self._schedule_label_layout()
            return True

        except Exception as e:
            logger.error(f"Error loading map: {e}")
            return False

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Handle resize events."""
        super().resizeEvent(event)
        if hasattr(self, "_drop_hint_overlay") and self._drop_hint_overlay:
            self._drop_hint_overlay.setGeometry(self.viewport().rect())
        self._schedule_label_layout()

    def sizeHint(self) -> QSize:
        """Return a stable preferred size.

        Returns:
            QSize: A reasonable default size.
        """
        return QSize(400, 300)

    def fit_to_view(self) -> None:
        """Fits the map to the current view size."""
        if self.pixmap_item:
            self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    # ------------------------------------------------------------------
    # Label layout (delegated to LabelManager)
    # ------------------------------------------------------------------

    def _schedule_label_layout(self) -> None:
        """Restarts the debounce timer to schedule a label layout pass."""
        if hasattr(self, "_layout_debounce_timer"):
            self._layout_debounce_timer.start()

    def _execute_label_layout(self) -> None:
        """Runs the label layout engine over all current markers.

        Keyframe dots and labels from the active trajectory are
        registered as extra obstacles so marker labels avoid them.
        """
        marker_list = list(self.markers.values())
        view_scale = self.transform().m11()
        extra = self._collect_keyframe_obstacles(view_scale)
        self.label_manager.run_layout_pass(
            marker_list, view_scale, extra_obstacles=extra
        )

    def _collect_keyframe_obstacles(self, view_scale: float) -> list[QRectF]:
        """Builds a list of scene-coordinate rects for keyframe elements.

        Args:
            view_scale: Current view transform scale factor.

        Returns:
            List of QRectF obstacles in scene coordinates.
        """
        obstacles: list[QRectF] = []
        inv_scale = 1.0 / view_scale if view_scale > 0 else 1.0

        for dot in self._trajectory.keyframe_items:
            if not dot.isVisible():
                continue
            r = dot.boundingRect()
            sp = dot.scenePos()
            obstacles.append(
                QRectF(
                    sp.x() + r.x(),
                    sp.y() + r.y(),
                    r.width(),
                    r.height(),
                )
            )

        for label in self._trajectory.keyframe_label_items:
            if not label.isVisible():
                continue
            # Labels have local transforms (translation + scale) and use
            # ItemIgnoresTransformations. Map their bounds through the local
            # transform to get the correct device-pixel offset, then scale
            # to scene coordinates.
            tr_rect = label.transform().mapRect(label.boundingRect())
            sp = label.pos()  # Use pos() to avoid double-translation from scenePos()
            obstacles.append(
                QRectF(
                    sp.x() + tr_rect.x() * inv_scale,
                    sp.y() + tr_rect.y() * inv_scale,
                    tr_rect.width() * inv_scale,
                    tr_rect.height() * inv_scale,
                )
            )

        return obstacles

    # ------------------------------------------------------------------
    # Marker management (delegated to MarkerManager)
    # ------------------------------------------------------------------

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
        visual_attributes: Optional[dict] = None,
    ) -> None:
        """Adds a marker or feature to the map at normalized coordinates.

        Args:
            marker_id: Unique identifier for the marker.
            object_type: Type of object ('entity' or 'event').
            label: Marker label text.
            x: Normalized X coordinate [0.0, 1.0].
            y: Normalized Y coordinate [0.0, 1.0].
            icon: Optional icon filename.
            color: Optional color hex string.
            description: Optional description for tooltip.
            lore_date: Optional lore timestamp.
            feature_type: 'point', 'path', or 'region'.
            geometry: Optional list of coordinate dicts.
            style: Optional visual override dict.
            visual_attributes: Optional dict with ``_v_*`` visual override keys.
        """
        self._marker_manager.add_marker(
            marker_id,
            object_type,
            label,
            x,
            y,
            icon,
            color,
            description,
            lore_date,
            feature_type,
            geometry,
            style,
            visual_attributes,
        )
        self._schedule_label_layout()

    def update_marker_position(self, marker_id: str, x: float, y: float) -> None:
        """Update a marker's position to new normalized coordinates.

        Args:
            marker_id: Unique identifier for the marker to update.
            x: New X coordinate (normalized 0-1).
            y: New Y coordinate (normalized 0-1).
        """
        self._marker_manager.update_marker_position(marker_id, x, y)
        self._schedule_label_layout()

    def remove_marker(self, marker_id: str) -> None:
        """Remove a marker or feature from the map.

        Args:
            marker_id: Unique identifier for the marker to remove.
        """
        self._marker_manager.remove_marker(marker_id)
        self._schedule_label_layout()

    def clear_markers(self) -> None:
        """Remove all markers and features from the map."""
        self._marker_manager.clear_markers()

    def update_markers_temporal_state(
        self, playhead_time: float, current_time: float
    ) -> None:
        """Updates the temporal visual state of all markers and features."""
        self._marker_manager.update_markers_temporal_state(playhead_time, current_time)

    # ------------------------------------------------------------------
    # Drawing mode (delegated to DrawingTool)
    # ------------------------------------------------------------------

    def start_drawing(self, feature_type: str) -> None:
        """Enters drawing mode for paths or regions.

        Args:
            feature_type: 'path' or 'region'.
        """
        self._drawing_tool.start_drawing(feature_type)

    def cancel_drawing(self) -> None:
        """Exits drawing mode without saving."""
        self._drawing_tool.cancel_drawing()
        self._hide_snap_indicator()

    def finish_drawing(self) -> None:
        """Completes the current drawing and emits the geometry."""
        self._drawing_tool.finish_drawing()
        self._hide_snap_indicator()

    @property
    def is_drawing(self) -> bool:
        """True when the view is in drawing mode.

        Returns:
            bool: Whether drawing mode is active.
        """
        return self._drawing_tool.is_drawing

    @property
    def drawing_mode(self) -> Optional[str]:
        """Returns the current drawing mode type.

        Returns:
            Optional[str]: 'path', 'region', or None.
        """
        return self._drawing_tool.drawing_mode

    # ------------------------------------------------------------------
    # Vertex editing (delegated to VertexEditor)
    # ------------------------------------------------------------------

    @property
    def is_editing_vertices(self) -> bool:
        """True when vertex editing mode is active.

        Returns:
            bool: Whether a feature's vertices are being edited.
        """
        return self._vertex_editor.is_editing_vertices

    def finish_editing(self) -> None:
        """Public API: completes any active vertex editing session."""
        if self._vertex_editor.is_editing_vertices:
            self._vertex_editor.finish_vertex_editing()

    # ------------------------------------------------------------------
    # Trajectory (delegated to TrajectoryRenderer)
    # ------------------------------------------------------------------

    def show_trajectory(self, marker_id: str, keyframes: list) -> None:
        """Visualizes the trajectory path and keyframes.

        Args:
            marker_id: The ID of the marker owning this trajectory.
            keyframes: List of Keyframe objects.
        """
        self._trajectory.show_trajectory(marker_id, keyframes)

    def clear_trajectory(self) -> None:
        """Clears the rendered trajectory path, keyframes, and labels."""
        self._trajectory.clear_trajectory()

    def set_calendar_converter(self, converter: object) -> None:
        """Sets the calendar converter for formatting keyframe labels."""
        self._trajectory.set_calendar_converter(converter)

    def set_keyframe_pinned(self, marker_id: str, t: float, pinned: bool) -> None:
        """Set visual pinned state for a specific keyframe."""
        self._trajectory.set_keyframe_pinned(marker_id, t, pinned)

    def update_keyframe_label(self, marker_id: str, t: float, new_time: float) -> None:
        """Updates the label of a specific keyframe."""
        self._trajectory.update_keyframe_label(marker_id, t, new_time)

    # ------------------------------------------------------------------
    # Snapping
    # ------------------------------------------------------------------

    @property
    def snapping_enabled(self) -> bool:
        """Whether snapping is currently enabled.

        Returns:
            bool: True if snapping is active.
        """
        return self._snapping_manager.enabled

    @snapping_enabled.setter
    def snapping_enabled(self, value: bool) -> None:
        """Enable or disable snapping.

        Args:
            value: True to enable snapping.
        """
        self._snapping_manager.enabled = value
        if not value:
            self._hide_snap_indicator()

    def _show_snap_indicator(self, pos: QPointF, snap_type: "SnapType") -> None:
        """Shows a visual snap indicator at the given position.

        Args:
            pos: Scene position for the indicator.
            snap_type: The type of snap (VERTEX or EDGE).
        """
        self._hide_snap_indicator()
        r = MAP_SNAP_INDICATOR_RADIUS
        self._snap_indicator = QGraphicsEllipseItem(-r, -r, r * 2, r * 2)
        color = (
            MAP_SNAP_INDICATOR_VERTEX_COLOR
            if snap_type == SnapType.VERTEX
            else MAP_SNAP_INDICATOR_EDGE_COLOR
        )
        self._snap_indicator.setBrush(QBrush(QColor(color)))
        self._snap_indicator.setPen(
            QPen(
                QColor(MAP_SNAP_INDICATOR_BORDER_COLOR),
                MAP_SNAP_INDICATOR_BORDER_WIDTH,
            )
        )
        self._snap_indicator.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True
        )
        self._snap_indicator.setZValue(LAYER_UI_OVERLAY + 2)
        self._snap_indicator.setPos(pos)
        self.scene.addItem(self._snap_indicator)

    def _hide_snap_indicator(self) -> None:
        """Removes the snap indicator from the scene."""
        if self._snap_indicator is not None:
            self.scene.removeItem(self._snap_indicator)
            self._snap_indicator = None

    # ------------------------------------------------------------------
    # Calibration
    # ------------------------------------------------------------------

    def start_calibration(self) -> None:
        """Enters calibration mode."""
        self.calibration_mode = True
        self.calibration_points.clear()
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setCursor(Qt.CrossCursor)
        self.viewport().update()

    def cancel_calibration(self) -> None:
        """Exits calibration mode."""
        self.calibration_mode = False
        self.calibration_points.clear()
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setCursor(Qt.ArrowCursor)
        self.viewport().update()

    # ------------------------------------------------------------------
    # Scale & Map Width
    # ------------------------------------------------------------------

    def set_map_width_meters(self, width_meters: float) -> None:
        """Sets the real-world width of the map for scale calculation.

        Args:
            width_meters: Width of the map image in meters.
        """
        if width_meters <= 0:
            logger.warning(f"Invalid map width: {width_meters}. Ignoring.")
            return

        self.map_width_meters = width_meters
        self.viewport().update()

    # ------------------------------------------------------------------
    # Item lookup
    # ------------------------------------------------------------------

    def find_item_by_id(self, object_id: str) -> Optional[QGraphicsItem]:
        """Public API: look up a graphics item by its object ID.

        Args:
            object_id: The object ID to search for.

        Returns:
            The matching QGraphicsItem, or None.
        """
        return self._marker_manager.find_item(object_id)

    def _find_graphics_item(self, node_id: str) -> Optional[QGraphicsItem]:
        """Look up a graphics item by layer node ID.

        Args:
            node_id: ID of the layer node.

        Returns:
            The matching QGraphicsItem, or None.
        """
        return self._marker_manager.find_item(node_id)

    # ------------------------------------------------------------------
    # Hierarchical Layer System integration
    # ------------------------------------------------------------------

    @property
    def layer_model(self) -> Optional["MapLayerModel"]:
        """Return the currently attached layer model (if any).

        Returns:
            Optional[MapLayerModel]: The layer model, or None.
        """
        return self._layer_model

    def set_layer_model(self, model: "MapLayerModel") -> None:
        """Attach a MapLayerModel and connect its signals.

        Args:
            model: The layer model to attach.
        """
        if self._layer_model is not None:
            try:
                self._layer_model.layer_visibility_changed.disconnect(
                    self._on_layer_visibility_changed
                )
                self._layer_model.layer_opacity_changed.disconnect(
                    self._on_layer_opacity_changed
                )
                self._layer_model.layer_order_changed.disconnect(
                    self._on_layer_order_changed
                )
            except RuntimeError:
                pass

        self._layer_model = model

        model.layer_visibility_changed.connect(self._on_layer_visibility_changed)
        model.layer_opacity_changed.connect(self._on_layer_opacity_changed)
        model.layer_order_changed.connect(self._on_layer_order_changed)

    def _on_layer_visibility_changed(self, node_id: str, visible: bool) -> None:
        """Respond to a layer visibility change.

        Args:
            node_id: ID of the layer node.
            visible: Whether the layer should be visible.
        """
        item = self._find_graphics_item(node_id)
        if item is not None:
            item.setVisible(visible)

    def _on_layer_opacity_changed(self, node_id: str, opacity: float) -> None:
        """Respond to a layer opacity change.

        Args:
            node_id: ID of the layer node.
            opacity: Effective opacity.
        """
        item = self._find_graphics_item(node_id)
        if item is not None:
            item.setOpacity(opacity)

    def _on_layer_order_changed(self) -> None:
        """Respond to a layer order change by recomputing Z-values."""
        if self._layer_model is None:
            return
        z_map = self._layer_model.compute_z_order()
        for node_id, z_val in z_map.items():
            item = self._find_graphics_item(node_id)
            if item is not None:
                item.setZValue(z_val)

        # Sync trajectory z-values if a trajectory is visible
        self._trajectory.update_z_values()

    def _get_current_zoom_level(self) -> float:
        """Compute the current zoom level from the view transform.

        Returns:
            float: Horizontal scale factor.
        """
        return self.transform().m11()

    def _apply_scale_dependent_visibility(self) -> None:
        """Show/hide items based on zoom and layer model."""
        if self._layer_model is None:
            return
        zoom = self._get_current_zoom_level()
        root = self._layer_model.root
        self._apply_zoom_recursive(root, zoom)

    def _apply_zoom_recursive(self, node: Any, zoom: float) -> None:
        """Walk the layer tree and toggle visibility per zoom range.

        Args:
            node: A MapLayerNode.
            zoom: Current zoom level.
        """
        if self._layer_model is None:
            return
        vis = self._layer_model.visible_at_zoom(node, zoom)
        item = self._find_graphics_item(node.id)
        if item is not None:
            item.setVisible(vis)
        for child in node.children:
            self._apply_zoom_recursive(child, zoom)

    # ------------------------------------------------------------------
    # Qt Event Overrides (thin dispatchers)
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press: drawing, calibration, or normal."""
        # Drawing mode
        if self._drawing_tool.is_drawing and self.pixmap_item:
            if event.button() == Qt.MouseButton.LeftButton:
                scene_pos = self.mapToScene(event.position().toPoint())
                if self._drawing_tool.handle_mouse_press(scene_pos):
                    self._hide_snap_indicator()
                    return

        # Calibration mode
        if self.calibration_mode and self.pixmap_item:
            pos = event.position().toPoint()
            scene_pos = self.mapToScene(pos)
            item_pos = self.pixmap_item.mapFromScene(scene_pos)

            if self.pixmap_item.contains(item_pos):
                self.calibration_points.append(scene_pos)
                self.viewport().update()

                if len(self.calibration_points) >= 2:
                    p1 = self.calibration_points[0]
                    p2 = self.calibration_points[1]

                    dx = p2.x() - p1.x()
                    dy = p2.y() - p1.y()
                    dist = math.sqrt(dx * dx + dy * dy)

                    self.calibration_mode = False
                    self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
                    self.setCursor(Qt.ArrowCursor)
                    self.calibration_completed.emit(dist)

                return

        if self.calibration_mode:
            return

        # Normal handling
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
        """Handle mouse move: drawing preview, vertex editing, coordinates."""
        super().mouseMoveEvent(event)

        scene_pos = self.mapToScene(event.position().toPoint())

        # Drawing mode
        if self._drawing_tool.handle_mouse_move(scene_pos):
            pass
        elif self._vertex_editor.handle_mouse_move(event.position().toPoint()):
            pass

        # Calibration cursor
        if self.calibration_mode:
            self.setCursor(Qt.CrossCursor)
            self.viewport().update()

        # Coordinate tracking
        if self.pixmap_item:
            pos = event.position().toPoint()
            sp = self.mapToScene(pos)

            item_pos = self.pixmap_item.mapFromScene(sp)
            if self.pixmap_item.contains(item_pos):
                norm_pos = self.coord_system.to_normalized(sp)
                self.mouse_coordinates_changed.emit(norm_pos[0], norm_pos[1], True)
            else:
                self.mouse_coordinates_changed.emit(0.0, 0.0, False)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Handle double-click to finish drawing.

        Args:
            event: The mouse double-click event.
        """
        if self._drawing_tool.handle_double_click():
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: "QKeyEvent") -> None:
        """Handle key presses for drawing/editing modes.

        Args:
            event: The key press event.
        """
        if event.key() == Qt.Key.Key_Escape:
            if self._drawing_tool.handle_key_escape():
                return
            if self._vertex_editor.handle_key_escape():
                return
        super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel for zooming."""
        zoom_out_factor = 1 / MAP_ZOOM_IN_FACTOR

        factor = MAP_ZOOM_IN_FACTOR if event.angleDelta().y() > 0 else zoom_out_factor

        self.scale(factor, factor)
        self._trajectory.update_label_scales()
        self._apply_scale_dependent_visibility()
        self._schedule_label_layout()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Handle context menu events.

        Args:
            event: The context menu event.
        """
        if not self.pixmap_item:
            return

        if self._drawing_tool.is_drawing:
            return

        pos = event.pos()
        item = self.itemAt(pos)
        if isinstance(item, MarkerItem):
            self._interaction.show_marker_context_menu(item, event.globalPos())
        elif isinstance(item, (PathItem, RegionItem)):
            self._interaction.show_feature_context_menu(item, event.globalPos())
        else:
            scene_pos = self.mapToScene(pos)
            item_pos = self.pixmap_item.mapFromScene(scene_pos)
            if self.pixmap_item.contains(item_pos):
                self._interaction.show_map_background_context_menu(
                    scene_pos, event.globalPos()
                )

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept drag events with our custom MIME type."""
        self._interaction.handle_drag_enter(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Allow drop only over the map pixmap."""
        self._interaction.handle_drag_move(event)

    def dragLeaveEvent(self, event: "QDragLeaveEvent") -> None:
        """Handle drag leave event.

        Args:
            event: The drag leave event.
        """
        super().dragLeaveEvent(event)
        self._interaction.handle_drag_leave()

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle drop of item from Project Explorer."""
        self._interaction.handle_drop(event)

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        """Draw overlay elements on top of the scene."""
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
                view_pos = self.mapFromGlobal(self.cursor().pos())
                end_pos = self.mapToScene(view_pos)

            if start_pos and end_pos:
                painter.drawLine(start_pos, end_pos)

                mid = (start_pos + end_pos) / 2

                dx = end_pos.x() - start_pos.x()
                dy = end_pos.y() - start_pos.y()
                dist_px = math.sqrt(dx * dx + dy * dy)

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
            image_width_px = self.pixmap_item.boundingRect().width()
            if image_width_px > 0:
                base_resolution = self.map_width_meters / image_width_px

                view_scale = self.transform().m11()

                if view_scale > 0:
                    current_resolution = base_resolution / view_scale

                    painter.save()
                    painter.resetTransform()

                    self.scale_bar_painter.paint(
                        painter,
                        QRectF(self.viewport().rect()),
                        current_resolution,
                    )

                    painter.restore()
