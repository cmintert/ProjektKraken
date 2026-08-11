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
from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from PySide6.QtCore import (
    Property,
    QPointF,
    QRect,
    QRectF,
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
    QGraphicsObject,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QSizePolicy,
    QStyleOptionGraphicsItem,
    QWidget,
)

from src.app.constants import (
    MAP_LAYER_BASEMAP_NODE_ID,
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
from src.core.calendar import CalendarConverter
from src.core.theme_manager import ThemeManager
from src.gui.widgets.map.coordinate_system import MapCoordinateSystem
from src.gui.widgets.map.detail_map_footprint_item import DetailMapFootprintItem
from src.gui.widgets.map.drawing_tool import DrawingTool
from src.gui.widgets.map.feature_items import PathItem, RegionItem
from src.gui.widgets.map.interaction_handler import InteractionHandler
from src.gui.widgets.map.label_manager import LabelLayoutItem, LabelManager
from src.gui.widgets.map.marker_item import MarkerItem
from src.gui.widgets.map.marker_manager import MarkerManager
from src.gui.widgets.map.raster_edit_tool import RasterEditMode
from src.gui.widgets.map.scale_bar_overlay import ScaleBarOverlay
from src.gui.widgets.map.scale_bar_painter import ScaleBarPainter
from src.gui.widgets.map.snapping_manager import SnappingManager, SnapType
from src.gui.widgets.map.trajectory_edit_overlay import TrajectoryEditOverlay
from src.gui.widgets.map.trajectory_renderer import TrajectoryRenderer
from src.gui.widgets.map.vertex_editor import VertexEditor

if TYPE_CHECKING:
    from src.gui.widgets.map.map_layer_model import MapLayerModel
    from src.gui.widgets.map_widget import MapWidget

logger = logging.getLogger(__name__)

# Layer Z-Values (backward-compatible aliases for constants)
LAYER_MAP_BG = MAP_LAYER_Z_MAP_BG
LAYER_TRAJECTORIES = MAP_LAYER_Z_TRAJECTORIES
LAYER_MARKERS = MAP_LAYER_Z_MARKERS
LAYER_UI_OVERLAY = MAP_LAYER_Z_UI_OVERLAY

# Colors — resolved from ThemeManager at runtime; these are fallback defaults only
KEYFRAME_COLOR_DEFAULT = "#f1c40f"  # Yellow (fallback)


class KeyframeItem(QGraphicsObject):
    """Passive playback dot for a trajectory keyframe."""

    def __init__(
        self,
        marker_id: str,
        t: float,
        x: float,
        y: float,
        rect: QRectF,
    ) -> None:
        super().__init__()
        self._rect = rect
        self.marker_id = marker_id
        self.t = t
        self.original_x = x
        self.original_y = y

        theme = ThemeManager().get_theme()
        color = theme.get("accent_secondary", KEYFRAME_COLOR_DEFAULT)
        self._brush = QBrush(QColor(color))
        self._pen = QPen(Qt.PenStyle.NoPen)

    def boundingRect(self) -> QRectF:
        """Return the keyframe dot bounds."""
        return self._rect

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        """Paint the keyframe dot."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(self._brush)
        painter.setPen(self._pen)
        painter.drawEllipse(self._rect)

    def setBrush(self, brush: QBrush) -> None:
        """Set the dot fill."""
        self._brush = brush
        self.update()

    def brush(self) -> QBrush:
        """Return the dot fill."""
        return self._brush

    def setPen(self, pen: QPen) -> None:
        """Set the dot outline."""
        self._pen = pen
        self.update()

    def pen(self) -> QPen:
        """Return the dot outline."""
        return self._pen

    @Property(float)
    def scale_val(self) -> float:
        """Return the animation scale."""
        return self.scale()

    @scale_val.setter  # type: ignore[no-redef]  # PySide6 Property stub mismatch
    def scale_val(self, value: float) -> None:
        """Set the animation scale."""
        self.setScale(value)
        self.update()


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
    marker_placement_ended = Signal()
    delete_marker_requested = Signal(str)  # marker_id
    change_marker_icon_requested = Signal(str, str)  # marker_id, new_icon
    change_marker_color_requested = Signal(str, str)  # marker_id, new_color_hex
    marker_drop_requested = Signal(str, str, str, float, float)

    # -- Coordinate signal --
    mouse_coordinates_changed = Signal(float, float, bool)

    # -- Direct trajectory editing signals --
    trajectory_edit_requested = Signal(str)
    trajectory_keyframe_selected = Signal(str)
    trajectory_keyframe_moved = Signal(str, float, float)
    trajectory_midpoint_insert_requested = Signal(str, str, float, float)
    trajectory_delete_selected_requested = Signal()

    # -- Calibration --
    calibration_completed = Signal(float)

    # -- Footprint overlay signals --
    detail_map_clicked = Signal(str)
    """Emitted when the user clicks a detail-map footprint in normal mode."""
    footprint_edit_confirmed = Signal(str, str, dict)
    """Emitted when the user confirms a footprint edit (detail_id, parent_id, reg)."""
    footprint_edit_cancelled = Signal()
    """Emitted when the user cancels a footprint edit."""

    # -- Drawing mode signals --
    drawing_finished = Signal(str, list)
    drawing_cancelled = Signal()

    # -- Feature editing signals --
    feature_style_changed = Signal(str, dict)
    feature_geometry_changed = Signal(str, list)
    feature_geometry_edit_requested = Signal(str)
    feature_geometry_manage_requested = Signal(str)
    feature_geometry_cancel_requested = Signal()
    temporal_validity_requested = Signal(str)
    temporal_jump_requested = Signal(str)
    temporal_show_in_layers_requested = Signal(str)
    effective_visibility_changed = Signal()

    # -- Visual styling signal (marker_id, style_overrides_dict) --
    marker_visual_style_changed = Signal(str, dict)

    # -- Raster editing signals --
    raster_stroke_completed = Signal(str, object)  # node_id, tile patches
    raster_value_probed = Signal(str, object, float, float)  # node_id, sample, x, y
    raster_edit_externally_stopped = Signal()  # edit stopped by Escape or other non-panel trigger
    raster_brush_resize_requested = Signal(int)  # new brush size from Ctrl+scroll
    raster_tool_shortcut_requested = Signal(str)

    # Emitted when the viewport resizes, useful for positioning overlays
    viewport_resized = Signal(QResizeEvent)

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

        self._graphics_scene = QGraphicsScene(self)
        self.setScene(self._graphics_scene)

        # View settings
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMouseTracking(True)
        # Scale bar is now a viewport overlay widget, so MinimalViewportUpdate
        # is safe — no more device-space painting in drawForeground().
        self.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate
        )

        # Disable scrollbars for infinite canvas feel
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Map background
        self.pixmap_item: Optional[QGraphicsPixmapItem] = None
        self._fit_zoom_level = 1.0

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

        # Scale bar overlay (viewport-space widget, avoids FullViewportUpdate)
        self._scale_bar_overlay = ScaleBarOverlay(self.viewport())
        self._scale_bar_overlay.show()

        # Temporal state
        self._current_time: float = 0.0
        self._playhead_time: float = 0.0
        self._show_temporal_ghosts = False
        self._temporal_authoring_overrides: set[str] = set()

        # -- Sub-components --
        self._snapping_manager = SnappingManager(self.graphics_scene)
        self._snap_indicator: Optional[QGraphicsEllipseItem] = None

        self._drawing_tool = DrawingTool(self, self._snapping_manager)
        self._vertex_editor = VertexEditor(self, self._snapping_manager)
        self._marker_manager = MarkerManager(self)
        self._trajectory = TrajectoryRenderer(self)
        self._trajectory_edit_overlay = TrajectoryEditOverlay(self)
        self._interaction = InteractionHandler(self)
        self._trajectory_marker_ids: set[str] = set()

        from src.gui.widgets.map.raster_edit_tool import RasterEditTool

        self._raster_edit_tool = RasterEditTool(self)

        # Label layout engine (Greedy PAL-Lite)
        self.label_manager = LabelManager()
        self._layout_debounce_timer = QTimer(self)
        self._layout_debounce_timer.setSingleShot(True)
        self._layout_debounce_timer.setInterval(50)
        self._layout_debounce_timer.timeout.connect(self._execute_label_layout)

        self._footprint_label_debounce_timer = QTimer(self)
        self._footprint_label_debounce_timer.setSingleShot(True)
        self._footprint_label_debounce_timer.setInterval(50)
        self._footprint_label_debounce_timer.timeout.connect(
            self._layout_footprint_labels
        )

        # Hierarchical Layer Model
        self._layer_model: Optional["MapLayerModel"] = None

        # Raster overlay items (node_id → RasterLayerItem)
        self._raster_items: dict[str, Any] = {}

        # Footprint overlay items (detail_map_id → DetailMapFootprintItem)
        self._footprint_items: dict[str, DetailMapFootprintItem] = {}
        self._footprints_visible: bool = True
        self._editing_footprint_id: Optional[str] = None

        # Spatial query overlay item (Feature D)
        self._query_overlay_item: Optional[QGraphicsPixmapItem] = None

        # Track loaded map image
        self.current_image_path: Optional[str] = None

        # World root (set when a world is opened)
        self._world_root: Optional[str] = None

        # Space held-to-pan state (industry-standard painting-app shortcut)
        self._space_pressed: bool = False

        # One-shot marker placement mode, activated by the map toolbar.
        self._is_placing_marker: bool = False

    # ------------------------------------------------------------------
    # Backward-compatible property aliases for sub-component state
    # ------------------------------------------------------------------

    @property
    def graphics_scene(self) -> QGraphicsScene:
        """Return the scene without shadowing ``QGraphicsView.scene``."""
        return self._graphics_scene

    @property
    def markers(self) -> Dict[str, MarkerItem]:
        """Marker items dictionary (delegated to MarkerManager)."""
        return self._marker_manager.markers

    @property
    def feature_items(self) -> Dict[str, PathItem | RegionItem]:
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
    def trajectory_edit_overlay(self) -> TrajectoryEditOverlay:
        """Return the direct trajectory editing overlay."""
        return self._trajectory_edit_overlay

    def set_trajectory_marker_ids(self, marker_ids: set[str]) -> None:
        """Record which visible markers currently own trajectories."""
        self._trajectory_marker_ids = set(marker_ids)

    @property
    def trigger_first_use_animation(self) -> bool:
        """Whether to trigger pulsing animation on first trajectory."""
        return self._trajectory.trigger_first_use_animation

    @trigger_first_use_animation.setter
    def trigger_first_use_animation(self, value: bool) -> None:
        """Set whether to trigger pulsing animation on first trajectory."""
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
        self._interaction.show_fill_color_picker(marker_item)

    # ------------------------------------------------------------------
    # Raster editing public API
    # ------------------------------------------------------------------

    def start_raster_editing(self, node_id: str) -> None:
        """Enter raster editing mode for a layer.

        Args:
            node_id: Raster layer node ID to edit.
        """
        logger.debug(
            "start_raster_editing: node_id=%s raster_items=%s",
            node_id,
            list(self._raster_items.keys()),
        )
        self._raster_edit_tool.start_editing(node_id)

    def stop_raster_editing(self) -> None:
        """Exit raster editing mode."""
        logger.debug("stop_raster_editing called")
        self._raster_edit_tool.stop_editing()

    # ------------------------------------------------------------------
    # Spatial query overlay (Feature D)
    # ------------------------------------------------------------------

    def set_query_overlay(self, mask: Any, scene_rect: "QRectF") -> None:
        """Display a red semi-transparent overlay for pixels matching a query mask.

        Args:
            mask: 2-D boolean numpy array (True = matches query).
            scene_rect: Scene-coordinate rectangle that the mask covers.
        """
        import numpy as np

        self.clear_query_overlay()

        h, w = mask.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[mask, 0] = 220  # red channel
        rgba[mask, 3] = 128  # 50 % alpha for matching cells

        from PySide6.QtGui import QImage

        img = QImage(rgba.tobytes(), w, h, w * 4, QImage.Format.Format_RGBA8888)
        pm = QPixmap.fromImage(img)
        if not scene_rect.isEmpty():
            pm = pm.scaled(
                int(scene_rect.width()),
                int(scene_rect.height()),
            )

        from src.app.constants import MAP_LAYER_Z_RASTER

        self._query_overlay_item = QGraphicsPixmapItem(pm)
        self._query_overlay_item.setPos(scene_rect.topLeft())
        self._query_overlay_item.setZValue(MAP_LAYER_Z_RASTER + 1)
        self.graphics_scene.addItem(self._query_overlay_item)

    def clear_query_overlay(self) -> None:
        """Remove the spatial query overlay from the scene."""
        if self._query_overlay_item is not None:
            self.graphics_scene.removeItem(self._query_overlay_item)
            self._query_overlay_item = None

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
        self.graphics_scene.setBackgroundBrush(QBrush(QColor(theme["app_bg"])))
        if hasattr(self, "_marker_manager"):
            label_items = [
                *self._marker_manager.markers.values(),
                *self._marker_manager.feature_items.values(),
            ]
            for item in label_items:
                item._label_item.refresh_theme()
            self._schedule_label_layout()

        # Scale Bar
        self.scale_bar_painter = ScaleBarPainter()
        if not hasattr(self, "map_width_meters"):
            self.map_width_meters = 0.0

        # Calibration State
        if not hasattr(self, "calibration_mode"):
            self.calibration_mode = False
            self.calibration_points = []

    def cleanup(self) -> None:
        """Stop all owned timers and release sub-component resources.

        Safe to call multiple times.  Must be called before the widget is
        closed so that pending Qt callbacks cannot fire on a partially-torn-
        down object.
        """
        self._layout_debounce_timer.stop()
        if hasattr(self, "_trajectory"):
            self._trajectory.cleanup()
        if hasattr(self, "_trajectory_edit_overlay"):
            self._trajectory_edit_overlay.clear()

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
                self.graphics_scene.removeItem(self.pixmap_item)

            self.pixmap_item = QGraphicsPixmapItem(pixmap)
            self.pixmap_item.setZValue(LAYER_MAP_BG)
            self.graphics_scene.addItem(self.pixmap_item)

            self.coord_system.set_scene_rect(self.pixmap_item.boundingRect())

            self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
            self._fit_zoom_level = max(self.transform().m11(), 1e-9)
            self.graphics_scene.setSceneRect(self.pixmap_item.boundingRect())

            self.current_image_path = image_path

            logger.info(f"Loaded map: {image_path}")
            self._schedule_label_layout()
            self._layout_footprint_labels()
            self._update_scale_bar_overlay()
            return True

        except Exception as e:
            logger.error(f"Error loading map: {e}")
            return False

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Handle resize events."""
        super().resizeEvent(event)
        self.viewport_resized.emit(event)
        import shiboken6

        if (
            hasattr(self, "_drop_hint_overlay")
            and self._drop_hint_overlay
            and shiboken6.isValid(self._drop_hint_overlay)
        ):
            self._drop_hint_overlay.setGeometry(self.viewport().rect())
        if hasattr(self, "_scale_bar_overlay") and shiboken6.isValid(
            self._scale_bar_overlay
        ):
            self._scale_bar_overlay.reposition(self.viewport().size())
        self._schedule_label_layout()
        self._layout_footprint_labels()

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
            self._fit_zoom_level = max(self.transform().m11(), 1e-9)
            self._layout_footprint_labels()

    def ensure_software_rendering(self) -> None:
        """Switch the viewport to software rendering if not already set.

        ``QPainter.setCompositionMode`` is silently ignored by Qt's OpenGL
        paint engine for most modes beyond ``SourceOver`` (Multiply, Screen,
        Difference, etc.).  Raster layers that use non-default blend modes
        must therefore be rendered with the software rasteriser so that
        composition modes are applied correctly.

        This method replaces the ``QOpenGLWidget`` viewport with a plain
        ``QWidget``, transparently preserving all render hints.  Calling it
        when already in software mode is a no-op.  Overlay reparenting is
        handled automatically by :meth:`setupViewport`.
        """
        from PySide6.QtOpenGLWidgets import QOpenGLWidget

        if isinstance(self.viewport(), QOpenGLWidget):
            logger.info(
                "ensure_software_rendering: switching to software "
                "rendering for correct blend-mode compositing."
            )
            # Qt accepts None here to restore its default software viewport;
            # the PySide6 stub incorrectly requires QWidget.
            self.setViewport(None)  # type: ignore[arg-type]
            # Re-apply render hints; setViewport() resets the viewport widget
            self.setRenderHint(QPainter.RenderHint.Antialiasing)
            self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    def setupViewport(self, viewport: QWidget) -> None:
        """Reparent floating overlays whenever the viewport is replaced.

        Qt calls this method each time a new viewport widget is installed
        (including the initial creation and any call to ``setViewport()``).
        Overriding it is the correct hook for keeping overlay widgets parented
        to the *active* viewport so they always render on top of the scene.

        Args:
            viewport: The new viewport widget being installed.
        """
        super().setupViewport(viewport)
        import shiboken6

        if hasattr(self, "_scale_bar_overlay") and shiboken6.isValid(
            self._scale_bar_overlay
        ):
            self._scale_bar_overlay.setParent(viewport)
            self._scale_bar_overlay.show()
            self._scale_bar_overlay.reposition(viewport.size())
        if hasattr(self, "_drop_hint_overlay") and shiboken6.isValid(
            self._drop_hint_overlay
        ):
            was_visible = self._drop_hint_overlay.isVisible()
            self._drop_hint_overlay.setParent(viewport)
            self._drop_hint_overlay.setGeometry(viewport.rect())
            if was_visible:
                self._drop_hint_overlay.show()

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
        marker_list = [
            cast(LabelLayoutItem, item) for item in self.markers.values()
        ]
        marker_list.extend(
            cast(LabelLayoutItem, item) for item in self.feature_items.values()
        )
        view_scale = self.transform().m11()
        extra = self._collect_keyframe_obstacles(view_scale)
        self.label_manager.run_layout_pass(
            marker_list, view_scale, extra_obstacles=extra
        )

    def _collect_keyframe_obstacles(self, view_scale: float) -> list[QRectF]:
        """Builds a list of scene-coordinate rects for keyframe labels.

        Keyframe labels are registered as immovable obstacles so that
        marker labels avoid them.  Keyframe dots are intentionally
        excluded so they do not block marker label placement.

        Args:
            view_scale: Current view transform scale factor.

        Returns:
            List of QRectF obstacles in scene coordinates.
        """
        obstacles: list[QRectF] = []
        inv_scale = 1.0 / view_scale if view_scale > 0 else 1.0

        for label in self._trajectory.keyframe_label_items:
            if not label.isVisible():
                continue
            # Labels have local transforms (translation + scale) and use
            # ItemIgnoresTransformations. Map their bounds through the
            # local transform to get the correct device-pixel offset,
            # then scale to scene coordinates.
            tr_rect = label.transform().mapRect(label.boundingRect())
            sp = label.pos()
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
        self._apply_effective_layer_opacity()
        self._apply_effective_layer_visibility()
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

    def update_feature_geometry(
        self,
        marker_id: str,
        geometry: list[dict[str, float]],
        anchor_x: float,
        anchor_y: float,
    ) -> None:
        """Replace a rendered path or region without recreating it."""
        self._marker_manager.update_feature_geometry(
            marker_id, geometry, anchor_x, anchor_y
        )
        self._schedule_label_layout()

    def remove_marker(self, marker_id: str) -> None:
        """Remove a marker or feature from the map.

        Args:
            marker_id: Unique identifier for the marker to remove.
        """
        if self._vertex_editor.editing_feature_id == marker_id:
            self._vertex_editor.finish_vertex_editing(emit_geometry_change=False)
        self._marker_manager.remove_marker(marker_id)
        self._schedule_label_layout()

    def clear_markers(self) -> None:
        """Remove all markers and features from the map."""
        self.exit_all_editing(commit_feature_edits=False)
        self._marker_manager.clear_markers()

    def update_markers_temporal_state(
        self, playhead_time: float, current_time: float
    ) -> None:
        """Updates the temporal visual state of all markers and features.

        Args:
            playhead_time: Current playhead position in lore time.
            current_time: Current absolute time for animation.
        """
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

    def start_marker_placement(self) -> None:
        """Enter one-shot marker placement mode."""
        self._is_placing_marker = True
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def cancel_marker_placement(self) -> None:
        """Exit marker placement mode without creating a marker."""
        if not self._is_placing_marker:
            return
        self._is_placing_marker = False
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.marker_placement_ended.emit()

    @property
    def is_placing_marker(self) -> bool:
        """Whether the next map click will place a marker."""
        return self._is_placing_marker

    def _handle_marker_placement_mouse_press(self, event: QMouseEvent) -> bool:
        """Place a marker when the active one-shot mode receives a map click."""
        if not self._is_placing_marker or not self.pixmap_item:
            return False
        if event.button() != Qt.MouseButton.LeftButton:
            return True

        scene_pos = self.mapToScene(event.position().toPoint())
        item_pos = self.pixmap_item.mapFromScene(scene_pos)
        if self.pixmap_item.contains(item_pos):
            norm_x, norm_y = self.coord_system.to_normalized(scene_pos)
            norm_x, norm_y = self.coord_system.clamp_normalized(norm_x, norm_y)
            self.cancel_marker_placement()
            self.add_marker_requested.emit(norm_x, norm_y)
        return True

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

    def exit_all_editing(self, commit_feature_edits: bool = False) -> None:
        """Exit drawing, vertex, and raster editing modes.

        Args:
            commit_feature_edits: Whether active vertex edits should emit a
                geometry change before teardown.
        """
        if self.is_drawing:
            self.cancel_drawing()
        if self._is_placing_marker:
            self.cancel_marker_placement()
        if self._vertex_editor.is_editing_vertices:
            self._vertex_editor.finish_vertex_editing(
                emit_geometry_change=commit_feature_edits
            )
        if self._raster_edit_tool.is_active:
            self.stop_raster_editing()

    # ------------------------------------------------------------------
    # Trajectory (delegated to TrajectoryRenderer)
    # ------------------------------------------------------------------

    def show_trajectory(
        self, marker_id: str, keyframes: list, segment_modes: dict | None = None
    ) -> None:
        """Visualizes the trajectory path and keyframes.

        Args:
            marker_id: The ID of the marker owning this trajectory.
            keyframes: List of Keyframe objects.
        """
        self._trajectory.show_trajectory(marker_id, keyframes, segment_modes)

    def clear_trajectory(self) -> None:
        """Clears the rendered trajectory path, keyframes, and labels."""
        self._trajectory.clear_trajectory()

    def set_calendar_converter(self, converter: CalendarConverter) -> None:
        """Sets the calendar converter for formatting keyframe labels."""
        self._trajectory.set_calendar_converter(converter)

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
        self.graphics_scene.addItem(self._snap_indicator)

    def _hide_snap_indicator(self) -> None:
        """Removes the snap indicator from the scene."""
        if self._snap_indicator is not None:
            self.graphics_scene.removeItem(self._snap_indicator)
            self._snap_indicator = None

    # ------------------------------------------------------------------
    # Calibration
    # ------------------------------------------------------------------

    def start_calibration(self) -> None:
        """Enters calibration mode."""
        self.calibration_mode = True
        self.calibration_points.clear()
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.viewport().update()

    def cancel_calibration(self) -> None:
        """Exits calibration mode."""
        self.calibration_mode = False
        self.calibration_points.clear()
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setCursor(Qt.CursorShape.ArrowCursor)
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
        self._update_scale_bar_overlay()

    def clear_map_scale(self) -> None:
        """Mark the map as uncalibrated and hide metric scale output."""
        self.map_width_meters = 0.0
        if hasattr(self, "_scale_bar_overlay"):
            self._scale_bar_overlay.update_scale(0.0)

    def _update_scale_bar_overlay(self) -> None:
        """Recompute and push the current resolution to the scale bar overlay."""
        import shiboken6

        if not hasattr(self, "_scale_bar_overlay") or not shiboken6.isValid(
            self._scale_bar_overlay
        ):
            return
        if not self.pixmap_item or self.map_width_meters <= 0:
            self._scale_bar_overlay.update_scale(0.0)
            return
        image_width_px = self.pixmap_item.boundingRect().width()
        if image_width_px <= 0:
            return
        view_scale = self.transform().m11()
        if view_scale <= 0:
            return
        base_resolution = self.map_width_meters / image_width_px
        current_resolution = base_resolution / view_scale
        self._scale_bar_overlay.update_scale(current_resolution)

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

        Checks the base-map pixmap, raster items, and the marker manager
        (which handles markers, paths, and regions).

        Args:
            node_id: ID of the layer node.

        Returns:
            The matching QGraphicsItem, or None.
        """
        if node_id == MAP_LAYER_BASEMAP_NODE_ID:
            return self.pixmap_item
        # Check raster items first (fast dict lookup)
        raster_item = self._raster_items.get(node_id)
        if raster_item is not None:
            return raster_item
        footprint_item = self._footprint_items.get(node_id)
        if footprint_item is not None:
            return footprint_item
        return self._marker_manager.find_item(node_id)

    # ------------------------------------------------------------------
    # Footprint overlay management
    # ------------------------------------------------------------------

    @property
    def is_editing_footprint(self) -> bool:
        """Return ``True`` when a footprint is being interactively edited."""
        return self._editing_footprint_id is not None

    @property
    def footprints_visible(self) -> bool:
        """Return whether footprint overlays are currently visible."""
        return self._footprints_visible

    def set_footprints_visible(self, visible: bool) -> None:
        """Show or hide all footprint overlays.

        Hidden footprints are made non-interactive by disabling their
        scene items.

        Args:
            visible: ``True`` to show footprints, ``False`` to hide.

        """
        visible = bool(visible)
        self._footprints_visible = visible

        if not visible and self.is_editing_footprint:
            self.cancel_footprint_edit()

        for item in self._footprint_items.values():
            item.setVisible(visible)
            item.setEnabled(visible)

        if visible:
            self._layout_footprint_labels()

    def set_footprints(self, footprint_data: list) -> None:
        """Replace all footprint overlays.

        Clears any existing footprint items and creates new ones from
        ``footprint_data``.  Does nothing if no map image is loaded.

        Args:
            footprint_data: List of dicts, each with keys:
                ``id`` (str), ``name`` (str), ``parent_map_id`` (str),
                ``registration`` (dict).

        """
        self.clear_footprints()
        if not self.pixmap_item:
            return
        iw = self.pixmap_item.boundingRect().width()
        ih = self.pixmap_item.boundingRect().height()
        if iw <= 0 or ih <= 0:
            return
        for data in footprint_data:
            item = DetailMapFootprintItem(
                detail_map_id=data["id"],
                name=data["name"],
                parent_map_id=data["parent_map_id"],
                registration=data["registration"],
                image_w=iw,
                image_h=ih,
                image_path=data.get("image_path", ""),
            )
            item.detail_map_clicked.connect(self.detail_map_clicked)
            item.registration_changed.connect(self._on_footprint_registration_changed)
            item.setVisible(self._footprints_visible)
            item.setEnabled(self._footprints_visible)
            self.graphics_scene.addItem(item)
            self._footprint_items[data["id"]] = item

        self._layout_footprint_labels()

    def clear_footprints(self) -> None:
        """Remove all footprint overlay items from the scene."""
        for item in list(self._footprint_items.values()):
            self.graphics_scene.removeItem(item)
        self._footprint_items.clear()
        self._editing_footprint_id = None

    def _on_footprint_registration_changed(self, _registration: dict) -> None:
        """Relayout labels while a footprint registration is being edited."""
        if hasattr(self, "_footprint_label_debounce_timer"):
            self._footprint_label_debounce_timer.start()

    def _layout_footprint_labels(self) -> None:
        """Layout footprint labels below footprints without overlaps.

        Labels are stacked downward when collisions occur, and hidden if
        no collision-free slot remains within the map bounds.
        """
        if not self.pixmap_item:
            return

        visible_items = [
            item
            for item in self._footprint_items.values()
            if item.isVisible() and item.isEnabled()
        ]
        if not visible_items:
            return

        zoom_scale = max(0.05, float(self.transform().m11()) or 1.0)
        map_rect = QRectF(self.pixmap_item.boundingRect())
        item_bounds = {item: item.footprint_bounds_rect() for item in visible_items}
        footprint_rects = list(item_bounds.values())

        occupied_label_rects: list[QRectF] = []
        ordered_items = sorted(
            visible_items,
            key=lambda it: (item_bounds[it].bottom(), item_bounds[it].left()),
        )

        for item in ordered_items:
            candidate = item.preferred_label_rect(zoom_scale)
            if candidate.isNull():
                item.set_label_layout(None, zoom_scale)
                continue

            max_left = map_rect.right() - candidate.width() - 2.0
            clamped_left = max(map_rect.left() + 2.0, min(candidate.left(), max_left))
            candidate.moveLeft(clamped_left)

            step = max(6.0, candidate.height() + 2.0)
            placed_rect: Optional[QRectF] = None
            for _ in range(80):
                overlaps_label = any(
                    candidate.intersects(r.adjusted(-2.0, -1.0, 2.0, 1.0))
                    for r in occupied_label_rects
                )
                overlaps_footprint = any(
                    candidate.intersects(r.adjusted(-1.0, -1.0, 1.0, 2.0))
                    for r in footprint_rects
                )
                if not overlaps_label and not overlaps_footprint:
                    placed_rect = QRectF(candidate)
                    break

                candidate.translate(0.0, step)
                if candidate.bottom() > map_rect.bottom() - 2.0:
                    break

            if placed_rect is None:
                item.set_label_layout(None, zoom_scale)
                continue

            item.set_label_layout(placed_rect, zoom_scale)
            occupied_label_rects.append(placed_rect)

    def start_footprint_edit(self, detail_map_id: str) -> None:
        """Enter interactive edit mode for a footprint.

        Args:
            detail_map_id: ID of the detail map whose footprint to edit.

        """
        if not self._footprints_visible:
            return
        item = self._footprint_items.get(detail_map_id)
        if item is None:
            return
        self._editing_footprint_id = detail_map_id
        item.set_edit_mode(True)

    def finish_footprint_edit(self) -> None:
        """Confirm the current footprint edit and emit the result signal."""
        fid = self._editing_footprint_id
        if fid is None:
            return
        item = self._footprint_items.get(fid)
        self._editing_footprint_id = None
        if item is None:
            return
        item.set_edit_mode(False)
        self.footprint_edit_confirmed.emit(
            fid, item.parent_map_id, item.current_registration()
        )

    def cancel_footprint_edit(self) -> None:
        """Cancel the current footprint edit and revert to the saved registration."""
        fid = self._editing_footprint_id
        if fid is None:
            return
        item = self._footprint_items.get(fid)
        self._editing_footprint_id = None
        if item is None:
            return
        item.cancel_edit()
        self.footprint_edit_cancelled.emit()

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
        model.set_current_time(self._playhead_time)
        self._apply_effective_layer_opacity()
        self._apply_effective_layer_visibility()

    def _on_layer_visibility_changed(self, node_id: str, visible: bool) -> None:
        """Respond to a layer visibility change.

        Args:
            node_id: ID of the layer node.
            visible: Whether the layer should be visible.
        """
        del node_id, visible
        self._apply_effective_layer_visibility()

    def _on_layer_opacity_changed(self, node_id: str, opacity: float) -> None:
        """Respond to a layer opacity change.

        Args:
            node_id: ID of the layer node.
            opacity: Effective opacity.
        """
        import shiboken6

        item = self._find_graphics_item(node_id)
        if item is not None and shiboken6.isValid(item):
            try:
                set_layer_opacity = getattr(item, "set_layer_opacity", None)
                if callable(set_layer_opacity):
                    set_layer_opacity(opacity)
                else:
                    item.setOpacity(opacity)
            except RuntimeError:
                logger.debug(
                    "_on_layer_opacity_changed: item %s already deleted", node_id
                )

    def _on_layer_order_changed(self) -> None:
        """Respond to a layer order change by recomputing Z-values."""
        if self._layer_model is None:
            return
        z_map = self._layer_model.compute_z_order()
        for node_id, z_val in z_map.items():
            # The basemap is pinned at MAP_LAYER_Z_MAP_BG and must stay
            # below every other layer, regardless of its position in the
            # layer tree.  Don't let compute_z_order override that.
            if node_id == MAP_LAYER_BASEMAP_NODE_ID:
                continue
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
        self._apply_effective_layer_visibility()

    def set_playhead_time(self, time: float) -> None:
        """Recompute historical feature visibility for a new playhead."""
        self._playhead_time = float(time)
        if self._layer_model is not None:
            self._layer_model.set_current_time(self._playhead_time)
        self._apply_effective_layer_visibility()

    def set_temporal_ghosts_visible(self, visible: bool) -> None:
        """Toggle session-only temporal authoring ghosts."""
        self._show_temporal_ghosts = bool(visible)
        self._apply_effective_layer_visibility()

    def set_temporal_authoring_override(
        self, marker_id: str, enabled: bool
    ) -> None:
        """Keep an actively edited feature visible despite temporal validity."""
        if enabled:
            self._temporal_authoring_overrides.add(marker_id)
        else:
            self._temporal_authoring_overrides.discard(marker_id)
        self._apply_effective_layer_visibility()

    def is_temporally_valid(self, marker_id: str) -> bool:
        """Return whether a vector feature exists at the current playhead."""
        if self._layer_model is None:
            return True
        node = self._layer_model.find_node_by_id(marker_id)
        if node is None:
            return True
        return self._layer_model.temporal_validity(node).valid

    def _apply_effective_layer_visibility(self) -> None:
        """Apply manual, ancestor, zoom, and temporal visibility together."""
        if self._layer_model is None:
            return
        zoom = self._get_current_zoom_level()
        base_visibility = dict(
            self._layer_model.compute_visibility(
                zoom,
                current_time=None,
                fit_zoom_level=self._fit_zoom_level,
            )
        )
        effective_visibility = self._layer_model.compute_visibility(
            zoom,
            current_time=self._playhead_time,
            fit_zoom_level=self._fit_zoom_level,
        )
        for node_id, base_visible in base_visibility.items():
            item = self._find_graphics_item(node_id)
            if item is None:
                continue
            temporal_invalid = base_visible and not effective_visibility.get(
                node_id, base_visible
            )
            override = (
                base_visible and node_id in self._temporal_authoring_overrides
            )
            ghost = (
                temporal_invalid
                and self._show_temporal_ghosts
                and not override
            )
            set_ghost = getattr(item, "set_temporal_ghost", None)
            if callable(set_ghost):
                set_ghost(ghost)
            visible = bool(
                effective_visibility.get(node_id, base_visible) or ghost or override
            )
            item.setVisible(visible)
            if (
                not visible
                and self._vertex_editor.editing_feature_id == node_id
            ):
                self._vertex_editor.finish_vertex_editing(
                    emit_geometry_change=False
                )
        self.effective_visibility_changed.emit()
        self._schedule_label_layout()

    def _apply_effective_layer_opacity(self) -> None:
        """Apply inherited layer opacity without replacing temporal factors."""
        if self._layer_model is None:
            return
        node_ids = self._layer_model.compute_visibility(
            self._get_current_zoom_level(),
            current_time=self._playhead_time,
            fit_zoom_level=self._fit_zoom_level,
        )
        for node_id in node_ids:
            node = self._layer_model.find_node_by_id(node_id)
            item = self._find_graphics_item(node_id)
            if node is None or item is None:
                continue
            opacity = self._layer_model.effective_opacity(node)
            set_layer_opacity = getattr(item, "set_layer_opacity", None)
            if callable(set_layer_opacity):
                set_layer_opacity(opacity)
            else:
                item.setOpacity(opacity)

    # ------------------------------------------------------------------
    # Qt Event Overrides (thin dispatchers)
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press: raster edit, drawing, calibration, or normal."""
        # Space held-to-pan takes absolute priority over every sub-system.
        if self._space_pressed and event.button() == Qt.MouseButton.LeftButton:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            super().mousePressEvent(event)
            return

        # Raster editing mode (highest priority).
        # Also handle SAMPLE mode even when edit is not active, so users can
        # probe values without pressing "Edit".
        raster_should_handle = (
            self._raster_edit_tool.is_active
            or self._raster_edit_tool.mode.name == "SAMPLE"
        ) and self.pixmap_item
        if raster_should_handle:
            if event.button() == Qt.MouseButton.LeftButton:
                scene_pos = self.mapToScene(event.position().toPoint())
                logger.debug(
                    "mousePressEvent: raster active — scene_pos=(%.1f,%.1f)",
                    scene_pos.x(),
                    scene_pos.y(),
                )
                if self._raster_edit_tool.handle_mouse_press(scene_pos):
                    return

        # Drawing mode
        if self._drawing_tool.is_drawing and self.pixmap_item:
            if event.button() == Qt.MouseButton.LeftButton:
                scene_pos = self.mapToScene(event.position().toPoint())
                if self._drawing_tool.handle_mouse_press(scene_pos):
                    self._hide_snap_indicator()
                    return

        # One-shot marker placement mode
        if self._handle_marker_placement_mouse_press(event):
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
                    self.setCursor(Qt.CursorShape.ArrowCursor)
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
        # Space panning takes priority — Qt needs the release to end scroll-pan correctly.
        if self._space_pressed and event.button() == Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            return

        # Raster editing
        if self._raster_edit_tool.is_active and self.pixmap_item:
            if event.button() == Qt.MouseButton.LeftButton:
                scene_pos = self.mapToScene(event.position().toPoint())
                logger.debug(
                    "mouseReleaseEvent: raster active — scene_pos=(%.1f,%.1f)",
                    scene_pos.x(),
                    scene_pos.y(),
                )
                if self._raster_edit_tool.handle_mouse_release(scene_pos):
                    return

        super().mouseReleaseEvent(event)
        if not self.calibration_mode and not self._raster_edit_tool.is_active:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move: raster edit, drawing preview, vertex editing, coordinates."""
        scene_pos = self.mapToScene(event.position().toPoint())

        # Raster editing (before super to avoid ScrollHandDrag panning).
        # When Space is held, yield to super() so Qt's pan gesture gets the move.
        if self._raster_edit_tool.is_active:
            if self._space_pressed:
                super().mouseMoveEvent(event)
            else:
                self._raster_edit_tool.handle_mouse_move(scene_pos)
        else:
            super().mouseMoveEvent(event)

        # Drawing mode
        if self._drawing_tool.handle_mouse_move(scene_pos):
            pass
        elif self._vertex_editor.handle_mouse_move(event.position().toPoint()):
            pass

        # Calibration cursor
        if self.calibration_mode:
            self.setCursor(Qt.CursorShape.CrossCursor)
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
        """Handle key presses for map interactions.

        Args:
            event: The key press event.
        """
        map_widget = self._find_map_widget()
        if (
            map_widget is not None
            and getattr(map_widget, "_trajectory_edit_marker_id", None) is not None
            and event.key()
            in (
                Qt.Key.Key_Escape,
                Qt.Key.Key_Return,
                Qt.Key.Key_Enter,
                Qt.Key.Key_Delete,
            )
        ):
            map_widget.keyPressEvent(event)
            return

        # Footprint edit mode — consume keys before general handlers.
        if self.is_editing_footprint:
            if self._handle_footprint_edit_key(event, map_widget):
                return

        if event.key() == Qt.Key.Key_Escape and self._handle_escape_key(event):
            return

        if self._raster_edit_tool.is_active:
            shortcut_modes: dict[int, RasterEditMode] = {
                Qt.Key.Key_B: RasterEditMode.BRUSH,
                Qt.Key.Key_F: RasterEditMode.FILL,
                Qt.Key.Key_G: RasterEditMode.GRADIENT,
                Qt.Key.Key_I: RasterEditMode.SAMPLE,
            }
            shortcut_mode = shortcut_modes.get(event.key())
            if shortcut_mode is not None:
                item = self._raster_edit_tool._get_active_item()
                if (
                    shortcut_mode is RasterEditMode.GRADIENT
                    and item is not None
                    and item.mode == "discrete"
                ):
                    event.accept()
                    return
                self._raster_edit_tool.mode = shortcut_mode
                self.raster_tool_shortcut_requested.emit(
                    shortcut_mode.name.lower()
                )
                event.accept()
                return

        # Space held-to-pan (industry-standard painting-app shortcut).
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_pressed = True
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return

        super().keyPressEvent(event)

    def _handle_escape_key(self, event: "QKeyEvent") -> bool:
        """Cancel the active editing mode or clear the current selection."""
        if self._is_placing_marker:
            self.cancel_marker_placement()
            event.accept()
            return True
        if self._raster_edit_tool.handle_key_escape():
            return True
        if self._drawing_tool.handle_key_escape():
            return True
        if self._vertex_editor.handle_key_escape():
            return True
        if self.graphics_scene.selectedItems():
            self.graphics_scene.clearSelection()
            event.accept()
            return True
        return False

    def keyReleaseEvent(self, event: "QKeyEvent") -> None:
        """Restore drag mode and cursor when Space is released.

        Args:
            event: The key release event.
        """
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_pressed = False
            if self._raster_edit_tool.is_active:
                # Return to brush mode: NoDrag + crosshair cursor
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
                self.viewport().setCursor(Qt.CursorShape.CrossCursor)
            elif not self.calibration_mode:
                self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
                self.viewport().unsetCursor()
            event.accept()
            return
        super().keyReleaseEvent(event)

    def _handle_footprint_edit_key(
        self, event: "QKeyEvent", map_widget: "Optional[MapWidget]"
    ) -> bool:
        """Process a key event while footprint edit mode is active.

        Returns ``True`` if the event was handled (and ``event.accept()``
        was called), ``False`` to let the caller fall through to the
        normal key handlers.

        Args:
            event: The key event to process.
            map_widget: The owning MapWidget for mode-indicator updates.

        Returns:
            bool: ``True`` if consumed, ``False`` otherwise.

        """
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.finish_footprint_edit()
            if map_widget is not None:
                map_widget._update_mode_indicator()
            event.accept()
            return True
        if key == Qt.Key.Key_Escape:
            self.cancel_footprint_edit()
            if map_widget is not None:
                map_widget._update_mode_indicator()
            event.accept()
            return True
        item = self._footprint_items.get(self._editing_footprint_id or "")
        if item is None:
            return False
        iw = (
            self.pixmap_item.boundingRect().width()
            if self.pixmap_item
            else 1000.0
        )
        ih = (
            self.pixmap_item.boundingRect().height()
            if self.pixmap_item
            else 1000.0
        )
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        step = 10.0 if shift else 1.0
        nudge_map: dict[int, tuple[float, float]] = {
            Qt.Key.Key_Left: (-step / iw, 0.0),
            Qt.Key.Key_Right: (step / iw, 0.0),
            Qt.Key.Key_Up: (0.0, -step / ih),
            Qt.Key.Key_Down: (0.0, step / ih),
        }
        if key in nudge_map:
            item.nudge(*nudge_map[key])
            event.accept()
            return True
        if key == Qt.Key.Key_BracketLeft:
            item.rotate(-5.0)
            event.accept()
            return True
        if key == Qt.Key.Key_BracketRight:
            item.rotate(5.0)
            event.accept()
            return True
        return False

    def _find_map_widget(self) -> "Optional[MapWidget]":
        """Walks up the parent chain to find the owning MapWidget.

        Returns:
            The MapWidget ancestor, or None.
        """
        # Avoid a circular import by checking a MapWidget-specific method.
        widget = self.parentWidget()
        while widget is not None:
            if hasattr(widget, "get_selected_map_id"):
                return cast("MapWidget", widget)
            widget = widget.parentWidget()
        return None

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel for zooming, with Ctrl+scroll brush resize."""
        # Ctrl+scroll → adjust raster brush size
        if (
            event.modifiers() & Qt.KeyboardModifier.ControlModifier
            and self._raster_edit_tool.is_active
        ):
            delta = event.angleDelta().y()
            if delta != 0:
                step = max(1, self._raster_edit_tool.brush_size // 5)
                new_size = self._raster_edit_tool.brush_size + (
                    step if delta > 0 else -step
                )
                new_size = max(1, min(128, new_size))
                self._raster_edit_tool.brush_size = new_size
                self._raster_edit_tool.refresh_cursor()
                self.raster_brush_resize_requested.emit(new_size)
            event.accept()
            return

        zoom_out_factor = 1 / MAP_ZOOM_IN_FACTOR

        factor = MAP_ZOOM_IN_FACTOR if event.angleDelta().y() > 0 else zoom_out_factor

        self.scale(factor, factor)
        self._trajectory.update_label_scales()
        self._apply_scale_dependent_visibility()
        self._schedule_label_layout()
        self._layout_footprint_labels()

        # Keep the raster brush cursor overlay sized correctly after zoom
        if self._raster_edit_tool.is_active:
            self._raster_edit_tool.refresh_cursor()

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
        from src.gui.widgets.map.trajectory_renderer import TrajectoryPathItem

        if isinstance(item, KeyframeItem):
            self._interaction.show_trajectory_context_menu(
                item.marker_id, event.globalPos()
            )
        elif isinstance(item, MarkerItem):
            self._interaction.show_marker_context_menu(item, event.globalPos())
        elif isinstance(item, TrajectoryPathItem):
            self._interaction.show_trajectory_context_menu(
                item.marker_id, event.globalPos()
            )
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

    def drawForeground(self, painter: QPainter, rect: QRectF | QRect) -> None:
        """Draw overlay elements on top of the scene."""
        super().drawForeground(painter, rect)

        # Draw calibration line
        if self.calibration_mode and len(self.calibration_points) > 0:
            painter.save()

            theme = self.tm.get_theme()
            pen = QPen(QColor(theme.get("destructive", "#e74c3c")))
            pen.setWidth(2)
            pen.setStyle(Qt.PenStyle.DashLine)
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

                mid = QPointF(
                    (start_pos.x() + end_pos.x()) / 2.0,
                    (start_pos.y() + end_pos.y()) / 2.0,
                )

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
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(t_rect, 4, 4)

                painter.setPen(Qt.GlobalColor.white)
                painter.drawText(t_rect, Qt.AlignmentFlag.AlignCenter, text)

            painter.restore()

        # Scale bar is rendered by _scale_bar_overlay (viewport widget).
        # Update its resolution from the current transform.
        self._update_scale_bar_overlay()
