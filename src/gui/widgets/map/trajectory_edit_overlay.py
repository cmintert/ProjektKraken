"""Interactive spatial overlay for one trajectory edit session."""

from typing import TYPE_CHECKING, Callable

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem, QGraphicsView

from src.core.theme_manager import ThemeManager
from src.core.trajectory import SEGMENT_MODE_STEP, SegmentKey, SegmentMode
from src.core.trajectory_edit import TrajectoryEditSession, TrajectoryEditSnapshot
from src.gui.constants import MAP_LAYER_Z_UI_OVERLAY
from src.gui.widgets.map.edit_handles import (
    DraggableEditHandle,
    MidpointEditHandle,
    snap_to_edit_handles,
)

if TYPE_CHECKING:
    from src.gui.widgets.map.map_graphics_view import MapGraphicsView


_MINIMUM_PATH_KEYFRAMES = 2


class TrajectoryEditOverlay:
    """Render and update only the active trajectory's editable geometry."""

    def __init__(self, view: "MapGraphicsView") -> None:
        """Initialize direct trajectory-edit scene overlays."""
        self._view = view
        self._marker_id: str | None = None
        self._selected_keyframe_id: str | None = None
        self._active_date_edit_id: str | None = None
        self._speed_anchor_id: str | None = None
        self._equalization_start_id: str | None = None
        self._equalization_end_id: str | None = None
        self._equalized_keyframe_ids: set[str] = set()
        self._route_point_ids: set[str] = set()
        self._path_item: QGraphicsPathItem | None = None
        self._relocation_path_items: list[QGraphicsPathItem] = []
        self._segment_modes: dict[SegmentKey, SegmentMode] = {}
        self._temporal_path_item: QGraphicsPathItem | None = None
        self._keyframe_handles: list[DraggableEditHandle[str]] = []
        self._midpoint_handles: list[MidpointEditHandle[tuple[str, str]]] = []
        self._second_location_handle: DraggableEditHandle[str] | None = None
        self._is_second_location_following_cursor = False

    @property
    def is_active(self) -> bool:
        """Whether an edit overlay is currently rendered."""
        return self._marker_id is not None

    @property
    def keyframe_handles(self) -> list[DraggableEditHandle[str]]:
        """Return active keyframe handles for tests and view coordination."""
        return list(self._keyframe_handles)

    @property
    def midpoint_handles(
        self,
    ) -> list[MidpointEditHandle[tuple[str, str]]]:
        """Return active midpoint handles for tests and view coordination."""
        return list(self._midpoint_handles)

    @property
    def temporal_path_item(self) -> QGraphicsPathItem | None:
        """Return the temporal preview path for diagnostics and tests."""
        return self._temporal_path_item

    @property
    def selected_keyframe_id(self) -> str | None:
        """Return the selected stable identity, if any."""
        return self._selected_keyframe_id

    def show(
        self,
        snapshot: TrajectoryEditSnapshot,
        *,
        date_formatter: Callable[[float], str] | None = None,
    ) -> None:
        """Rebuild the active overlay from serialized session state."""
        self.clear()
        format_date = date_formatter or (lambda value: f"T {value:g}")
        self._marker_id = snapshot["marker_id"]
        theme = ThemeManager().get_theme()
        selected_id = snapshot["selected_keyframe_id"]
        self._selected_keyframe_id = selected_id
        self._active_date_edit_id = snapshot["active_date_edit_id"]
        self._speed_anchor_id = snapshot["speed_anchor_id"]
        self._equalization_start_id = snapshot["equalization_start_id"]
        self._equalization_end_id = snapshot["equalization_end_id"]
        self._equalized_keyframe_ids = {
            change["edit_id"] for change in snapshot["equalization_changes"]
        }
        previewing = snapshot["is_equalization_previewing"]
        self._segment_modes = {
            (
                snapshot["keyframes"][index - 1]["edit_id"],
                keyframe["edit_id"],
            ): keyframe["arrival_mode"]
            for index, keyframe in enumerate(snapshot["keyframes"])
            if index > 0 and keyframe["arrival_mode"] is not None
        }
        self._route_point_ids = {
            keyframe["edit_id"]
            for keyframe in snapshot["keyframes"]
            if keyframe["point_kind"] == "route"
        }

        for keyframe in snapshot["keyframes"]:
            edit_id = keyframe["edit_id"]
            handle = DraggableEditHandle(
                edit_id,
                self._on_keyframe_moved,
                self._on_keyframe_deleted,
                select_callback=self._on_keyframe_selected,
                fill_color=theme.get("accent_secondary", "#f1c40f"),
                border_color=theme.get("text_main", "#ffffff"),
            )
            handle.setPos(
                self._view.coord_system.to_scene(keyframe["x"], keyframe["y"])
            )
            point_label = (
                "Route point (calculated)"
                if keyframe["point_kind"] == "route"
                else "Timed location"
            )
            tooltip_parts = [f"{point_label} at {format_date(keyframe['t'])}"]
            if edit_id == self._speed_anchor_id:
                tooltip_parts.append("Speed start anchor")
            if edit_id == self._equalization_end_id:
                tooltip_parts.append("Speed end anchor")
            if edit_id in self._equalized_keyframe_ids:
                tooltip_parts.append("Equalized date preview")
            handle.setToolTip(" | ".join(tooltip_parts))
            handle.setEnabled(not previewing and not snapshot["is_awaiting_second_location"])
            handle.set_notifications_enabled(True)
            self._view.graphics_scene.addItem(handle)
            self._keyframe_handles.append(handle)
            if keyframe["point_kind"] == "route":
                handle.setScale(0.72)
            self._style_handle(handle, theme)

        if snapshot["is_awaiting_second_location"]:
            destination_x = snapshot["second_location_x"]
            destination_y = snapshot["second_location_y"]
            if destination_x is not None and destination_y is not None:
                destination = DraggableEditHandle(
                    "guided-second-location",
                    self._on_second_location_moved,
                    lambda _handle_id: None,
                    fill_color=theme.get("accent_primary", "#3498db"),
                    border_color=theme.get("text_main", "#ffffff"),
                )
                destination.setPos(
                    self._view.coord_system.to_scene(destination_x, destination_y)
                )
                self._is_second_location_following_cursor = snapshot[
                    "is_second_location_following_cursor"
                ]
                destination.setToolTip(
                    "Destination marker — move the cursor and click to place it."
                    if self._is_second_location_following_cursor
                    else "Destination marker — drag to adjust before accepting."
                )
                destination.setEnabled(not self._is_second_location_following_cursor)
                if self._is_second_location_following_cursor:
                    self._start_cursor_following()
                destination.set_notifications_enabled(True)
                self._view.graphics_scene.addItem(destination)
                self._second_location_handle = destination

        keyframes = snapshot["keyframes"]
        for start, end in zip(keyframes, keyframes[1:]):
            segment_id = (start["edit_id"], end["edit_id"])
            midpoint_handle = MidpointEditHandle(segment_id, self._on_midpoint_inserted)
            midpoint_handle.setPos(
                self._view.coord_system.to_scene(
                    (start["x"] + end["x"]) / 2.0,
                    (start["y"] + end["y"]) / 2.0,
                )
            )
            midpoint_time = start["t"] + (end["t"] - start["t"]) / 2.0
            midpoint_handle.setToolTip(
                f"Insert Route point at {format_date(midpoint_time)}"
            )
            error = snapshot["midpoint_errors"].get(
                TrajectoryEditSession.midpoint_key(*segment_id)
            )
            if error or previewing:
                midpoint_handle.setEnabled(False)
                midpoint_handle.setCursor(Qt.CursorShape.ForbiddenCursor)
                if error:
                    midpoint_handle.setToolTip(error)
                else:
                    midpoint_handle.setToolTip(
                        "Apply or cancel the equalization preview first."
                    )
            self._view.graphics_scene.addItem(midpoint_handle)
            self._midpoint_handles.append(midpoint_handle)

        self._rebuild_path()

    def select(self, edit_id: str | None) -> None:
        """Update selected-handle styling without rebuilding geometry."""
        self._selected_keyframe_id = edit_id
        theme = ThemeManager().get_theme()
        for handle in self._keyframe_handles:
            self._style_handle(handle, theme)

    def clear(self) -> None:
        """Remove only trajectory edit overlay items from the scene."""
        if self._path_item is not None:
            self._view.graphics_scene.removeItem(self._path_item)
            self._path_item = None
        if self._temporal_path_item is not None:
            self._view.graphics_scene.removeItem(self._temporal_path_item)
            self._temporal_path_item = None
        for item in self._relocation_path_items:
            self._view.graphics_scene.removeItem(item)
        self._relocation_path_items.clear()
        for handle in self._keyframe_handles:
            self._view.graphics_scene.removeItem(handle)
        self._keyframe_handles.clear()
        for midpoint_handle in self._midpoint_handles:
            self._view.graphics_scene.removeItem(midpoint_handle)
        self._midpoint_handles.clear()
        if self._second_location_handle is not None:
            self._view.graphics_scene.removeItem(self._second_location_handle)
        self._second_location_handle = None
        self._is_second_location_following_cursor = False
        self._stop_cursor_following()
        self._view._hide_snap_indicator()
        self._marker_id = None
        self._selected_keyframe_id = None
        self._active_date_edit_id = None
        self._speed_anchor_id = None
        self._equalization_start_id = None
        self._equalization_end_id = None
        self._equalized_keyframe_ids.clear()
        self._route_point_ids.clear()
        self._segment_modes = {}

    def _on_keyframe_selected(self, edit_id: str) -> None:
        self.select(edit_id)
        self._view.trajectory_keyframe_selected.emit(edit_id)

    def _on_keyframe_deleted(self, edit_id: str) -> None:
        self._view.trajectory_keyframe_selected.emit(edit_id)
        self._view.trajectory_delete_selected_requested.emit()

    def _on_keyframe_moved(self, edit_id: str, scene_pos: QPointF) -> None:
        handle = next(
            item for item in self._keyframe_handles if item.handle_id == edit_id
        )
        excluded: set[QGraphicsItem] = {
            *self._keyframe_handles,
            *self._midpoint_handles,
        }
        if self._path_item is not None:
            excluded.add(self._path_item)
        if self._temporal_path_item is not None:
            excluded.add(self._temporal_path_item)
        snap_result = self._view._snapping_manager.snap_point(
            scene_pos,
            self._view.transform(),
            excluded,
        )
        if snap_result.snapped:
            final_position = snap_result.pos
            self._view._show_snap_indicator(final_position, snap_result.snap_type)
        else:
            final_position = snap_to_edit_handles(
                edit_id,
                scene_pos,
                self._keyframe_handles,
                self._view.transform().m11(),
            )
            self._view._hide_snap_indicator()

        x, y = self._view.coord_system.to_normalized(final_position)
        x, y = self._view.coord_system.clamp_normalized(x, y)
        final_position = self._view.coord_system.to_scene(x, y)
        if handle.pos() != final_position:
            handle.set_notifications_enabled(False)
            handle.setPos(final_position)
            handle.set_notifications_enabled(True)

        self._update_midpoint_positions()
        self._rebuild_path()
        self.select(edit_id)
        self._view.trajectory_keyframe_moved.emit(edit_id, x, y)

    def _on_second_location_moved(
        self, _handle_id: str, scene_pos: QPointF
    ) -> None:
        """Snap and forward a guided temporary destination movement."""
        self._update_second_location(scene_pos)

    @property
    def is_second_location_following_cursor(self) -> bool:
        """Whether the temporary destination follows the map cursor."""
        return self._is_second_location_following_cursor

    def follow_second_location_cursor(self, scene_pos: QPointF) -> bool:
        """Move the guided destination with the cursor when placement is active."""
        if not self._is_second_location_following_cursor:
            return False
        self._update_second_location(scene_pos)
        return True

    def place_second_location(self, scene_pos: QPointF) -> bool:
        """Lock the cursor-led destination on a map click, if active."""
        if not self._is_second_location_following_cursor:
            return False
        self._update_second_location(scene_pos)
        self._is_second_location_following_cursor = False
        self._stop_cursor_following()
        self._view.trajectory_second_destination_placed.emit()
        return True

    def _start_cursor_following(self) -> None:
        """Use a precise viewport crosshair while placing the destination."""
        self._view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self._view.viewport().setCursor(Qt.CursorShape.CrossCursor)

    def _stop_cursor_following(self) -> None:
        """Restore normal map panning after guided placement ends."""
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._view.viewport().unsetCursor()

    def _update_second_location(self, scene_pos: QPointF) -> None:
        """Snap, render, and forward the temporary destination position."""
        handle = self._second_location_handle
        if handle is None:
            return
        excluded: set[QGraphicsItem] = {
            *self._keyframe_handles,
            *self._midpoint_handles,
            handle,
        }
        snap_result = self._view._snapping_manager.snap_point(
            scene_pos, self._view.transform(), excluded
        )
        final_position = snap_result.pos if snap_result.snapped else scene_pos
        if snap_result.snapped:
            self._view._show_snap_indicator(final_position, snap_result.snap_type)
        else:
            self._view._hide_snap_indicator()
        x, y = self._view.coord_system.to_normalized(final_position)
        x, y = self._view.coord_system.clamp_normalized(x, y)
        final_position = self._view.coord_system.to_scene(x, y)
        if handle.pos() != final_position:
            handle.set_notifications_enabled(False)
            handle.setPos(final_position)
            handle.set_notifications_enabled(True)
        self._view.trajectory_second_destination_moved.emit(x, y)

    def _on_midpoint_inserted(
        self, segment_id: tuple[str, str], scene_pos: QPointF
    ) -> None:
        excluded: set[QGraphicsItem] = {
            *self._keyframe_handles,
            *self._midpoint_handles,
        }
        if self._path_item is not None:
            excluded.add(self._path_item)
        if self._temporal_path_item is not None:
            excluded.add(self._temporal_path_item)
        snap_result = self._view._snapping_manager.snap_point(
            scene_pos,
            self._view.transform(),
            excluded,
        )
        final_position = snap_result.pos if snap_result.snapped else scene_pos
        x, y = self._view.coord_system.to_normalized(final_position)
        x, y = self._view.coord_system.clamp_normalized(x, y)
        self._view.trajectory_midpoint_insert_requested.emit(
            segment_id[0], segment_id[1], x, y
        )

    def _update_midpoint_positions(self) -> None:
        positions = {
            handle.handle_id: handle.pos() for handle in self._keyframe_handles
        }
        for midpoint in self._midpoint_handles:
            start_id, end_id = midpoint.segment_id
            start = positions[start_id]
            end = positions[end_id]
            midpoint.setPos(
                QPointF(
                    (start.x() + end.x()) / 2.0,
                    (start.y() + end.y()) / 2.0,
                )
            )

    def _rebuild_path(self) -> None:
        for item in self._relocation_path_items:
            self._view.graphics_scene.removeItem(item)
        self._relocation_path_items.clear()
        if len(self._keyframe_handles) < _MINIMUM_PATH_KEYFRAMES:
            if self._path_item is not None:
                self._view.graphics_scene.removeItem(self._path_item)
                self._path_item = None
            if self._temporal_path_item is not None:
                self._view.graphics_scene.removeItem(self._temporal_path_item)
                self._temporal_path_item = None
            return

        path = QPainterPath()
        path.moveTo(self._keyframe_handles[0].pos())
        for start, end in zip(self._keyframe_handles, self._keyframe_handles[1:]):
            pair = (start.handle_id, end.handle_id)
            if self._segment_modes.get(pair) == SEGMENT_MODE_STEP:
                path.moveTo(end.pos())
                self._add_relocation_connector(start.pos(), end.pos())
            else:
                path.lineTo(end.pos())

        if self._path_item is None:
            self._path_item = QGraphicsPathItem()
            theme = ThemeManager().get_theme()
            pen = QPen(QColor(theme.get("warning", "#e67e22")), 3.0)
            pen.setStyle(Qt.PenStyle.DashLine)
            self._path_item.setPen(pen)
            self._path_item.setZValue(MAP_LAYER_Z_UI_OVERLAY - 1)
            self._view.graphics_scene.addItem(self._path_item)
        self._path_item.setPath(path)
        self._rebuild_temporal_path()

    def _add_relocation_connector(self, start: QPointF, end: QPointF) -> None:
        """Render one broken connector for a non-travel relocation."""
        delta = end - start
        path = QPainterPath()
        path.moveTo(start)
        path.lineTo(start + delta * 0.38)
        path.moveTo(start + delta * 0.62)
        path.lineTo(end)
        item = QGraphicsPathItem(path)
        theme = ThemeManager().get_theme()
        pen = QPen(QColor(theme.get("warning", "#e67e22")), 3.0)
        pen.setStyle(Qt.PenStyle.DashDotLine)
        item.setPen(pen)
        item.setToolTip("Relocation — no travel route is implied")
        item.setZValue(MAP_LAYER_Z_UI_OVERLAY - 0.75)
        self._view.graphics_scene.addItem(item)
        self._relocation_path_items.append(item)

    def _rebuild_temporal_path(self) -> None:
        """Highlight segments affected by the active retiming target."""
        if (
            self._equalization_start_id is not None
            and self._equalization_end_id is not None
        ):
            start_index = self._handle_index(self._equalization_start_id)
            end_index = self._handle_index(self._equalization_end_id)
            if start_index is not None and end_index is not None:
                self._set_temporal_range_path(start_index, end_index)
                return
        active_id = self._active_date_edit_id
        if active_id is None:
            if self._temporal_path_item is not None:
                self._view.graphics_scene.removeItem(self._temporal_path_item)
                self._temporal_path_item = None
            return
        active_index = next(
            (
                index
                for index, handle in enumerate(self._keyframe_handles)
                if handle.handle_id == active_id
            ),
            None,
        )
        if active_index is None:
            return

        affected = QPainterPath()
        if active_index > 0:
            affected.moveTo(self._keyframe_handles[active_index - 1].pos())
            affected.lineTo(self._keyframe_handles[active_index].pos())
        if active_index < len(self._keyframe_handles) - 1:
            affected.moveTo(self._keyframe_handles[active_index].pos())
            affected.lineTo(self._keyframe_handles[active_index + 1].pos())

        if self._temporal_path_item is None:
            self._temporal_path_item = QGraphicsPathItem()
            theme = ThemeManager().get_theme()
            pen = QPen(QColor(theme.get("error", "#e74c3c")), 5.0)
            pen.setStyle(Qt.PenStyle.SolidLine)
            self._temporal_path_item.setPen(pen)
            self._temporal_path_item.setZValue(MAP_LAYER_Z_UI_OVERLAY - 0.5)
            self._view.graphics_scene.addItem(self._temporal_path_item)
        self._temporal_path_item.setPath(affected)

    def _set_temporal_range_path(self, start_index: int, end_index: int) -> None:
        """Highlight the complete equalization anchor range."""
        affected = QPainterPath()
        affected.moveTo(self._keyframe_handles[start_index].pos())
        for handle in self._keyframe_handles[start_index + 1 : end_index + 1]:
            affected.lineTo(handle.pos())
        if self._temporal_path_item is None:
            self._temporal_path_item = QGraphicsPathItem()
            theme = ThemeManager().get_theme()
            pen = QPen(QColor(theme.get("success", "#2ecc71")), 5.0)
            pen.setStyle(Qt.PenStyle.SolidLine)
            self._temporal_path_item.setPen(pen)
            self._temporal_path_item.setZValue(MAP_LAYER_Z_UI_OVERLAY - 0.5)
            self._view.graphics_scene.addItem(self._temporal_path_item)
        self._temporal_path_item.setPath(affected)

    def _handle_index(self, edit_id: str) -> int | None:
        return next(
            (
                index
                for index, handle in enumerate(self._keyframe_handles)
                if handle.handle_id == edit_id
            ),
            None,
        )

    def _style_handle(
        self,
        handle: DraggableEditHandle[str],
        theme: dict[str, str],
    ) -> None:
        """Keep selection, anchors, and preview changes visually distinct."""
        edit_id = handle.handle_id
        if edit_id == self._selected_keyframe_id:
            fill = theme.get("error", "#e74c3c")
        elif edit_id in self._equalized_keyframe_ids:
            fill = theme.get("warning", "#e67e22")
        elif edit_id == self._speed_anchor_id:
            fill = theme.get("success", "#2ecc71")
        elif edit_id in self._route_point_ids:
            fill = theme.get("text_muted", "#95a5a6")
        else:
            fill = theme.get("accent_secondary", "#f1c40f")

        is_start = edit_id in {
            self._speed_anchor_id,
            self._equalization_start_id,
        }
        is_end = edit_id == self._equalization_end_id
        if is_start:
            border = theme.get("success", "#2ecc71")
        elif is_end:
            border = theme.get("accent_primary", "#3498db")
        else:
            border = theme.get("text_main", "#ffffff")
        handle.setBrush(QBrush(QColor(fill)))
        handle.setPen(QPen(QColor(border), 3.0 if is_start or is_end else 1.0))
