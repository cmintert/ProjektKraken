"""Drawing Tool for the Map Graphics View.

Manages path/region drawing mode: vertex placement, rubber-band preview,
snapping during draw, and coordinate conversion on completion.
"""

import logging
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsView,
)

from src.core.border_trace import simple_draft
from src.core.region_geometry import MIN_REGION_AREA, Geometry, Point, signed_area
from src.core.theme_manager import ThemeManager
from src.gui.constants import MAP_LAYER_Z_UI_OVERLAY
from src.gui.widgets.map.border_trace_tool import BorderTraceTool
from src.gui.widgets.map.region_paths import region_path
from src.gui.widgets.map.region_preview import RegionPreview
from src.gui.widgets.map.snapping_manager import SnappingManager

if TYPE_CHECKING:
    from src.gui.widgets.map.map_graphics_view import MapGraphicsView

logger = logging.getLogger(__name__)

# Drawing mode constants
NORMALIZED_COORD_PRECISION = 6  # decimal places for normalized coordinates
MINIMUM_PATH_VERTICES = 2
MINIMUM_REGION_VERTICES = 3
MINIMUM_REGION_PREVIEW_VERTICES = 2


class DrawingTool:
    """Manages drawing mode for paths and regions.

    Handles vertex placement, rubber-band preview rendering,
    snapping during draw, and coordinate conversion on completion.

    Args:
        view: The parent MapGraphicsView.
        snapping_manager: The shared SnappingManager instance.
    """

    def __init__(
        self,
        view: "MapGraphicsView",
        snapping_manager: SnappingManager,
    ) -> None:
        """Initialize drawing state for a map graphics view."""
        self._view = view
        self._snapping_manager = snapping_manager
        self.trace = BorderTraceTool(view, snapping_manager)
        self._copied_points: dict[int, Point] = {}

        # Drawing state
        self._drawing_mode: Optional[str] = None  # None, "path", or "region"
        self._drawing_vertices: list[QPointF] = []  # scene coordinates
        self._drawing_preview_item: Optional[QGraphicsPathItem] = None
        self._drawing_dots: list[QGraphicsItem] = []  # vertex dots
        self.retain_draft = False
        self.paused = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

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

    @property
    def vertex_count(self) -> int:
        """Return the number of vertices in the active drawing draft."""
        return len(self._drawing_vertices)

    @property
    def can_finish(self) -> bool:
        """Return whether the current drawing draft has valid geometry."""
        if self.trace.active:
            return False
        if self._drawing_mode == "path":
            return len(self._drawing_vertices) >= MINIMUM_PATH_VERTICES
        if self._drawing_mode == "region":
            return len(self._drawing_vertices) >= MINIMUM_REGION_VERTICES
        return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_drawing(self, feature_type: str) -> None:
        """Enters drawing mode for paths or regions.

        Click to add vertices; Confirm or Enter to finish; Escape to cancel.

        Args:
            feature_type: 'path' or 'region'.
        """
        self._drawing_mode = feature_type
        self.retain_draft = self.paused = False
        self.trace.cancel()
        self._copied_points.clear()
        self._drawing_vertices.clear()
        self._clear_drawing_preview()
        self._view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self._view.setCursor(Qt.CursorShape.CrossCursor)
        self._view.border_trace_changed.emit()
        logger.info(f"Drawing mode started: {feature_type}")

    def cancel_drawing(self) -> None:
        """Exits drawing mode without saving."""
        self._drawing_mode = None
        self.retain_draft = self.paused = False
        self.trace.cancel()
        self._copied_points.clear()
        self._drawing_vertices.clear()
        self._clear_drawing_preview()
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._view.setCursor(Qt.CursorShape.ArrowCursor)
        self._view.border_trace_changed.emit()
        self._view.drawing_cancelled.emit()
        logger.info("Drawing cancelled")

    def finish_drawing(self) -> None:
        """Completes the current drawing and emits the geometry.

        Converts scene-coordinate vertices to normalized coordinates
        and emits ``drawing_finished(feature_type, geometry)``.
        """
        if self.trace.active:
            return
        if not self._drawing_mode or not self._view.pixmap_item:
            self.cancel_drawing()
            return

        min_points = (
            MINIMUM_PATH_VERTICES
            if self._drawing_mode == "path"
            else MINIMUM_REGION_VERTICES
        )
        if len(self._drawing_vertices) < min_points:
            logger.warning(
                f"Need at least {min_points} points for {self._drawing_mode}"
            )
            return

        # Convert scene coords to normalized
        points = self.draft_points()
        if self._drawing_mode == "region" and not simple_draft(points, closed=True):
            self.trace.report("The region's border crosses or repeats itself.")
            return
        if (
            self._drawing_mode == "region"
            and abs(signed_area(points)) <= MIN_REGION_AREA
        ):
            self.trace.report("The drawn region needs more filled area.")
            return
        geometry = [{"x": x, "y": y} for x, y in points]

        if self.retain_draft:
            self._view.drawing_proposed.emit(geometry)
            return

        feature_type = self._drawing_mode
        logger.info(f"Drawing finished: {feature_type} with {len(geometry)} vertices")

        # Clean up drawing state
        self._drawing_mode = None
        self.trace.cancel()
        self._copied_points.clear()
        self._drawing_vertices.clear()
        self._clear_drawing_preview()
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._view.setCursor(Qt.CursorShape.ArrowCursor)

        self._view.border_trace_changed.emit()
        self._view.drawing_finished.emit(feature_type, geometry)

    def handle_mouse_press(self, scene_pos: QPointF) -> bool:
        """Handle mouse press during drawing mode.

        Args:
            scene_pos: Scene position of the click.

        Returns:
            True if the event was consumed.
        """
        if not self._drawing_mode or not self._view.pixmap_item:
            return False

        if self.paused:
            return True

        if self.trace.active:
            self.trace.pick(scene_pos, self.draft_points())
            return True

        item_pos = self._view.pixmap_item.mapFromScene(scene_pos)
        if self._view.pixmap_item.contains(item_pos):
            # Apply snapping to placed vertex
            snap_result = self._snapping_manager.snap_point(
                scene_pos, self._view.transform()
            )
            self._add_drawing_vertex(
                snap_result.pos if snap_result.snapped else scene_pos
            )
            return True
        return False

    def handle_mouse_move(self, scene_pos: QPointF) -> bool:
        """Handle mouse move during drawing mode.

        Shows snap indicator and updates rubber-band preview.

        Args:
            scene_pos: Current mouse position in scene coordinates.

        Returns:
            True if drawing mode is active (cursor was set).
        """
        if not self._drawing_mode:
            return False

        if self.paused:
            return True
        self._view.setCursor(Qt.CursorShape.CrossCursor)
        if self.trace.active:
            self.trace.hover(scene_pos)
            return True
        snap_result = self._snapping_manager.snap_point(
            scene_pos, self._view.transform()
        )
        if snap_result.snapped:
            self._view._show_snap_indicator(snap_result.pos, snap_result.snap_type)
        else:
            self._view._hide_snap_indicator()
        if self._drawing_vertices:
            preview_pos = snap_result.pos if snap_result.snapped else scene_pos
            self._update_drawing_preview(preview_pos)
        return True

    def handle_double_click(self) -> bool:
        """Consume double-clicks without implicitly confirming a drawing.

        Returns:
            True if the event was consumed.
        """
        return self._drawing_mode is not None

    def handle_key_escape(self) -> bool:
        """Handle Escape key to cancel drawing.

        Returns:
            True if the event was consumed.
        """
        if self.trace.active:
            self.trace.cancel()
            return True
        if self._drawing_mode:
            self.cancel_drawing()
            return True
        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def draft_points(self) -> tuple[Point, ...]:
        """Return authored coordinates, retaining the precise copied border."""
        return tuple(
            self._copied_points[i]
            if i in self._copied_points
            else self._normal_point(pos)
            for i, pos in enumerate(self._drawing_vertices)
        )

    def show_retained_preview(self, geometries: tuple[Geometry, ...] | None) -> None:
        """Pause drawing for a result, or restore its unmodified input outline."""
        self.paused = geometries is not None
        self.trace.cancel()
        for dot in self._drawing_dots:
            dot.setVisible(not self.paused)
        if self._drawing_preview_item is not None:
            self._view.graphics_scene.removeItem(self._drawing_preview_item)
            self._drawing_preview_item = None
        if geometries is None:
            if self._drawing_vertices:
                self._update_drawing_preview(self._drawing_vertices[-1])
        elif self._view.pixmap_item is not None:
            path = QPainterPath()
            path.setFillRule(Qt.FillRule.OddEvenFill)
            rect = self._view.pixmap_item.sceneBoundingRect()
            for geometry in geometries:
                path.addPath(region_path(geometry, rect))
            preview = RegionPreview(self._view.graphics_scene)
            preview.show_path(path, filled=True)
            self._drawing_preview_item = preview
        self._view.border_trace_changed.emit()

    def restyle_preview(self) -> None:
        """Refresh a retained drawing/result without changing its coordinates."""
        if isinstance(self._drawing_preview_item, RegionPreview):
            self._drawing_preview_item.restyle()

    def _normal_point(self, pos: QPointF) -> Point:
        x, y = self._view.coord_system.to_normalized(pos)
        x, y = self._view.coord_system.clamp_normalized(x, y)
        return (
            round(x, NORMALIZED_COORD_PRECISION),
            round(y, NORMALIZED_COORD_PRECISION),
        )

    def accept_trace(self) -> None:
        """Append the chosen arc to the region draft."""
        if not self.trace.can_use:
            return
        from src.gui.widgets.map.region_paths import scene_point

        assert self._view.pixmap_item is not None
        rect = self._view.pixmap_item.sceneBoundingRect()
        for point in self.trace.append_points(self.draft_points()):
            self._copied_points[len(self._drawing_vertices)] = point
            self._add_drawing_vertex(scene_point(point, rect), refresh=False)
        self._update_drawing_preview(self._drawing_vertices[-1])
        self.trace.cancel()

    def _add_drawing_vertex(self, scene_pos: QPointF, *, refresh: bool = True) -> None:
        """Adds a vertex to the current drawing.

        Args:
            scene_pos: The vertex position in scene coordinates.
            refresh: Redraw immediately for an individual vertex.
        """
        if not self.trace.active and self.trace.message:
            self.trace.report("")
        self._drawing_vertices.append(scene_pos)

        # Add visible dot
        dot = QGraphicsEllipseItem(-3, -3, 6, 6)
        dot.setPos(scene_pos)
        theme = ThemeManager().get_theme()
        dot.setBrush(QBrush(QColor(theme["selection_bg"])))
        dot.setPen(QPen(QColor(theme["surface"]), 1))
        dot.setZValue(MAP_LAYER_Z_UI_OVERLAY)
        self._view.graphics_scene.addItem(dot)
        self._drawing_dots.append(dot)

        if refresh:
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
            self._view.graphics_scene.removeItem(self._drawing_preview_item)
            self._drawing_preview_item = None

        path = QPainterPath()
        path.moveTo(self._drawing_vertices[0])
        for pt in self._drawing_vertices[1:]:
            path.lineTo(pt)
        # Rubber band to mouse
        path.lineTo(mouse_pos)
        # Close for region preview
        if (
            self._drawing_mode == "region"
            and len(self._drawing_vertices) >= MINIMUM_REGION_PREVIEW_VERTICES
        ):
            path.lineTo(self._drawing_vertices[0])

        preview = RegionPreview(self._view.graphics_scene)
        preview.show_path(path, filled=self._drawing_mode == "region")
        self._drawing_preview_item = preview

    def _clear_drawing_preview(self) -> None:
        """Removes all drawing preview items from the scene."""
        if self._drawing_preview_item:
            self._view.graphics_scene.removeItem(self._drawing_preview_item)
            self._drawing_preview_item = None
        for dot in self._drawing_dots:
            self._view.graphics_scene.removeItem(dot)
        self._drawing_dots.clear()
