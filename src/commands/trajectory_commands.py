"""Undoable commands for complete trajectory replacement."""

import copy
import logging

from src.commands.base_command import BaseCommand, CommandResult
from src.core.trajectory import Keyframe, clone_keyframes
from src.services.db_service import DatabaseService
from src.services.repositories.trajectory_repository import TrajectorySnapshot

logger = logging.getLogger(__name__)


class UpdateTrajectoryCommand(BaseCommand):
    """Atomically apply one complete trajectory edit session."""

    def __init__(
        self,
        map_id: str,
        marker_id: str,
        before_snapshot: TrajectorySnapshot | None,
        after_keyframes: list[Keyframe],
        after_properties: dict | None = None,
    ) -> None:
        """Initialize a complete trajectory update.

        Args:
            map_id: ID of the containing map.
            marker_id: Entity or event ID associated with the map marker.
            before_snapshot: Exact row state captured when editing began.
            after_keyframes: Complete desired keyframe state.
            after_properties: Complete desired trajectory properties.

        """
        super().__init__()
        self.map_id = map_id
        self.marker_id = marker_id
        self.before_snapshot = copy.deepcopy(before_snapshot)
        self.after_keyframes = clone_keyframes(after_keyframes)
        self.after_properties = copy.deepcopy(after_properties)
        self.after_snapshot: TrajectorySnapshot | None = None
        self._after_snapshot_resolved = False

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Apply or redo the complete trajectory replacement.

        Args:
            db_service: Worker-thread-owned database service.

        Returns:
            Result describing whether the replacement succeeded.

        """
        if self._is_executed:
            return CommandResult(
                success=False,
                message="Trajectory update is already applied.",
                command_name="UpdateTrajectoryCommand",
            )

        try:
            if self._after_snapshot_resolved:
                persisted = db_service.restore_marker_trajectory_snapshot(
                    self.map_id,
                    self.marker_id,
                    copy.deepcopy(self.after_snapshot),
                    expected_snapshot=copy.deepcopy(self.before_snapshot),
                )
            else:
                persisted = db_service.set_marker_trajectory(
                    self.map_id,
                    self.marker_id,
                    clone_keyframes(self.after_keyframes),
                    properties=copy.deepcopy(self.after_properties),
                    expected_snapshot=copy.deepcopy(self.before_snapshot),
                )
                self.after_snapshot = copy.deepcopy(persisted)
                self._after_snapshot_resolved = True

            self._is_executed = True
            return CommandResult(
                success=True,
                message="Trajectory updated.",
                command_name="UpdateTrajectoryCommand",
                data={
                    "trajectory_id": (
                        persisted["id"] if persisted is not None else None
                    ),
                    "effects": [self._trajectory_changed_effect()],
                },
            )
        except Exception as exc:
            logger.warning("Trajectory update failed: %s", exc, exc_info=True)
            return CommandResult(
                success=False,
                message=str(exc),
                command_name="UpdateTrajectoryCommand",
            )

    def undo(self, db_service: DatabaseService) -> CommandResult:
        """Restore the exact row state captured before the edit session.

        Args:
            db_service: Worker-thread-owned database service.

        Returns:
            Result describing whether restoration succeeded.

        """
        if not self._is_executed or not self._after_snapshot_resolved:
            return CommandResult(
                success=False,
                message="Trajectory update is not currently applied.",
                command_name="Undo_UpdateTrajectoryCommand",
            )

        try:
            restored = db_service.restore_marker_trajectory_snapshot(
                self.map_id,
                self.marker_id,
                copy.deepcopy(self.before_snapshot),
                expected_snapshot=copy.deepcopy(self.after_snapshot),
            )
            self._is_executed = False
            return CommandResult(
                success=True,
                message="Trajectory update undone.",
                command_name="Undo_UpdateTrajectoryCommand",
                data={
                    "trajectory_id": (
                        restored["id"] if restored is not None else None
                    ),
                    "effects": [self._trajectory_changed_effect()],
                },
            )
        except Exception as exc:
            logger.warning("Trajectory undo failed: %s", exc, exc_info=True)
            return CommandResult(
                success=False,
                message=str(exc),
                command_name="Undo_UpdateTrajectoryCommand",
            )

    def to_dict(self) -> dict:
        """Serialize complete independent before and after command state."""
        return {
            "map_id": self.map_id,
            "marker_id": self.marker_id,
            "before_snapshot": copy.deepcopy(self.before_snapshot),
            "after_keyframes": [
                {
                    "id": keyframe.keyframe_id,
                    "t": keyframe.t,
                    "x": keyframe.x,
                    "y": keyframe.y,
                }
                for keyframe in self.after_keyframes
            ],
            "after_properties": copy.deepcopy(self.after_properties),
            "after_snapshot": copy.deepcopy(self.after_snapshot),
            "after_snapshot_resolved": self._after_snapshot_resolved,
        }

    def _trajectory_changed_effect(self) -> dict[str, str]:
        """Return the targeted UI-refresh effect for this trajectory."""
        return {
            "kind": "trajectory_changed",
            "map_id": self.map_id,
            "marker_id": self.marker_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UpdateTrajectoryCommand":
        """Deserialize a persistent trajectory command snapshot.

        Args:
            data: Dictionary produced by :meth:`to_dict`.

        Returns:
            Reconstructed command with independent snapshot values.

        """
        after_keyframes = [
            Keyframe(
                t=float(keyframe["t"]),
                x=float(keyframe["x"]),
                y=float(keyframe["y"]),
                keyframe_id=(
                    str(keyframe["id"])
                    if keyframe.get("id") is not None
                    else None
                ),
            )
            for keyframe in data["after_keyframes"]
        ]
        command = cls(
            map_id=str(data["map_id"]),
            marker_id=str(data["marker_id"]),
            before_snapshot=copy.deepcopy(data.get("before_snapshot")),
            after_keyframes=after_keyframes,
            after_properties=copy.deepcopy(data.get("after_properties")),
        )
        command.after_snapshot = copy.deepcopy(data.get("after_snapshot"))
        command._after_snapshot_resolved = bool(
            data.get("after_snapshot_resolved", False)
        )
        return command
