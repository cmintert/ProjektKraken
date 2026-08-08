"""Interactive spatial overlay for one trajectory edit session."""

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem

from src.app.constants import MAP_LAYER_Z_UI_OVERLAY
from src.core.theme_manager import ThemeManager
from src.core.trajectory_edit import TrajectoryEditSession, TrajectoryEditSnapshot
from src.gui.widgets.map.edit_handles import (
    DraggableEditHandle,
    MidpointEditHandle,
    snap_to_edit_handles,
)

if TYPE_CHECKING:
    from src.gui.widgets.map.map_graphics_view import MapGraphicsView


class TrajectoryEditOverlay:
    """Render and update only the active trajectory's editable geometry."""

    def __init__(self, view: "MapGraphicsView") -> None:
        self._view = view
        self._marker_id: str | None = None
        self._selected_keyframe_id: str | None = None
        self._active_date_edit_id: str | None = None
        self._path_item: QGraphicsPathItem | None = None
        self._temporal_path_item: QGraphicsPathItem | None = None
        self._keyframe_handles: list[DraggableEditHandle[str]] = []
        self._midpoint_handles: list[
            MidpointEditHandle[tuple[str, str]]
        ] = []

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

    def show(self, snapshot: TrajectoryEditSnapshot) -> None:
        """Rebuild the active overlay from serialized session state."""
        self.clear()
        self._marker_id = snapshot["marker_id"]
        theme = ThemeManager().get_theme()
        selected_id = snapshot["selected_keyframe_id"]
        self._selected_keyframe_id = selected_id
        self._active_date_edit_id = snapshot["active_date_edit_id"]

        for keyframe in snapshot["keyframes"]:
            edit_id = keyframe["edit_id"]
            selected = edit_id == selected_id
            handle = DraggableEditHandle(
                edit_id,
                self._on_keyframe_moved,
                self._on_keyframe_deleted,
                select_callback=self._on_keyframe_selected,
                fill_color=theme.get(
                    "error" if selected else "accent_secondary",
                    "#e74c3c" if selected else "#f1c40f",
                ),
                border_color=theme.get("text_main", "#ffffff"),
            )
            handle.setPos(
                self._view.coord_system.to_scene(keyframe["x"], keyframe["y"])
            )
            handle.setToolTip(f"Keyframe at {keyframe['t']:g}")
            handle.set_notifications_enabled(True)
            self._view.graphics_scene.addItem(handle)
            self._keyframe_handles.append(handle)

        keyframes = snapshot["keyframes"]
        for start, end in zip(keyframes, keyframes[1:]):
            segment_id = (start["edit_id"], end["edit_id"])
            midpoint_handle = MidpointEditHandle(
                segment_id, self._on_midpoint_inserted
            )
            midpoint_handle.setPos(
                self._view.coord_system.to_scene(
                    (start["x"] + end["x"]) / 2.0,
                    (start["y"] + end["y"]) / 2.0,
                )
            )
            midpoint_time = start["t"] + (end["t"] - start["t"]) / 2.0
            midpoint_handle.setToolTip(
                f"Insert keyframe at {midpoint_time:g}"
            )
            error = snapshot["midpoint_errors"].get(
                TrajectoryEditSession.midpoint_key(*segment_id)
            )
            if error:
                midpoint_handle.setEnabled(False)
                midpoint_handle.setCursor(Qt.CursorShape.ForbiddenCursor)
                midpoint_handle.setToolTip(error)
            self._view.graphics_scene.addItem(midpoint_handle)
            self._midpoint_handles.append(midpoint_handle)

        self._rebuild_path()

    def select(self, edit_id: str | None) -> None:
        """Update selected-handle styling without rebuilding geometry."""
        self._selected_keyframe_id = edit_id
        theme = ThemeManager().get_theme()
        for handle in self._keyframe_handles:
            selected = handle.handle_id == edit_id
            handle.setBrush(
                QBrush(
                    QColor(
                    theme.get(
                        "error" if selected else "accent_secondary",
                        "#e74c3c" if selected else "#f1c40f",
                    )
                    )
                )
            )

    def clear(self) -> None:
        """Remove only trajectory edit overlay items from the scene."""
        if self._path_item is not None:
            self._view.graphics_scene.removeItem(self._path_item)
            self._path_item = None
        if self._temporal_path_item is not None:
            self._view.graphics_scene.removeItem(self._temporal_path_item)
            self._temporal_path_item = None
        for handle in self._keyframe_handles:
            self._view.graphics_scene.removeItem(handle)
        self._keyframe_handles.clear()
        for midpoint_handle in self._midpoint_handles:
            self._view.graphics_scene.removeItem(midpoint_handle)
        self._midpoint_handles.clear()
        self._view._hide_snap_indicator()
        self._marker_id = None
        self._selected_keyframe_id = None
        self._active_date_edit_id = None

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
            self._view._show_snap_indicator(
                final_position, snap_result.snap_type
            )
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
        if len(self._keyframe_handles) < 2:
            if self._path_item is not None:
                self._view.graphics_scene.removeItem(self._path_item)
                self._path_item = None
            if self._temporal_path_item is not None:
                self._view.graphics_scene.removeItem(self._temporal_path_item)
                self._temporal_path_item = None
            return

        path = QPainterPath()
        path.moveTo(self._keyframe_handles[0].pos())
        for handle in self._keyframe_handles[1:]:
            path.lineTo(handle.pos())

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

    def _rebuild_temporal_path(self) -> None:
        """Highlight segments affected by the active retiming target."""
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
