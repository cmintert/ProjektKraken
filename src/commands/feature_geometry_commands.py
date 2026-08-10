"""Undoable complete replacement of one feature's dated geometry states."""

from __future__ import annotations

import copy
from collections.abc import Sequence
from typing import Any

from src.commands.base_command import BaseCommand, CommandResult
from src.core.feature_geometry_state import FeatureGeometryState
from src.services.db_service import DatabaseService


class ReplaceFeatureGeometryStatesCommand(BaseCommand):
    """Apply one atomic create, edit, retime, or delete state operation."""

    def __init__(
        self,
        map_id: str,
        marker_id: str,
        before_snapshot: list[dict],
        after_states: Sequence[FeatureGeometryState | dict[str, Any]],
        description: str = "Update Dated Geometry",
    ) -> None:
        super().__init__()
        self.map_id = map_id
        self.marker_id = marker_id
        self.before_snapshot = copy.deepcopy(before_snapshot)
        self.after_states = [
            state.to_dict() if isinstance(state, FeatureGeometryState) else copy.deepcopy(state)
            for state in after_states
        ]
        self.after_snapshot: list[dict] | None = None
        self._description = description

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Apply or redo the complete ordered state set."""
        if self._is_executed:
            return CommandResult(False, "Geometry-state update is already applied.")
        replacement = self.after_snapshot or self.after_states
        try:
            self.after_snapshot = db_service.feature_geometry_repo.replace_marker_states(
                self.marker_id,
                replacement,
                expected_snapshot=copy.deepcopy(self.before_snapshot),
            )
            self._is_executed = True
            return CommandResult(
                True,
                "Dated geometry updated.",
                command_name=self.__class__.__name__,
                data={"effects": [self._effect()]},
            )
        except Exception as exc:
            return CommandResult(
                False,
                str(exc),
                command_name=self.__class__.__name__,
            )

    def undo(self, db_service: DatabaseService) -> CommandResult:
        """Restore the exact state set captured before the operation."""
        if not self._is_executed or self.after_snapshot is None:
            return CommandResult(False, "Geometry-state update is not applied.")
        try:
            db_service.feature_geometry_repo.replace_marker_states(
                self.marker_id,
                copy.deepcopy(self.before_snapshot),
                expected_snapshot=copy.deepcopy(self.after_snapshot),
            )
            self._is_executed = False
            return CommandResult(
                True,
                "Dated geometry update undone.",
                command_name=f"Undo_{self.__class__.__name__}",
                data={"effects": [self._effect()]},
            )
        except Exception as exc:
            return CommandResult(
                False,
                str(exc),
                command_name=f"Undo_{self.__class__.__name__}",
            )

    def get_description(self) -> str:
        """Return the user-facing operation description."""
        return self._description

    def to_dict(self) -> dict:
        """Serialize complete before and after snapshots."""
        return {
            "map_id": self.map_id,
            "marker_id": self.marker_id,
            "before_snapshot": copy.deepcopy(self.before_snapshot),
            "after_states": copy.deepcopy(self.after_states),
            "after_snapshot": copy.deepcopy(self.after_snapshot),
            "description": self._description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReplaceFeatureGeometryStatesCommand":
        """Reconstruct a persistent command."""
        command = cls(
            str(data["map_id"]),
            str(data["marker_id"]),
            list(data.get("before_snapshot", [])),
            list(data.get("after_states", [])),
            str(data.get("description", "Update Dated Geometry")),
        )
        raw_after = data.get("after_snapshot")
        command.after_snapshot = copy.deepcopy(raw_after) if raw_after is not None else None
        return command

    def _effect(self) -> dict[str, str]:
        return {
            "kind": "feature_geometry_states_changed",
            "map_id": self.map_id,
            "marker_id": self.marker_id,
        }
