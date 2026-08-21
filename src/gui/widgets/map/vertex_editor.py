"""Vertex Editor for the Map Graphics View.

Manages vertex editing mode: draggable vertex handles, midpoint ghost
handles for segment insertion, snapping, geometry mutation, and
style overlay during editing.
"""

import logging
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Dict, Optional

from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QGraphicsItem, QGraphicsView

from src.gui.constants import (
    MAP_EDIT_DASH_PATTERN,
    MAP_EDIT_STROKE_COLOR,
    MAP_EDIT_STROKE_WIDTH,
    MAP_LAYER_Z_UI_OVERLAY,
)
from src.gui.widgets.map.edit_handles import (
    DraggableEditHandle,
    MidpointEditHandle,
    snap_to_edit_handles,
)
from src.gui.widgets.map.feature_items import PathItem, RegionItem
from src.gui.widgets.map.snapping_manager import SnappingManager

if TYPE_CHECKING:
    from src.gui.widgets.map.map_graphics_view import MapGraphicsView

logger = logging.getLogger(__name__)

# Normalized coordinate precision (decimal places)
NORMALIZED_COORD_PRECISION = 6


class VertexEditor:
    """Manages vertex editing for path and region features.

    Provides draggable vertex handles, midpoint ghost handles for segment
    insertion, snapping, geometry mutation, and editing style overlay.

    Args:
        view: The parent MapGraphicsView.
        snapping_manager: The shared SnappingManager instance.
    """

    # Visual style for the feature being edited
    _EDIT_DASH_PATTERN = MAP_EDIT_DASH_PATTERN
    _EDIT_STROKE_COLOR = MAP_EDIT_STROKE_COLOR
    _EDIT_STROKE_WIDTH = MAP_EDIT_STROKE_WIDTH

    def __init__(
        self,
        view: "MapGraphicsView",
        snapping_manager: SnappingManager,
    ) -> None:
        """Initialize vector-feature vertex editing."""
        self._view = view
        self._snapping_manager = snapping_manager

        # Editing state
        self._editing_feature_id: Optional[str] = None
        self._vertex_handles: list[DraggableEditHandle[int]] = []
        self._midpoint_handles: list[MidpointEditHandle[int]] = []
        self._editing_original_style: Optional[Dict[str, Any]] = None
        self._editing_original_geometry: list[dict[str, float]] | None = None
        self._managed_session = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_editing_vertices(self) -> bool:
        """True when vertex editing mode is active.

        Returns:
            bool: Whether a feature's vertices are being edited.
        """
        return self._editing_feature_id is not None

    @property
    def editing_feature_id(self) -> Optional[str]:
        """The ID of the feature currently being edited.

        Returns:
            Optional[str]: The feature ID, or None.
        """
        return self._editing_feature_id

    @property
    def is_managed_session(self) -> bool:
        """Return whether an app coordinator owns the current edit session."""
        return self._managed_session

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_vertex_editing(
        self, item: "PathItem | RegionItem", *, managed_session: bool = False
    ) -> None:
        """Enters vertex editing mode for a feature.

        Shows draggable handles on each vertex and ghost midpoint handles
        on each segment.

        Args:
            item: The PathItem or RegionItem to edit.
        """
        self.cancel_vertex_editing()
        self._editing_feature_id = item.marker_id
        self._managed_session = managed_session

        geometry = item._geometry
        if not geometry or not self._view.pixmap_item:
            return

        # Save original style and apply editing visual feedback
        self._editing_original_style = dict(item._style)
        self._editing_original_geometry = deepcopy(item._geometry)
        item._style["dash_pattern"] = self._EDIT_DASH_PATTERN
        item._style["stroke_color"] = self._EDIT_STROKE_COLOR
        item._style["stroke_width"] = self._EDIT_STROKE_WIDTH
        item.update()

        rect = self._view.pixmap_item.sceneBoundingRect()
        for i, pt in enumerate(geometry):
            sx = rect.left() + pt["x"] * rect.width()
            sy = rect.top() + pt["y"] * rect.height()
            handle = DraggableEditHandle(
                i, self._on_vertex_moved, self._on_vertex_deleted
            )
            handle.setPos(sx, sy)
            handle.set_notifications_enabled(True)
            handle.setZValue(MAP_LAYER_Z_UI_OVERLAY + 1)
            self._view.graphics_scene.addItem(handle)
            self._vertex_handles.append(handle)

        self._rebuild_midpoint_handles()
        self._view.setDragMode(QGraphicsView.DragMode.NoDrag)
        logger.info(
            f"Vertex editing started for {item.marker_id} ({len(geometry)} vertices)"
        )
        self._view._refresh_mode_indicator()

    def finish_vertex_editing(self, emit_geometry_change: bool = True) -> None:
        """Commits vertex edits and removes handles.

        Restores the original feature style and emits
        ``feature_geometry_changed`` with the updated normalized
        coordinates so the command layer can persist the change.

        Args:
            emit_geometry_change: Whether to emit the geometry-changed
                signal for the edited feature. Use ``False`` when the
                feature is being deleted and edit handles only need to be
                torn down.
        """
        finished_id: Optional[str] = None
        finished_geometry: Optional[list] = None

        if self._editing_feature_id:
            item = self._view.feature_items.get(self._editing_feature_id)
            if item:
                # Restore original style
                if self._editing_original_style is not None:
                    item._style = self._editing_original_style
                    self._editing_original_style = None
                    item.update()
                if emit_geometry_change and item._geometry:
                    finished_id = self._editing_feature_id
                    finished_geometry = list(item._geometry)

        # Clear editing state BEFORE emitting signal so that
        # is_editing_vertices returns False when _update_mode_indicator
        # is called from the connected slot.
        self._editing_feature_id = None
        self._managed_session = False
        self._editing_original_geometry = None
        for handle in self._vertex_handles:
            self._view.graphics_scene.removeItem(handle)
        self._vertex_handles.clear()
        for mh in self._midpoint_handles:
            self._view.graphics_scene.removeItem(mh)
        self._midpoint_handles.clear()
        self._view._hide_snap_indicator()
        if not self._view.is_drawing:
            self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        # Emit after state is fully cleared
        if finished_id and finished_geometry:
            self._view.feature_geometry_changed.emit(finished_id, finished_geometry)
            logger.info(f"Vertex editing finished for {finished_id}")

    def cancel_vertex_editing(self) -> None:
        """Discard vertex changes and restore the session-start geometry."""
        item = self._view.feature_items.get(self._editing_feature_id or "")
        original = self._editing_original_geometry
        if item is not None and original is not None:
            item.set_geometry(original, item._anchor_x, item._anchor_y)
        self.finish_vertex_editing(emit_geometry_change=False)

    def handle_mouse_move(self, pos: Any) -> bool:
        """Handle cursor updates during vertex editing mode.

        Args:
            pos: View-local position (QPoint).

        Returns:
            True if editing mode is active (cursor was set).
        """
        if not self._editing_feature_id:
            return False

        item_under = self._view.itemAt(pos)
        if isinstance(item_under, (DraggableEditHandle, MidpointEditHandle)):
            pass  # Handle sets its own cursor
        elif (
            item_under
            and hasattr(item_under, "marker_id")
            and item_under.marker_id == self._editing_feature_id
        ):
            self._view.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self._view.setCursor(Qt.CursorShape.ArrowCursor)
        return True

    def handle_key_escape(self) -> bool:
        """Handle Escape by cancelling the active vertex-editing session.

        Returns:
            True if the event was consumed.
        """
        if self._editing_feature_id:
            if self._managed_session:
                self._view.feature_geometry_cancel_requested.emit()
            else:
                self.cancel_vertex_editing()
            return True
        return False

    # ------------------------------------------------------------------
    # Internal callbacks
    # ------------------------------------------------------------------

    def _on_vertex_moved(self, index: int, new_scene_pos: QPointF) -> None:
        """Callback when a vertex handle is dragged to a new position.

        Args:
            index: The vertex index that was moved.
            new_scene_pos: The new scene position.
        """
        if not self._editing_feature_id or not self._view.pixmap_item:
            return

        item = self._view.feature_items.get(self._editing_feature_id)
        if not item:
            return

        # --- Cross-feature snapping via SnappingManager ---
        exclude: set[QGraphicsItem] = {item}
        for h in self._vertex_handles:
            exclude.add(h)
        for mh in self._midpoint_handles:
            exclude.add(mh)
        snap_indicator = self._view._snap_indicator
        if snap_indicator:
            exclude.add(snap_indicator)

        snap_result = self._snapping_manager.snap_point(
            new_scene_pos, self._view.transform(), exclude
        )

        if snap_result.snapped:
            snap_pos = snap_result.pos
            self._view._show_snap_indicator(snap_pos, snap_result.snap_type)
        else:
            # Fallback: same-feature vertex snapping
            snap_pos = self._snap_to_nearby_vertex(index, new_scene_pos)
            self._view._hide_snap_indicator()

        # Synchronize the vertex handle to the snap position
        if index < len(self._vertex_handles):
            handle = self._vertex_handles[index]
            handle.set_notifications_enabled(False)
            handle.setPos(snap_pos)
            handle.set_notifications_enabled(True)

        # Convert scene pos → normalized
        rect = self._view.pixmap_item.sceneBoundingRect()
        nx = (snap_pos.x() - rect.left()) / rect.width()
        ny = (snap_pos.y() - rect.top()) / rect.height()
        nx = max(0.0, min(1.0, nx))
        ny = max(0.0, min(1.0, ny))

        if index < len(item._geometry):
            pt = item._geometry[index]
            pt["x"] = round(nx, NORMALIZED_COORD_PRECISION)
            pt["y"] = round(ny, NORMALIZED_COORD_PRECISION)
            if isinstance(item, PathItem):
                item._build_path()
                item._position_label()
            elif isinstance(item, RegionItem):
                item._build_polygon()
                item._position_label()
            item.prepareGeometryChange()
            item.update()

            self._update_midpoint_positions()

    def _snap_to_nearby_vertex(self, moving_index: int, scene_pos: QPointF) -> QPointF:
        """Snaps a position to the nearest existing vertex within snap radius.

        Args:
            moving_index: Index of the vertex being moved.
            scene_pos: Current scene position of the handle.

        Returns:
            Snapped scene position, or the original if no snap.
        """
        return snap_to_edit_handles(
            moving_index,
            scene_pos,
            self._vertex_handles,
            self._view.transform().m11(),
        )

    def _on_vertex_deleted(self, index: int) -> None:
        """Removes a vertex from the feature being edited.

        Args:
            index: The index of the vertex to remove.
        """
        item = self._view.feature_items.get(self._editing_feature_id or "")
        if not item or not item._geometry:
            return

        min_verts = 3 if isinstance(item, RegionItem) else 2
        if len(item._geometry) <= min_verts:
            logger.warning(
                f"Cannot delete vertex: minimum {min_verts} vertices required"
            )
            return

        del item._geometry[index]

        if isinstance(item, PathItem):
            item._build_path()
            item._position_label()
        elif isinstance(item, RegionItem):
            item._build_polygon()
            item._position_label()
        item.prepareGeometryChange()
        item.update()

        self._rebuild_vertex_handles(item)
        self._rebuild_midpoint_handles()
        logger.info(f"Deleted vertex {index}, {len(item._geometry)} remaining")

    def _on_midpoint_insert(self, segment_index: int, scene_pos: QPointF) -> None:
        """Inserts a new vertex at the midpoint of a segment.

        Args:
            segment_index: Index of the segment.
            scene_pos: Scene position of the new vertex.
        """
        item = self._view.feature_items.get(self._editing_feature_id or "")
        if not item or not item._geometry or not self._view.pixmap_item:
            return

        rect = self._view.pixmap_item.sceneBoundingRect()
        nx = (scene_pos.x() - rect.left()) / rect.width()
        ny = (scene_pos.y() - rect.top()) / rect.height()
        nx = max(0.0, min(1.0, nx))
        ny = max(0.0, min(1.0, ny))

        new_pt = {
            "x": round(nx, NORMALIZED_COORD_PRECISION),
            "y": round(ny, NORMALIZED_COORD_PRECISION),
        }
        item._geometry.insert(segment_index + 1, new_pt)

        if isinstance(item, PathItem):
            item._build_path()
            item._position_label()
        elif isinstance(item, RegionItem):
            item._build_polygon()
            item._position_label()
        item.prepareGeometryChange()
        item.update()

        self._rebuild_vertex_handles(item)
        self._rebuild_midpoint_handles()
        logger.info(
            f"Inserted vertex after index {segment_index}, {len(item._geometry)} total"
        )

    # ------------------------------------------------------------------
    # Handle management
    # ------------------------------------------------------------------

    def _rebuild_midpoint_handles(self) -> None:
        """Rebuilds ghost midpoint handles between each pair of vertices."""
        for mh in self._midpoint_handles:
            self._view.graphics_scene.removeItem(mh)
        self._midpoint_handles.clear()

        item = self._view.feature_items.get(self._editing_feature_id or "")
        if not item or not item._geometry or not self._view.pixmap_item:
            return

        rect = self._view.pixmap_item.sceneBoundingRect()
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

            mh = MidpointEditHandle(i, self._on_midpoint_insert)
            mh.setPos(sx, sy)
            self._view.graphics_scene.addItem(mh)
            self._midpoint_handles.append(mh)

    def _update_midpoint_positions(self) -> None:
        """Repositions existing midpoint handles without recreating them."""
        item = self._view.feature_items.get(self._editing_feature_id or "")
        if not item or not item._geometry or not self._view.pixmap_item:
            return

        rect = self._view.pixmap_item.sceneBoundingRect()
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

    def _rebuild_vertex_handles(self, item: "PathItem | RegionItem") -> None:
        """Removes and recreates all vertex handles for the current feature.

        Args:
            item: The feature item whose handles need rebuilding.
        """
        for handle in self._vertex_handles:
            self._view.graphics_scene.removeItem(handle)
        self._vertex_handles.clear()

        if not item._geometry or not self._view.pixmap_item:
            return

        rect = self._view.pixmap_item.sceneBoundingRect()
        for i, pt in enumerate(item._geometry):
            sx = rect.left() + pt["x"] * rect.width()
            sy = rect.top() + pt["y"] * rect.height()
            handle = DraggableEditHandle(
                i, self._on_vertex_moved, self._on_vertex_deleted
            )
            handle.setPos(sx, sy)
            handle.set_notifications_enabled(True)
            handle.setZValue(MAP_LAYER_Z_UI_OVERLAY + 1)
            self._view.graphics_scene.addItem(handle)
            self._vertex_handles.append(handle)
