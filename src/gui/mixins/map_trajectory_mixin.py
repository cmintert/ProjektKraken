"""Trajectory playback and direct-edit presentation for the map."""

import logging
from typing import TYPE_CHECKING, Any, Iterator, Protocol, Tuple

from PySide6.QtCore import QSettings, Slot
from PySide6.QtWidgets import QComboBox, QGraphicsItem

from src.core.trajectory import (
    Keyframe,
    TrajectoryDistanceContext,
    interpolate_position,
)
from src.core.trajectory_edit import TrajectoryEditSnapshot
from src.gui.widgets.map.marker_item import MarkerItem

if TYPE_CHECKING:
    from src.gui.widgets.map.map_graphics_view import MapGraphicsView

logger = logging.getLogger(__name__)


class _CoordinateLabel(Protocol):
    """Text API required from the map widget's lightweight status label."""

    def text(self) -> str: ...

    def setText(self, text: str) -> None: ...


class MapTrajectoryMixin:
    """Mixin providing trajectory playback and direct editing.

    Requires the host class to have:
        - self.view: MapGraphicsView
        - self._active_trajectories: dict[str, list]
        - self._playhead_time: float
        - self._current_time: float
        - self._selected_marker_id: Optional[str]
        - self.jump_to_time_requested: Signal
        - self.map_selector: QComboBox
        - self.coord_label: NoLayoutLabel
        - self._update_mode_indicator(): method
        - self.get_selected_map_id(): method
    """

    if TYPE_CHECKING:
        # Host contract supplied by MapWidget. Keeping it here makes the mixin
        # independently type-checkable without adding runtime base classes.
        view: "MapGraphicsView"
        _active_trajectories: dict[str, list[Any]]
        _trajectory_edit_marker_id: str | None
        _trajectory_edit_keyframes: list[Keyframe]
        _playhead_time: float
        _current_time: float
        _calendar_converter: Any
        _selected_marker_id: str | None
        map_selector: QComboBox
        coord_label: _CoordinateLabel
        trajectory_edit_label: Any
        trajectory_keyframe_label: Any
        trajectory_validation_label: Any
        trajectory_edit_strip: Any
        btn_delete_trajectory_keyframe: Any
        btn_reload_trajectory: Any
        btn_apply_trajectory: Any
        btn_cancel_trajectory: Any
        trajectory_date_panel: Any
        trajectory_date_feedback: Any
        trajectory_date_input: Any
        btn_trajectory_date_previous: Any
        btn_trajectory_date_next: Any
        btn_edit_trajectory_date: Any
        btn_trajectory_date_use_playhead: Any
        btn_finish_trajectory_date: Any
        btn_cancel_trajectory_date: Any
        trajectory_speed_panel: Any
        trajectory_speed_feedback: Any
        trajectory_speed_changes: Any
        btn_set_trajectory_speed_anchor: Any
        btn_equalize_trajectory_speed: Any
        btn_equalize_whole_trajectory: Any
        btn_clear_trajectory_speed_anchor: Any
        btn_apply_speed_equalization: Any
        btn_cancel_speed_equalization: Any

        def _update_mode_indicator(self) -> None:
            ...

        def get_selected_map_id(self) -> str | None:
            ...

        def _update_trajectory_edit_action(self) -> None:
            ...

    def set_trajectories(self, trajectories: list) -> None:
        """Sets the active trajectories for the current map.

        Args:
            trajectories: JSON-safe trajectory snapshot dictionaries.

        """
        self._active_trajectories.clear()
        marker_counts: dict[str, int] = {}
        for trajectory in trajectories:
            marker_id = str(trajectory["marker_id"])
            marker_counts[marker_id] = marker_counts.get(marker_id, 0) + 1

        ambiguous_marker_ids = {
            marker_id
            for marker_id, count in marker_counts.items()
            if count > 1
        }
        for marker_id in sorted(ambiguous_marker_ids):
            logger.warning(
                "Ignoring ambiguous duplicate trajectories for marker %s",
                marker_id,
            )

        count = 0
        from src.core.trajectory import Keyframe

        for trajectory in trajectories:
            marker_id = str(trajectory["marker_id"])
            if marker_id in ambiguous_marker_ids:
                continue
            keyframes = [
                Keyframe(
                    t=float(keyframe["t"]),
                    x=float(keyframe["x"]),
                    y=float(keyframe["y"]),
                )
                for keyframe in trajectory["keyframes"]
            ]
            self._active_trajectories[marker_id] = keyframes
            count += 1

        self.view.set_trajectory_marker_ids(set(self._active_trajectories))

        # Detect first trajectory use for animation
        settings = QSettings()
        is_first_trajectories = not settings.value(
            "map/trajectories_initialized", False, type=bool
        )
        logger.debug(
            f"set_trajectories: count={count}, is_first={is_first_trajectories}"
        )
        if is_first_trajectories and count > 0:
            logger.info(
                "First trajectory display detected - enabling pulsing animation"
            )
            settings.setValue("map/trajectories_initialized", True)
            self.view.trigger_first_use_animation = True

        logger.debug(f"Loaded {count} temporal trajectories for map")
        # Force an update immediately so markers jump to correct spot for current time
        self._update_trajectory_positions()
        self._update_mode_indicator()

        # Update visualization if selection exists
        if self._selected_marker_id:
            self._update_trajectory_visualization(self._selected_marker_id)

        # Update marker indicators
        self._update_marker_indicators()
        self._update_trajectory_edit_action()

    def show_trajectory_edit(
        self,
        snapshot: TrajectoryEditSnapshot,
        *,
        pending: bool = False,
        rebuild_overlay: bool = True,
    ) -> None:
        """Render an isolated trajectory edit-session snapshot."""
        marker_id = snapshot["marker_id"]
        self._trajectory_edit_marker_id = marker_id
        self._trajectory_edit_keyframes = [
            Keyframe(
                t=float(keyframe["t"]),
                x=float(keyframe["x"]),
                y=float(keyframe["y"]),
            )
            for keyframe in snapshot["keyframes"]
        ]
        marker = self.view.markers.get(marker_id)
        if marker is not None:
            marker.setFlag(
                QGraphicsItem.GraphicsItemFlag.ItemIsMovable,
                False,
            )
        self.view.clear_trajectory()
        if rebuild_overlay:
            self.view.trajectory_edit_overlay.show(snapshot)
        else:
            self.view.trajectory_edit_overlay.select(
                snapshot["selected_keyframe_id"]
            )

        count = snapshot["keyframe_count"]
        self.trajectory_edit_label.setText(
            f"Edit Trajectory | {count} keyframe{'s' if count != 1 else ''}"
        )
        selected_index = snapshot["selected_keyframe_index"]
        is_equalization_previewing = snapshot["is_equalization_previewing"]
        if selected_index is None:
            self.trajectory_keyframe_label.setText("Select a keyframe")
            self.trajectory_date_panel.hide()
        else:
            keyframe = snapshot["keyframes"][selected_index]
            self.trajectory_keyframe_label.setText(
                f"Keyframe {selected_index + 1} of {count} | "
                f"{self._format_trajectory_date(keyframe['t'])}"
            )
            self.trajectory_date_input.set_value(keyframe["t"])
            is_date_editing = snapshot["is_date_editing"]
            if is_date_editing:
                original = snapshot["date_edit_original_t"]
                proposed = snapshot["date_edit_proposed_t"]
                delta = snapshot["date_edit_delta"]
                feedback = "Editing keyframe date"
                if delta is not None:
                    feedback = (
                        "Original: "
                        f"{self._format_trajectory_date(original)} | Proposed: "
                        f"{self._format_trajectory_date(proposed)} | Change: "
                        f"{delta:+g} days"
                    )
                self.trajectory_date_feedback.setText(feedback)
            else:
                self.trajectory_date_feedback.setText(
                    f"Date: {self._format_trajectory_date(keyframe['t'])}"
                )
            self.trajectory_date_input.setEnabled(is_date_editing and not pending)
            self.trajectory_date_input.setVisible(is_date_editing)
            self.btn_trajectory_date_previous.setEnabled(
                is_date_editing and not pending
            )
            self.btn_trajectory_date_previous.setVisible(is_date_editing)
            self.btn_trajectory_date_next.setEnabled(
                is_date_editing and not pending
            )
            self.btn_trajectory_date_next.setVisible(is_date_editing)
            self.btn_edit_trajectory_date.setVisible(not is_date_editing)
            self.btn_edit_trajectory_date.setEnabled(
                not pending and not is_equalization_previewing
            )
            self.btn_trajectory_date_use_playhead.setVisible(True)
            self.btn_trajectory_date_use_playhead.setEnabled(
                not pending and not is_equalization_previewing
            )
            self.btn_finish_trajectory_date.setVisible(is_date_editing)
            self.btn_finish_trajectory_date.setEnabled(not pending)
            self.btn_cancel_trajectory_date.setVisible(is_date_editing)
            self.btn_cancel_trajectory_date.setEnabled(not pending)
            self.trajectory_date_panel.show()

        self._show_trajectory_speed_controls(snapshot, pending=pending)

        messages = list(snapshot["validation_errors"])
        if snapshot["is_conflicted"]:
            messages.insert(0, "Trajectory changed externally; Apply is blocked.")
        if is_equalization_previewing:
            messages.insert(0, "Apply or cancel the equalization preview.")
        self.trajectory_validation_label.setText(" ".join(messages))
        self.btn_delete_trajectory_keyframe.setEnabled(
            snapshot["selected_keyframe_id"] is not None
            and not snapshot["is_date_editing"]
            and not is_equalization_previewing
            and not pending
        )
        self.btn_reload_trajectory.setVisible(snapshot["is_conflicted"])
        self.btn_apply_trajectory.setEnabled(snapshot["can_apply"] and not pending)
        self.btn_cancel_trajectory.setEnabled(not pending)
        self.trajectory_edit_strip.show()
        self._update_trajectory_positions()
        self._update_trajectory_edit_action()

    def clear_trajectory_edit(self) -> None:
        """Remove the working overlay and restore authoritative playback."""
        marker_id = self._trajectory_edit_marker_id
        self.view.trajectory_edit_overlay.clear()
        if marker_id is not None:
            marker = self.view.markers.get(marker_id)
            if marker is not None:
                marker.setFlag(
                    QGraphicsItem.GraphicsItemFlag.ItemIsMovable,
                    not marker.has_keyframes,
                )
        self._trajectory_edit_marker_id = None
        self._trajectory_edit_keyframes = []
        self.trajectory_edit_strip.hide()
        self.trajectory_date_panel.hide()
        self.trajectory_speed_panel.hide()
        self._update_trajectory_positions()
        if marker_id == self._selected_marker_id and marker_id is not None:
            self._update_trajectory_visualization(marker_id)
        self._update_trajectory_edit_action()

    def _format_trajectory_date(self, value: float | None) -> str:
        """Format a lore date through the active calendar when available."""
        if value is None:
            return "—"
        if self._calendar_converter is not None:
            try:
                return str(self._calendar_converter.format_date(value))
            except Exception:
                logger.warning("Could not format trajectory date %s", value)
        return f"T {value:g}"

    def get_trajectory_distance_context(self) -> TrajectoryDistanceContext:
        """Return calibrated or aspect-corrected relative map dimensions."""
        aspect_ratio = 1.0
        pixmap_item = getattr(self.view, "pixmap_item", None)
        if pixmap_item is not None:
            rect = pixmap_item.boundingRect()
        else:
            rect = self.view.sceneRect()
        if rect.width() > 0.0 and rect.height() > 0.0:
            aspect_ratio = rect.width() / rect.height()

        width_meters = float(getattr(self.view, "map_width_meters", 0.0))
        if width_meters > 0.0:
            return TrajectoryDistanceContext(
                width=width_meters,
                height=width_meters / aspect_ratio,
                unit="m",
            )
        return TrajectoryDistanceContext(
            width=aspect_ratio,
            height=1.0,
        )

    def _show_trajectory_speed_controls(
        self,
        snapshot: TrajectoryEditSnapshot,
        *,
        pending: bool,
    ) -> None:
        """Render the compact start-anchor and equalization preview workflow."""
        previewing = snapshot["is_equalization_previewing"]
        has_anchor = snapshot["speed_anchor_id"] is not None
        has_selection = snapshot["selected_keyframe_id"] is not None
        is_date_editing = snapshot["is_date_editing"]

        self.btn_set_trajectory_speed_anchor.setVisible(not previewing)
        self.btn_set_trajectory_speed_anchor.setEnabled(
            has_selection and not is_date_editing and not pending
        )
        self.btn_equalize_trajectory_speed.setVisible(not previewing and has_anchor)
        self.btn_equalize_trajectory_speed.setEnabled(
            snapshot["can_equalize_to_selected"] and not pending
        )
        self.btn_equalize_whole_trajectory.setVisible(not previewing)
        self.btn_equalize_whole_trajectory.setEnabled(
            snapshot["can_equalize_whole"] and not pending
        )
        self.btn_clear_trajectory_speed_anchor.setVisible(
            not previewing and has_anchor
        )
        self.btn_clear_trajectory_speed_anchor.setEnabled(not pending)
        self.btn_apply_speed_equalization.setVisible(previewing)
        self.btn_apply_speed_equalization.setEnabled(not pending)
        self.btn_cancel_speed_equalization.setVisible(previewing)
        self.btn_cancel_speed_equalization.setEnabled(not pending)

        if previewing:
            changed_count = len(snapshot["equalization_changes"])
            distance = self._format_equalization_distance(
                snapshot["equalization_total_distance"],
                snapshot["equalization_distance_unit"],
            )
            speed = self._format_equalization_speed(
                snapshot["equalization_average_speed"],
                snapshot["equalization_distance_unit"],
            )
            self.trajectory_speed_feedback.setText(
                f"Equalize Speed preview | {changed_count} changed | "
                f"Distance: {distance} | Average: {speed}"
            )
            all_changes = " | ".join(
                f"K{change['keyframe_number']}: "
                f"{self._format_trajectory_date(change['original_t'])} → "
                f"{self._format_trajectory_date(change['proposed_t'])}"
                for change in snapshot["equalization_changes"]
            )
            visible_changes = " | ".join(all_changes.split(" | ")[:4])
            if changed_count > 4:
                visible_changes += f" | … {changed_count - 4} more"
            self.trajectory_speed_changes.setText(visible_changes)
            self.trajectory_speed_changes.setToolTip(all_changes)
            self.trajectory_speed_changes.show()
        else:
            anchor_index = snapshot["speed_anchor_index"]
            if anchor_index is None:
                feedback = "Equalize dates by cumulative path distance."
            else:
                feedback = (
                    f"Start anchor: Keyframe {anchor_index + 1}. "
                    "Select a later keyframe."
                )
            self.trajectory_speed_feedback.setText(feedback)
            self.trajectory_speed_changes.clear()
            self.trajectory_speed_changes.setToolTip("")
            self.trajectory_speed_changes.hide()

        self.trajectory_speed_panel.setVisible(
            snapshot["keyframe_count"] >= 3 or previewing
        )

    @staticmethod
    def _format_equalization_distance(value: float | None, unit: str | None) -> str:
        if value is None:
            return "—"
        if unit == "m":
            return f"{value / 1000.0:.2f} km" if value >= 1000.0 else f"{value:.1f} m"
        return f"{value:.3g} relative units"

    @staticmethod
    def _format_equalization_speed(value: float | None, unit: str | None) -> str:
        if value is None:
            return "—"
        if unit == "m":
            return (
                f"{value / 1000.0:.2f} km/day"
                if value >= 1000.0
                else f"{value:.1f} m/day"
            )
        return f"{value:.3g} relative units/day"

    def _update_marker_indicators(self) -> None:
        """Updates the has_keyframes state for all markers."""
        if not self.view.graphics_scene:
            return

        for item in self.view.graphics_scene.items():
            if isinstance(item, MarkerItem):
                has_traj = item.marker_id in self._active_trajectories
                item.set_has_keyframes(has_traj)

    def _iter_trajectory_positions(self) -> Iterator[Tuple[str, float, float]]:
        """Yield (marker_id, x, y) for markers with trajectories at current time."""
        for marker_id, keyframes in self._active_trajectories.items():
            if marker_id == self._trajectory_edit_marker_id:
                keyframes = self._trajectory_edit_keyframes
            position = interpolate_position(keyframes, self._playhead_time)
            if position:
                x, y = position
                yield marker_id, x, y

    def _update_trajectory_positions(self) -> None:
        """Update all trajectory markers for the current playhead time."""
        for marker_id, x, y in self._iter_trajectory_positions():
            self.view.update_marker_position(marker_id, x, y)

    @Slot(float)
    def on_time_changed(self, time: float) -> None:
        """Receives playhead time updates from the Timeline.

        Updates the internal time state, refreshes the status display,
        and updates any trajectory-based markers.

        Args:
            time: Current playhead time in lore_date units.

        """
        # Round to 4 decimal places to prevent float precision drift
        # during rapid playhead scrubbing
        time = round(time, 4)

        self._playhead_time = time
        self._update_time_display()

        self._update_trajectory_positions()

        # Update marker visuals (dull/vivid) based on new time
        self.view.update_markers_temporal_state(self._playhead_time, self._current_time)

    @Slot(float)
    def on_current_time_changed(self, time: float) -> None:
        """Receives current time ("Now") updates from the Timeline.

        This represents the story's current moment, distinct from the playhead.

        Args:
            time: Current time in lore_date units.

        """
        self._current_time = time
        self._update_time_display()

        # Update marker visuals (dull/vivid) based on new 'Now'
        self.view.update_markers_temporal_state(self._playhead_time, self._current_time)

    def _update_time_display(self) -> None:
        """Updates the coord_label to include playhead and current time."""
        # Get existing coordinate text or default
        current_text = self.coord_label.text()

        # Remove any existing time suffix
        if " | T:" in current_text:
            current_text = current_text.split(" | T:")[0]

        # Append time (Playhead and Now)
        time_str = f"T: {self._playhead_time:.1f} | Now: {self._current_time:.1f}"
        self.coord_label.setText(f"{current_text} | {time_str}")

    @Slot(str, str)
    def _on_marker_clicked_internal(self, marker_id: str, object_type: str) -> None:
        """Internal handler for marker click to update visualization."""
        self._selected_marker_id = marker_id
        self._update_trajectory_visualization(marker_id)

    def _update_trajectory_visualization(self, marker_id: str) -> None:
        """Updates the view to show the trajectory for the given marker."""
        if self._trajectory_edit_marker_id is not None:
            return
        keyframes = self._active_trajectories.get(marker_id, [])
        if keyframes:
            self.view.show_trajectory(marker_id, keyframes)
        else:
            self.view.clear_trajectory()
