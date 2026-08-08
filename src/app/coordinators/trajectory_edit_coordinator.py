"""Application-level coordination for direct spatial trajectory editing."""

import copy
import logging
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import Q_ARG, QObject, Qt, Signal, Slot

from src.app.qt_invocation import invoke_queued
from src.commands.base_command import CommandResult
from src.commands.trajectory_commands import UpdateTrajectoryCommand
from src.core.trajectory import Keyframe
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
            self._session is not None
            and self._session.active_date_edit_id is not None
        )

    def bind_ui(self) -> None:
        """Connect map intents after the MainWindow widget skeleton exists."""
        if self._bound:
            return
        widget = self._window.map_widget
        widget.trajectory_edit_requested.connect(self.start_edit)
        widget.trajectory_keyframe_selected.connect(self.select_keyframe)
        widget.trajectory_keyframe_moved.connect(self.move_keyframe)
        widget.trajectory_midpoint_insert_requested.connect(self.insert_midpoint)
        widget.trajectory_delete_selected_requested.connect(
            self.delete_selected_keyframe
        )
        widget.trajectory_apply_requested.connect(self.apply)
        widget.trajectory_cancel_requested.connect(self.cancel)
        widget.trajectory_discard_reload_requested.connect(
            self.discard_and_reload
        )
        widget.trajectory_date_edit_requested.connect(self.begin_date_edit)
        widget.trajectory_date_value_changed.connect(self.set_date_value)
        widget.trajectory_date_step_requested.connect(self.step_date)
        widget.trajectory_date_edit_done_requested.connect(self.finish_date_edit)
        widget.trajectory_date_edit_cancel_requested.connect(self.cancel_date_edit)
        self._window.timeline.playhead_time_changed.connect(
            self.on_playhead_time_changed
        )
        self.command_requested.connect(self._window.command_requested.emit)
        self._window.worker.command_finished.connect(
            self.on_command_finished,
            Qt.ConnectionType.QueuedConnection,
        )
        self._bound = True

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

        if len(matching) != 1 or incoming_row != self._before_snapshot:
            session.mark_conflicted()

        # Apply harmless changes to unrelated trajectories, retaining the
        # session-start row for the active trajectory under the edit overlay.
        merged = [
            row for row in incoming if row.get("marker_id") != session.marker_id
        ]
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
        if len(records) != 1:
            message = (
                "This marker has multiple trajectory rows and cannot be edited."
                if len(records) > 1
                else "No trajectory is available for this marker."
            )
            self._show_status(message)
            return
        record = records[0]
        keyframes = [
            Keyframe(
                t=float(item["t"]),
                x=float(item["x"]),
                y=float(item["y"]),
            )
            for item in record.get("keyframes", [])
        ]
        self._session = TrajectoryEditSession.create(
            map_id=map_id,
            marker_id=marker_id,
            trajectory_id=str(record["trajectory_id"]),
            keyframes=keyframes,
            playhead=self._window.map_widget._playhead_time,
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
        """Start retiming a keyframe and jump the global playhead to it."""
        session = self._session
        if session is None or self._pending_command_id is not None:
            return
        try:
            if (
                session.active_date_edit_id is not None
                and session.active_date_edit_id != edit_id
            ):
                session.finish_date_edit()
            jump_time = session.begin_date_edit(
                edit_id, self._window.timeline.get_playhead_time()
            )
        except ValueError as exc:
            self._show_status(str(exc))
            return
        self._window.timeline.set_playhead_time(jump_time)

    @Slot(float)
    def set_date_value(self, proposed_time: float) -> None:
        """Route direct calendar input through the shared playhead preview."""
        if not self.is_date_editing or self._pending_command_id is not None:
            return
        self._window.timeline.set_playhead_time(proposed_time)

    @Slot(float)
    def step_date(self, delta_days: float) -> None:
        """Move the active proposed date by a small lore-day increment."""
        session = self._session
        if session is None or session.active_date_edit_id is None:
            return
        current = session.active_date_value
        if current is not None:
            self.set_date_value(current + delta_days)

    @Slot(float)
    def on_playhead_time_changed(self, proposed_time: float) -> None:
        """Preview timeline movement as the active keyframe's proposed date."""
        session = self._session
        if session is None or session.active_date_edit_id is None:
            return
        try:
            session.update_active_date(proposed_time)
        except ValueError as exc:
            self._show_status(str(exc))
            return
        self._render()

    @Slot()
    def finish_date_edit(self) -> None:
        """Keep the proposed date and leave the temporal sub-operation."""
        if self._session is None:
            return
        if self._session.finish_date_edit() is not None:
            self._render()

    @Slot()
    def cancel_date_edit(self) -> None:
        """Restore only the current keyframe's prior working date/playhead."""
        if self._session is None or self._pending_command_id is not None:
            return
        restore_playhead = self._session.cancel_date_edit()
        if restore_playhead is not None:
            self._window.timeline.set_playhead_time(restore_playhead)
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
    def insert_midpoint(
        self, start_id: str, end_id: str, x: float, y: float
    ) -> None:
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
    def delete_selected_keyframe(self) -> None:
        """Delete exactly the selected working keyframe."""
        if self._session is None or self._pending_command_id is not None:
            return
        if self._session.delete_selected_keyframe():
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
        if not session.can_apply:
            self._show_status("Resolve trajectory validation or reload conflicts first.")
            return
        command = UpdateTrajectoryCommand(
            session.map_id,
            session.marker_id,
            cast("TrajectorySnapshot | None", copy.deepcopy(self._before_snapshot)),
            session.to_keyframes(),
        )
        self._pending_command_id = command.command_id
        self._render(pending=True)
        self.command_requested.emit(command)

    @Slot()
    def cancel(self) -> None:
        """Discard the working copy without persistence or history."""
        if self._session is None or self._pending_command_id is not None:
            return
        restore_playhead = self._session.playhead_at_session_start
        latest = self._latest_deferred or self._current_authoritative()
        self._finish_session(latest)
        self._window.timeline.set_playhead_time(restore_playhead)

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
            data = command_state.get("data", {}) if isinstance(command_state, dict) else {}
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
        return copy.deepcopy(
            self._authoritative_by_map.get(self._session.map_id, [])
        )

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
