"""Undoable complete replacement of one feature's dated geometry states."""

from __future__ import annotations

import copy
import dataclasses
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
        """Initialize a complete feature-geometry state replacement."""
        super().__init__()
        self.map_id = map_id
        self.marker_id = marker_id
        self.before_snapshot = copy.deepcopy(before_snapshot)
        self.after_states = [
            state.to_dict()
            if isinstance(state, FeatureGeometryState)
            else copy.deepcopy(state)
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
            self.after_snapshot = (
                db_service.feature_geometry_repo.replace_marker_states(
                    self.marker_id,
                    replacement,
                    expected_snapshot=copy.deepcopy(self.before_snapshot),
                )
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
        command.after_snapshot = (
            copy.deepcopy(raw_after) if raw_after is not None else None
        )
        return command

    def _effect(self) -> dict[str, str]:
        return {
            "kind": "feature_geometry_states_changed",
            "map_id": self.map_id,
            "marker_id": self.marker_id,
        }


class UpdateFeatureBaseGeometryCommand(BaseCommand):
    """Compare and replace Base geometry without overwriting concurrent edits."""

    def __init__(
        self, marker_id: str, before: dict[str, Any], after: dict[str, Any]
    ) -> None:
        """Capture only the geometry and anchor fields owned by this edit."""
        super().__init__()
        self.marker_id = marker_id
        self.update_data = copy.deepcopy(after)
        self.before = copy.deepcopy(before)

    def _replace(
        self,
        db_service: DatabaseService,
        expected: dict[str, Any],
        replacement: dict[str, Any],
    ) -> str:
        with db_service.transaction():
            marker = db_service.get_marker(self.marker_id)
            if marker is None:
                raise ValueError("The edited feature no longer exists.")
            current = {"geometry": marker.geometry, "x": marker.x, "y": marker.y}
            if current != expected:
                raise ValueError("Base geometry changed while you were editing.")
            db_service.insert_marker(dataclasses.replace(marker, **replacement))
            return marker.map_id

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Apply only when the original Base geometry still matches."""
        try:
            map_id = self._replace(db_service, self.before, self.update_data)
            self._is_executed = True
            return CommandResult(
                True,
                "Base geometry updated.",
                command_name=self.__class__.__name__,
                data={"effects": [self._effect(map_id)]},
            )
        except Exception as exc:
            return CommandResult(False, str(exc), command_name=self.__class__.__name__)

    def undo(self, db_service: DatabaseService) -> CommandResult:
        """Restore geometry while preserving unrelated current marker fields."""
        try:
            map_id = self._replace(db_service, self.update_data, self.before)
            self._is_executed = False
            return CommandResult(
                True,
                "Base geometry restored.",
                command_name=f"Undo_{self.__class__.__name__}",
                data={"effects": [self._effect(map_id)]},
            )
        except Exception as exc:
            return CommandResult(
                False, str(exc), command_name=f"Undo_{self.__class__.__name__}"
            )

    @staticmethod
    def _effect(map_id: str) -> dict[str, str]:
        return {"kind": "feature_base_geometry_changed", "map_id": map_id}

    def to_dict(self) -> dict:
        """Serialize the optimistic before/after geometry snapshots."""
        return {
            "marker_id": self.marker_id,
            "before": self.before,
            "after": self.update_data,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UpdateFeatureBaseGeometryCommand":
        """Restore a serialized geometry command."""
        return cls(data["marker_id"], data["before"], data["after"])
