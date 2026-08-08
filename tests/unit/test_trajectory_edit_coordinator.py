"""Application coordination tests for direct spatial trajectory editing."""

from unittest.mock import MagicMock

from PySide6.QtCore import QObject, Signal

from src.app.coordinators.trajectory_edit_coordinator import (
    TrajectoryEditCoordinator,
)
from src.commands.base_command import CommandResult
from src.commands.trajectory_commands import UpdateTrajectoryCommand


class _Worker(QObject):
    command_finished = Signal(CommandResult)


class _MapWidget:
    def __init__(self) -> None:
        self._playhead_time = 5.0
        self.show_trajectory_edit = MagicMock()
        self.clear_trajectory_edit = MagicMock()

    def get_selected_map_id(self) -> str:
        return "map-1"


class _MapHandler:
    def __init__(self) -> None:
        self.on_trajectories_ready = MagicMock()


class _Window(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.map_widget = _MapWidget()
        self.map_handler = _MapHandler()
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


def _coordinator():
    window = _Window()
    coordinator = TrajectoryEditCoordinator(window)  # type: ignore[arg-type]
    coordinator.on_trajectories_ready("map-1", [_record()])
    return coordinator, window


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
