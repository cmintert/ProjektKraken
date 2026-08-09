"""Application-level coordination for direct spatial trajectory editing."""

import copy
import logging
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import Q_ARG, QObject, Qt, Signal, Slot

from src.app.qt_invocation import invoke_queued
from src.commands.base_command import CommandResult
from src.commands.trajectory_commands import UpdateTrajectoryCommand
from src.core.trajectory import (
    SEGMENT_MODE_LINEAR,
    SEGMENT_MODE_STEP,
    Keyframe,
    SegmentKey,
    SegmentMode,
    TrajectoryPointKind,
    interpolate_position,
)
from src.core.trajectory_edit import TrajectoryEditSession

if TYPE_CHECKING:
    from src.app.main_window import MainWindow
    from src.services.repositories.trajectory_repository import TrajectorySnapshot

logger = logging.getLogger(__name__)


class TrajectoryEditCoordinator(QObject):
    """Own the single active trajectory working copy and persistence boundary."""

    command_requested = Signal(object)

    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__(main_window)
        self._window = main_window
        self._session: TrajectoryEditSession | None = None
        self._authoritative_by_map: dict[str, list[dict[str, Any]]] = {}
        self._latest_deferred: list[dict[str, Any]] | None = None
        self._before_snapshot: dict[str, Any] | None = None
        self._active_record_at_start: dict[str, Any] | None = None
        self._pending_command_id: str | None = None
        self._expected_after_snapshot: dict[str, Any] | None = None
        self._bound = False

    @property
    def is_active(self) -> bool:
        """Whether a direct trajectory edit session is active."""
        return self._session is not None

    @property
    def is_date_editing(self) -> bool:
        """Whether the active session is retiming one selected keyframe."""
        return (
            self._session is not None and self._session.active_date_edit_id is not None
        )

    @property
    def is_equalization_previewing(self) -> bool:
        """Whether speed redistribution awaits preview confirmation."""
        return self._session is not None and self._session.is_equalization_previewing

    def bind_ui(self) -> None:
        """Connect map intents after the MainWindow widget skeleton exists."""
        if self._bound:
            return
        widget = self._window.map_widget
        widget.map_selected.connect(self.on_map_selected)
        widget.trajectory_edit_requested.connect(self.start_edit)
        widget.trajectory_keyframe_selected.connect(self.select_keyframe)
        widget.trajectory_keyframe_moved.connect(self.move_keyframe)
        widget.trajectory_midpoint_insert_requested.connect(self.insert_midpoint)
        widget.trajectory_add_location_requested.connect(self.add_location_at_playhead)
        widget.trajectory_delete_selected_requested.connect(
            self.delete_selected_keyframe
        )
        widget.trajectory_apply_requested.connect(self.apply)
        widget.trajectory_cancel_requested.connect(self.cancel)
        widget.trajectory_discard_reload_requested.connect(self.discard_and_reload)
        widget.trajectory_date_edit_requested.connect(self.begin_date_edit)
        widget.trajectory_date_use_playhead_requested.connect(
            self.set_selected_date_from_playhead
        )
        widget.trajectory_date_value_changed.connect(self.set_date_value)
        widget.trajectory_date_step_requested.connect(self.step_date)
        widget.trajectory_date_edit_done_requested.connect(self.finish_date_edit)
        widget.trajectory_date_edit_cancel_requested.connect(self.cancel_date_edit)
        widget.trajectory_shift_later_requested.connect(self.shift_later)
        widget.trajectory_arrival_mode_changed.connect(self.set_arrival_mode)
        widget.trajectory_speed_anchor_requested.connect(self.set_speed_anchor)
        widget.trajectory_speed_anchor_clear_requested.connect(self.clear_speed_anchor)
        widget.trajectory_speed_equalize_requested.connect(
            self.preview_speed_equalization
        )
        widget.trajectory_speed_equalize_whole_requested.connect(
            self.preview_whole_speed_equalization
        )
        widget.trajectory_speed_equalization_apply_requested.connect(
            self.confirm_speed_equalization
        )
        widget.trajectory_speed_equalization_cancel_requested.connect(
            self.cancel_speed_equalization
        )
        widget.trajectory_make_route_point_requested.connect(
            self.make_selected_route_point
        )
        widget.trajectory_make_timed_location_requested.connect(
            self.make_selected_timed_location
        )
        widget.trajectory_make_intermediate_automatic_requested.connect(
            self.make_intermediate_points_automatic
        )
        self.command_requested.connect(self._window.command_requested.emit)
        self._window.worker.command_finished.connect(
            self.on_command_finished,
            Qt.ConnectionType.QueuedConnection,
        )
        self._bound = True

    @Slot(str)
    def on_map_selected(self, map_id: str) -> None:
        """Discard an active edit when the user changes map context."""
        if self._session is not None and self._session.map_id != map_id:
            self.cancel()

    @Slot(str, list)
    def on_trajectories_ready(
        self, map_id: str, trajectories: list[dict[str, Any]]
    ) -> None:
        """Gate authoritative reloads so they cannot replace active work."""
        incoming = copy.deepcopy(trajectories)
        self._authoritative_by_map[map_id] = incoming
        session = self._session
        if session is None or session.map_id != map_id:
            self._window.map_handler.on_trajectories_ready(map_id, incoming)
            return

        self._latest_deferred = incoming
        matching = [
            row for row in incoming if row.get("marker_id") == session.marker_id
        ]
        incoming_row = matching[0].get("row_snapshot") if len(matching) == 1 else None

        if self._pending_command_id is not None:
            if len(matching) <= 1 and incoming_row == self._expected_after_snapshot:
                self._finish_session(incoming)
            else:
                self._pending_command_id = None
                self._expected_after_snapshot = None
                session.mark_conflicted()
                self._render()
            return

        authoritative_matches = (
            len(matching) == 0 and self._before_snapshot is None
        ) or (len(matching) == 1 and incoming_row == self._before_snapshot)
        if not authoritative_matches:
            session.mark_conflicted()

        # Apply harmless changes to unrelated trajectories, retaining the
        # session-start row for the active trajectory under the edit overlay.
        merged = [row for row in incoming if row.get("marker_id") != session.marker_id]
        if self._active_record_at_start is not None:
            merged.append(copy.deepcopy(self._active_record_at_start))
        self._window.map_handler.on_trajectories_ready(map_id, merged)
        self._render()

    @Slot(str)
    def start_edit(self, marker_id: str) -> None:
        """Start editing one unambiguous trajectory on the selected map."""
        if self._session is not None:
            if self._session.marker_id == marker_id:
                return
            self._show_status("Finish the current trajectory edit first.")
            return
        map_id = self._window.map_widget.get_selected_map_id()
        if map_id is None:
            return
        records = [
            row
            for row in self._authoritative_by_map.get(map_id, [])
            if row.get("marker_id") == marker_id
        ]
        if len(records) > 1:
            self._show_status(
                "This marker has multiple trajectory rows and cannot be edited."
            )
            return
        if not records:
            position = self._window.map_widget.get_marker_base_position(marker_id)
            if position is None:
                self._show_status("The selected marker has no usable map position.")
                return
            playhead = self._window.timeline.get_playhead_time()
            seed = Keyframe(
                t=playhead,
                x=position[0],
                y=position[1],
            )
            self._session = TrajectoryEditSession.create(
                map_id=map_id,
                marker_id=marker_id,
                trajectory_id=None,
                keyframes=[seed],
                is_new=True,
                distance_context=(
                    self._window.map_widget.get_trajectory_distance_context()
                ),
            )
            self._before_snapshot = None
            self._active_record_at_start = None
            self._latest_deferred = None
            self._window.map_widget.show_trajectory_edit(self._session.to_snapshot())
            return

        record = records[0]
        keyframes = [
            Keyframe(
                t=float(item["t"]),
                x=float(item["x"]),
                y=float(item["y"]),
                keyframe_id=str(item.get("id") or f"legacy-{index}"),
                point_kind=cast("TrajectoryPointKind", str(item["point_kind"])),
            )
            for index, item in enumerate(record.get("keyframes", []))
        ]
        segment_modes: dict[SegmentKey, SegmentMode] = {}
        for item in record.get("segment_modes", []):
            if not isinstance(item, dict):
                continue
            mode = item.get("mode")
            if mode not in {SEGMENT_MODE_LINEAR, SEGMENT_MODE_STEP}:
                continue
            segment_modes[(str(item["from_id"]), str(item["to_id"]))] = cast(
                "SegmentMode", mode
            )
        self._session = TrajectoryEditSession.create(
            map_id=map_id,
            marker_id=marker_id,
            trajectory_id=str(record["trajectory_id"]),
            keyframes=keyframes,
            segment_modes=segment_modes,
            properties=cast(dict[str, Any], record.get("properties", {})),
            distance_context=(
                self._window.map_widget.get_trajectory_distance_context()
            ),
        )
        self._before_snapshot = copy.deepcopy(record.get("row_snapshot"))
        self._active_record_at_start = copy.deepcopy(record)
        self._latest_deferred = None
        self._window.map_widget.show_trajectory_edit(self._session.to_snapshot())

    @Slot(str)
    def select_keyframe(self, edit_id: str) -> None:
        """Select one session-local keyframe identity."""
        if self._session is None:
            return
        if self._session.is_equalization_previewing:
            return
        try:
            if (
                self._session.active_date_edit_id is not None
                and self._session.active_date_edit_id != edit_id
            ):
                self._session.finish_date_edit()
            self._session.select_keyframe(edit_id)
        except ValueError as exc:
            self._show_status(str(exc))
            return
        self._render(rebuild_overlay=False)

    @Slot(str)
    def begin_date_edit(self, edit_id: str) -> None:
        """Start retiming a keyframe without changing the timeline."""
        session = self._session
        if session is None or self._pending_command_id is not None:
            return
        try:
            if (
                session.active_date_edit_id is not None
                and session.active_date_edit_id != edit_id
            ):
                session.finish_date_edit()
            session.begin_date_edit(edit_id)
        except ValueError as exc:
            self._show_date_error(str(exc))
            return
        self._render()

    @Slot(float)
    def set_date_value(self, proposed_time: float) -> None:
        """Update the active date proposal without moving the timeline."""
        session = self._session
        if (
            session is None
            or session.active_date_edit_id is None
            or self._pending_command_id is not None
        ):
            return
        try:
            session.update_active_date(proposed_time)
        except ValueError as exc:
            self._show_date_error(str(exc))
            return
        self._render()

    @Slot()
    def set_selected_date_from_playhead(self) -> None:
        """Set the selected keyframe date without moving the playhead."""
        session = self._session
        if (
            session is None
            or session.selected_keyframe_id is None
            or session.is_equalization_previewing
            or self._pending_command_id is not None
        ):
            return
        playhead = self._window.timeline.get_playhead_time()
        try:
            if session.active_date_edit_id is not None:
                session.update_active_date(playhead)
            else:
                session.set_keyframe_time(
                    session.selected_keyframe_id,
                    playhead,
                )
        except ValueError as exc:
            self._show_date_error(str(exc))
            return
        self._render()

    @Slot(float)
    def step_date(self, delta_days: float) -> None:
        """Move the active proposed date by a small lore-day increment."""
        session = self._session
        if session is None or session.active_date_edit_id is None:
            return
        current = session.active_date_value
        if current is not None:
            self.set_date_value(current + delta_days)

    @Slot()
    def finish_date_edit(self) -> None:
        """Keep the proposed date and leave the temporal sub-operation."""
        if self._session is None:
            return
        if self._session.finish_date_edit():
            self._render()

    @Slot()
    def cancel_date_edit(self) -> None:
        """Restore only the current keyframe's prior working date."""
        if self._session is None or self._pending_command_id is not None:
            return
        if self._session.cancel_date_edit():
            self._render()

    @Slot()
    def shift_later(self) -> None:
        """Apply the active date delta to all later locations."""
        if self._session is None or self._pending_command_id is not None:
            return
        try:
            self._session.shift_later_by_active_delta()
        except ValueError as exc:
            self._show_date_error(str(exc))
            return
        self._render()

    @Slot(str)
    def set_arrival_mode(self, mode: str) -> None:
        """Set the selected location's arrival behavior."""
        session = self._session
        if (
            session is None
            or session.selected_keyframe_id is None
            or self._pending_command_id is not None
        ):
            return
        try:
            session.set_arrival_mode(
                session.selected_keyframe_id, cast("SegmentMode", mode)
            )
        except ValueError as exc:
            self._show_status(str(exc))
            return
        self._render()

    @Slot(str)
    def set_speed_anchor(self, edit_id: str) -> None:
        """Set the selected keyframe as the explicit equalization start."""
        if self._session is None or self._pending_command_id is not None:
            return
        try:
            self._session.set_speed_anchor(edit_id)
        except ValueError as exc:
            self._show_status(str(exc))
            return
        self._render()

    @Slot()
    def clear_speed_anchor(self) -> None:
        """Clear the pending start anchor without changing working dates."""
        if self._session is None or self._pending_command_id is not None:
            return
        try:
            self._session.clear_speed_anchor()
        except ValueError as exc:
            self._show_status(str(exc))
            return
        self._render()

    @Slot(str)
    def preview_speed_equalization(self, end_id: str) -> None:
        """Preview distance-weighted dates between explicit anchors."""
        if self._session is None or self._pending_command_id is not None:
            return
        try:
            self._session.preview_speed_equalization(
                end_id,
                self._window.map_widget.get_trajectory_distance_context(),
            )
        except ValueError as exc:
            self._show_status(str(exc))
            return
        self._render()

    @Slot()
    def preview_whole_speed_equalization(self) -> None:
        """Preview distance-weighted dates across the complete trajectory."""
        if self._session is None or self._pending_command_id is not None:
            return
        try:
            self._session.preview_whole_speed_equalization(
                self._window.map_widget.get_trajectory_distance_context()
            )
        except ValueError as exc:
            self._show_status(str(exc))
            return
        self._render()

    @Slot()
    def confirm_speed_equalization(self) -> None:
        """Keep previewed dates in the working copy until trajectory Apply."""
        if self._session is None or self._pending_command_id is not None:
            return
        if self._session.confirm_speed_equalization():
            self._render()

    @Slot()
    def cancel_speed_equalization(self) -> None:
        """Restore the dates captured before the equalization preview."""
        if self._session is None or self._pending_command_id is not None:
            return
        if self._session.cancel_speed_equalization():
            self._render()

    @Slot()
    def make_selected_route_point(self) -> None:
        """Convert the selected interior timed location to a route point."""
        if self._session is None or self._pending_command_id is not None:
            return
        try:
            self._session.make_selected_route_point()
        except ValueError as exc:
            self._show_status(str(exc))
            return
        self._render()

    @Slot()
    def make_selected_timed_location(self) -> None:
        """Promote the selected route point to a dated location."""
        if self._session is None or self._pending_command_id is not None:
            return
        try:
            self._session.make_selected_timed_location()
        except ValueError as exc:
            self._show_status(str(exc))
            return
        self._render()

    @Slot(str)
    def make_intermediate_points_automatic(self, end_id: str) -> None:
        """Convert a selected timed range's interior points to route points."""
        if self._session is None or self._pending_command_id is not None:
            return
        try:
            changed = self._session.make_intermediate_points_automatic(end_id)
        except ValueError as exc:
            self._show_status(str(exc))
            return
        self._show_status(f"Made {changed} intermediate points automatic.")
        self._render()

    @Slot(str, float, float)
    def move_keyframe(self, edit_id: str, x: float, y: float) -> None:
        """Update only the working spatial coordinates during a drag."""
        if self._session is None or self._pending_command_id is not None:
            return
        try:
            self._session.move_keyframe(edit_id, x, y)
        except ValueError as exc:
            self._show_status(str(exc))
            return
        self._render(rebuild_overlay=False)

    @Slot(str, str, float, float)
    def insert_midpoint(self, start_id: str, end_id: str, x: float, y: float) -> None:
        """Promote one midpoint handle into a fixed-date working keyframe."""
        if self._session is None or self._pending_command_id is not None:
            return
        try:
            self._session.insert_between(start_id, end_id, x, y)
        except ValueError as exc:
            self._show_status(str(exc))
            return
        self._render()

    @Slot()
    def add_location_at_playhead(self) -> None:
        """Add a dated location at the current playhead and resolved position."""
        session = self._session
        if session is None or self._pending_command_id is not None:
            return
        playhead = self._window.timeline.get_playhead_time()
        keyframes = session.to_keyframes()
        base_position = self._window.map_widget.get_marker_base_position(
            session.marker_id
        )
        position = interpolate_position(
            keyframes,
            playhead,
            segment_modes=session.working_segment_modes,
            base_position=base_position,
        )
        if position is None:
            position = base_position
        if position is None:
            self._show_status("The marker has no position to copy.")
            return
        try:
            session.add_location(playhead, position[0], position[1])
        except ValueError as exc:
            self._show_status(str(exc))
            return
        self._render()

    @Slot()
    def delete_selected_keyframe(self) -> None:
        """Delete exactly the selected working keyframe."""
        if self._session is None or self._pending_command_id is not None:
            return
        try:
            deleted = self._session.delete_selected_keyframe()
        except ValueError as exc:
            self._show_status(str(exc))
            return
        if deleted:
            self._render()

    @Slot()
    def apply(self) -> None:
        """Persist the complete working trajectory as one undoable command."""
        session = self._session
        if session is None or self._pending_command_id is not None:
            return
        if not session.is_dirty:
            self._finish_session(self._current_authoritative())
            return
        if session.is_equalization_previewing:
            self._show_status("Apply or cancel the equalization preview first.")
            return
        if not session.can_apply:
            self._show_status(
                "Resolve trajectory validation or reload conflicts first."
            )
            return
        command = UpdateTrajectoryCommand(
            session.map_id,
            session.marker_id,
            cast("TrajectorySnapshot | None", copy.deepcopy(self._before_snapshot)),
            session.to_keyframes(),
            session.to_properties(),
        )
        self._pending_command_id = command.command_id
        self._render(pending=True)
        self.command_requested.emit(command)

    @Slot()
    def cancel(self) -> None:
        """Discard the working copy without persistence or history."""
        if self._session is None or self._pending_command_id is not None:
            return
        latest = self._latest_deferred or self._current_authoritative()
        self._finish_session(latest)

    @Slot()
    def discard_and_reload(self) -> None:
        """Resolve a conflict by discarding local edits and using latest data."""
        self.cancel()

    @Slot(CommandResult)
    def on_command_finished(self, result: CommandResult) -> None:
        """Request one targeted reload after apply, undo, or redo."""
        is_trajectory_result = result.command_name in {
            "UpdateTrajectoryCommand",
            "Undo_UpdateTrajectoryCommand",
            "Redo_UpdateTrajectoryCommand",
        }
        if not is_trajectory_result:
            return

        if result.command_name == "UpdateTrajectoryCommand":
            command_id = str(result.data.get("command_id", ""))
            if command_id != self._pending_command_id:
                return
            if not result.success:
                self._pending_command_id = None
                self._render()
                return
            command_state = result.data.get("command_state", {})
            data = (
                command_state.get("data", {}) if isinstance(command_state, dict) else {}
            )
            self._expected_after_snapshot = copy.deepcopy(
                data.get("after_snapshot") if isinstance(data, dict) else None
            )
            if self._session is not None:
                self._request_reload(self._session.map_id)
            return

        if result.success and self._session is None:
            map_id = self._effect_map_id(result)
            if map_id is not None:
                self._request_reload(map_id)

    def _render(self, *, pending: bool = False, rebuild_overlay: bool = True) -> None:
        if self._session is not None:
            self._window.map_widget.show_trajectory_edit(
                self._session.to_snapshot(),
                pending=pending,
                rebuild_overlay=rebuild_overlay,
            )

    def _finish_session(self, trajectories: list[dict[str, Any]]) -> None:
        session = self._session
        self._session = None
        self._before_snapshot = None
        self._active_record_at_start = None
        self._latest_deferred = None
        self._pending_command_id = None
        self._expected_after_snapshot = None
        if session is not None:
            self._authoritative_by_map[session.map_id] = copy.deepcopy(trajectories)
            self._window.map_handler.on_trajectories_ready(
                session.map_id, copy.deepcopy(trajectories)
            )
        self._window.map_widget.clear_trajectory_edit()

    def _current_authoritative(self) -> list[dict[str, Any]]:
        if self._session is None:
            return []
        return copy.deepcopy(self._authoritative_by_map.get(self._session.map_id, []))

    def _request_reload(self, map_id: str) -> None:
        invoke_queued(
            self._window.worker,
            "load_trajectories",
            Q_ARG(str, map_id),
        )

    @staticmethod
    def _effect_map_id(result: CommandResult) -> str | None:
        effects = result.data.get("effects", [])
        if not isinstance(effects, list):
            return None
        for effect in effects:
            if isinstance(effect, dict) and effect.get("kind") == "trajectory_changed":
                return str(effect.get("map_id"))
        return None

    def _show_status(self, message: str) -> None:
        logger.warning(message)
        if hasattr(self._window, "status_bar"):
            self._window.status_bar.showMessage(message, 5000)

    def _show_date_error(self, message: str) -> None:
        """Keep a rejected date operation visible beside the date controls."""
        self._window.map_widget.show_trajectory_date_error(message)
        self._show_status(message)
