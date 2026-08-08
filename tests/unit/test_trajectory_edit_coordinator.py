"""Application coordination tests for direct spatial trajectory editing."""

from unittest.mock import MagicMock

from PySide6.QtCore import QObject, Signal

from src.app.coordinators.trajectory_edit_coordinator import (
    TrajectoryEditCoordinator,
)
from src.commands.base_command import CommandResult
from src.commands.trajectory_commands import UpdateTrajectoryCommand
from src.core.trajectory import TrajectoryDistanceContext


class _Worker(QObject):
    command_finished = Signal(CommandResult)


class _MapWidget:
    def __init__(self) -> None:
        self._playhead_time = 5.0
        self.show_trajectory_edit = MagicMock()
        self.clear_trajectory_edit = MagicMock()
        self.get_trajectory_distance_context = MagicMock(
            return_value=TrajectoryDistanceContext(1.0, 1.0)
        )

    def get_selected_map_id(self) -> str:
        return "map-1"


class _MapHandler:
    def __init__(self) -> None:
        self.on_trajectories_ready = MagicMock()


class _Timeline(QObject):
    playhead_time_changed = Signal(float)

    def __init__(self) -> None:
        super().__init__()
        self._playhead_time = 5.0

    def get_playhead_time(self) -> float:
        return self._playhead_time

    def set_playhead_time(self, value: float) -> None:
        self._playhead_time = value
        self.playhead_time_changed.emit(value)


class _Window(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.map_widget = _MapWidget()
        self.map_handler = _MapHandler()
        self.timeline = _Timeline()
        self.worker = _Worker()


def _record(*, x: float = 0.1) -> dict:
    row = {
        "id": "trajectory-1",
        "marker_id": 7,
        "properties": '{"name": "route"}',
        "trajectory": "mf-json",
        "t_start": 0.0,
        "t_end": 10.0,
    }
    return {
        "marker_id": "marker-1",
        "trajectory_id": "trajectory-1",
        "keyframes": [
            {"t": 0.0, "x": x, "y": 0.2},
            {"t": 10.0, "x": 0.9, "y": 0.8},
        ],
        "row_snapshot": row,
    }


def _coordinator(record=None):
    window = _Window()
    coordinator = TrajectoryEditCoordinator(window)  # type: ignore[arg-type]
    coordinator.on_trajectories_ready("map-1", [record or _record()])
    return coordinator, window


def _speed_record() -> dict:
    record = _record()
    record["keyframes"] = [
        {"t": 0.0, "x": 0.0, "y": 0.0},
        {"t": 12.0, "x": 0.25, "y": 0.0},
        {"t": 20.0, "x": 1.0, "y": 0.0},
    ]
    return record


def test_cancel_discards_preview_without_command():
    coordinator, window = _coordinator()
    commands = []
    coordinator.command_requested.connect(commands.append)
    coordinator.start_edit("marker-1")
    edit_id = coordinator._session.working_keyframes[0].edit_id  # type: ignore[union-attr]
    coordinator.move_keyframe(edit_id, 0.3, 0.4)

    coordinator.cancel()

    assert commands == []
    assert not coordinator.is_active
    window.map_widget.clear_trajectory_edit.assert_called_once()


def test_switching_maps_discards_active_edit():
    coordinator, window = _coordinator()
    coordinator.start_edit("marker-1")

    coordinator.on_map_selected("map-2")

    assert not coordinator.is_active
    window.map_widget.clear_trajectory_edit.assert_called_once()


def test_apply_emits_one_atomic_command_and_waits_for_reload():
    coordinator, window = _coordinator()
    commands = []
    coordinator.command_requested.connect(commands.append)
    coordinator._request_reload = MagicMock()  # type: ignore[method-assign]
    coordinator.start_edit("marker-1")
    edit_id = coordinator._session.working_keyframes[0].edit_id  # type: ignore[union-attr]
    coordinator.move_keyframe(edit_id, 0.3, 0.4)

    coordinator.apply()

    assert len(commands) == 1
    command = commands[0]
    assert isinstance(command, UpdateTrajectoryCommand)
    assert coordinator.is_active
    after = {**_record(x=0.3)["row_snapshot"], "trajectory": "updated"}
    coordinator.on_command_finished(
        CommandResult(
            success=True,
            command_name="UpdateTrajectoryCommand",
            data={
                "command_id": command.command_id,
                "command_state": {"data": {"after_snapshot": after}},
            },
        )
    )
    coordinator._request_reload.assert_called_once_with("map-1")
    assert coordinator.is_active

    updated = _record(x=0.3)
    updated["row_snapshot"] = after
    coordinator.on_trajectories_ready("map-1", [updated])

    assert not coordinator.is_active
    window.map_widget.clear_trajectory_edit.assert_called_once()


def test_conflicting_reload_preserves_working_copy_and_blocks_apply():
    coordinator, window = _coordinator()
    commands = []
    coordinator.command_requested.connect(commands.append)
    coordinator.start_edit("marker-1")
    edit_id = coordinator._session.working_keyframes[0].edit_id  # type: ignore[union-attr]
    coordinator.move_keyframe(edit_id, 0.3, 0.4)
    external = _record(x=0.7)
    external["row_snapshot"] = {
        **external["row_snapshot"],
        "trajectory": "external",
    }

    coordinator.on_trajectories_ready("map-1", [external])
    coordinator.apply()

    assert coordinator._session is not None
    assert coordinator._session.is_conflicted
    assert coordinator._session.working_keyframes[0].x == 0.3
    assert commands == []
    window.map_widget.show_trajectory_edit.assert_called()

    coordinator.discard_and_reload()
    assert not coordinator.is_active


def test_date_edit_does_not_move_playhead_or_follow_navigation():
    coordinator, window = _coordinator()
    commands = []
    coordinator.command_requested.connect(commands.append)
    coordinator.start_edit("marker-1")
    session = coordinator._session
    assert session is not None
    first_id = session.working_keyframes[0].edit_id
    coordinator.begin_date_edit(first_id)
    window.timeline.set_playhead_time(12.0)

    assert coordinator.is_date_editing
    assert window.timeline.get_playhead_time() == 12.0
    assert session.working_keyframes[0].edit_id == first_id
    assert session.working_keyframes[0].t == 0.0
    assert commands == []


def test_direct_date_input_changes_proposal_without_moving_playhead():
    coordinator, window = _coordinator()
    coordinator.start_edit("marker-1")
    session = coordinator._session
    assert session is not None
    first_id = session.working_keyframes[0].edit_id
    coordinator.begin_date_edit(first_id)
    coordinator.set_date_value(7.0)

    assert window.timeline.get_playhead_time() == 5.0
    assert session.active_date_value == 7.0


def test_selected_keyframe_date_can_copy_current_playhead_without_moving_it():
    coordinator, window = _coordinator()
    coordinator.start_edit("marker-1")
    session = coordinator._session
    assert session is not None
    first_id = session.working_keyframes[0].edit_id
    coordinator.select_keyframe(first_id)
    window.timeline.set_playhead_time(7.0)

    coordinator.set_selected_date_from_playhead()

    selected = next(
        keyframe
        for keyframe in session.working_keyframes
        if keyframe.edit_id == first_id
    )
    assert selected.t == 7.0
    assert window.timeline.get_playhead_time() == 7.0
    assert not coordinator.is_date_editing
    window.map_widget.show_trajectory_edit.assert_called()


def test_use_playhead_inside_date_edit_keeps_suboperation_open():
    coordinator, window = _coordinator()
    coordinator.start_edit("marker-1")
    session = coordinator._session
    assert session is not None
    first_id = session.working_keyframes[0].edit_id
    coordinator.begin_date_edit(first_id)
    window.timeline.set_playhead_time(7.0)

    coordinator.set_selected_date_from_playhead()

    assert coordinator.is_date_editing
    assert session.active_date_value == 7.0
    assert window.timeline.get_playhead_time() == 7.0


def test_cancel_date_restores_date_but_keeps_spatial_edit_and_playhead():
    coordinator, window = _coordinator()
    coordinator.start_edit("marker-1")
    session = coordinator._session
    assert session is not None
    first_id = session.working_keyframes[0].edit_id
    coordinator.move_keyframe(first_id, 0.3, 0.4)
    coordinator.begin_date_edit(first_id)
    window.timeline.set_playhead_time(7.0)
    coordinator.set_selected_date_from_playhead()

    coordinator.cancel_date_edit()

    restored = next(
        keyframe
        for keyframe in session.working_keyframes
        if keyframe.edit_id == first_id
    )
    assert not coordinator.is_date_editing
    assert restored.t == 0.0
    assert (restored.x, restored.y) == (0.3, 0.4)
    assert window.timeline.get_playhead_time() == 7.0


def test_full_cancel_keeps_current_playhead():
    coordinator, window = _coordinator()
    coordinator.start_edit("marker-1")
    window.timeline.set_playhead_time(8.0)

    coordinator.cancel()

    assert window.timeline.get_playhead_time() == 8.0
    assert not coordinator.is_active


def test_apply_does_not_move_playhead_to_proposed_date():
    coordinator, window = _coordinator()
    commands = []
    coordinator.command_requested.connect(commands.append)
    coordinator.start_edit("marker-1")
    session = coordinator._session
    assert session is not None
    first_id = session.working_keyframes[0].edit_id
    coordinator.begin_date_edit(first_id)
    coordinator.set_date_value(7.0)

    coordinator.apply()

    assert len(commands) == 1
    assert window.timeline.get_playhead_time() == 5.0


def test_speed_equalization_preview_has_no_persistence_side_effect():
    coordinator, window = _coordinator(_speed_record())
    commands = []
    coordinator.command_requested.connect(commands.append)
    coordinator.start_edit("marker-1")
    session = coordinator._session
    assert session is not None
    start_id = session.working_keyframes[0].edit_id
    end_id = session.working_keyframes[-1].edit_id

    coordinator.set_speed_anchor(start_id)
    coordinator.preview_speed_equalization(end_id)

    assert session.is_equalization_previewing
    assert [item.t for item in session.working_keyframes] == [0.0, 5.0, 20.0]
    assert commands == []
    window.map_widget.get_trajectory_distance_context.assert_called_once()


def test_cancel_speed_equalization_restores_dates_without_command():
    coordinator, _window = _coordinator(_speed_record())
    commands = []
    coordinator.command_requested.connect(commands.append)
    coordinator.start_edit("marker-1")
    session = coordinator._session
    assert session is not None
    start_id = session.working_keyframes[0].edit_id
    end_id = session.working_keyframes[-1].edit_id
    coordinator.set_speed_anchor(start_id)
    coordinator.preview_speed_equalization(end_id)

    coordinator.cancel_speed_equalization()

    assert [item.t for item in session.working_keyframes] == [0.0, 12.0, 20.0]
    assert not session.is_equalization_previewing
    assert commands == []


def test_confirm_then_trajectory_apply_emits_one_atomic_command():
    coordinator, _window = _coordinator(_speed_record())
    commands = []
    coordinator.command_requested.connect(commands.append)
    coordinator.start_edit("marker-1")
    session = coordinator._session
    assert session is not None
    coordinator.set_speed_anchor(session.working_keyframes[0].edit_id)
    coordinator.preview_speed_equalization(session.working_keyframes[-1].edit_id)

    coordinator.apply()
    assert commands == []

    coordinator.confirm_speed_equalization()
    coordinator.apply()

    assert len(commands) == 1
    command = commands[0]
    assert isinstance(command, UpdateTrajectoryCommand)
    assert [item.t for item in command.after_keyframes] == [0.0, 5.0, 20.0]


def test_whole_speed_equalization_uses_map_distance_context():
    coordinator, window = _coordinator(_speed_record())
    coordinator.start_edit("marker-1")

    coordinator.preview_whole_speed_equalization()

    assert coordinator._session is not None
    assert coordinator._session.is_equalization_previewing
    window.map_widget.get_trajectory_distance_context.assert_called_once()
