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

from src.app.constants import MAP_LAYER_Z_UI_OVERLAY
from src.gui.widgets.map.snapping_manager import SnappingManager

if TYPE_CHECKING:
    from src.gui.widgets.map.map_graphics_view import MapGraphicsView

logger = logging.getLogger(__name__)

# Drawing mode constants
NORMALIZED_COORD_PRECISION = 6  # decimal places for normalized coordinates


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
        self._view = view
        self._snapping_manager = snapping_manager

        # Drawing state
        self._drawing_mode: Optional[str] = None  # None, "path", or "region"
        self._drawing_vertices: list[QPointF] = []  # scene coordinates
        self._drawing_preview_item: Optional[QGraphicsPathItem] = None
        self._drawing_dots: list[QGraphicsItem] = []  # vertex dots

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

    # ------------------------------------------------------------------
    # Public API
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
        self._view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self._view.setCursor(Qt.CursorShape.CrossCursor)
        logger.info(f"Drawing mode started: {feature_type}")

    def cancel_drawing(self) -> None:
        """Exits drawing mode without saving."""
        self._drawing_mode = None
        self._drawing_vertices.clear()
        self._clear_drawing_preview()
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._view.setCursor(Qt.CursorShape.ArrowCursor)
        self._view.drawing_cancelled.emit()
        logger.info("Drawing cancelled")

    def finish_drawing(self) -> None:
        """Completes the current drawing and emits the geometry.

        Converts scene-coordinate vertices to normalized coordinates
        and emits ``drawing_finished(feature_type, geometry)``.
        """
        if not self._drawing_mode or not self._view.pixmap_item:
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
            nx, ny = self._view.coord_system.to_normalized(sp)
            nx, ny = self._view.coord_system.clamp_normalized(nx, ny)
            geometry.append(
                {
                    "x": round(nx, NORMALIZED_COORD_PRECISION),
                    "y": round(ny, NORMALIZED_COORD_PRECISION),
                }
            )

        feature_type = self._drawing_mode
        logger.info(f"Drawing finished: {feature_type} with {len(geometry)} vertices")

        # Clean up drawing state
        self._drawing_mode = None
        self._drawing_vertices.clear()
        self._clear_drawing_preview()
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._view.setCursor(Qt.CursorShape.ArrowCursor)

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

        self._view.setCursor(Qt.CursorShape.CrossCursor)
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
        """Handle double-click to finish drawing.

        Returns:
            True if the event was consumed.
        """
        if self._drawing_mode:
            self.finish_drawing()
            return True
        return False

    def handle_key_escape(self) -> bool:
        """Handle Escape key to cancel drawing.

        Returns:
            True if the event was consumed.
        """
        if self._drawing_mode:
            self.cancel_drawing()
            return True
        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_drawing_vertex(self, scene_pos: QPointF) -> None:
        """Adds a vertex to the current drawing.

        Args:
            scene_pos: The vertex position in scene coordinates.
        """
        self._drawing_vertices.append(scene_pos)

        # Add visible dot
        dot = QGraphicsEllipseItem(-3, -3, 6, 6)
        dot.setPos(scene_pos)
        dot.setBrush(QBrush(QColor("#e74c3c")))
        dot.setPen(QPen(QColor("#FFFFFF"), 1))
        dot.setZValue(MAP_LAYER_Z_UI_OVERLAY)
        self._view.scene.addItem(dot)
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
            self._view.scene.removeItem(self._drawing_preview_item)
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
        self._drawing_preview_item.setZValue(MAP_LAYER_Z_UI_OVERLAY)
        self._view.scene.addItem(self._drawing_preview_item)

    def _clear_drawing_preview(self) -> None:
        """Removes all drawing preview items from the scene."""
        if self._drawing_preview_item:
            self._view.scene.removeItem(self._drawing_preview_item)
            self._drawing_preview_item = None
        for dot in self._drawing_dots:
            self._view.scene.removeItem(dot)
        self._drawing_dots.clear()
