"""Optimistically guarded creation of an independent neighboring region."""

import copy
from typing import Any

from src.commands.base_command import CommandResult
from src.commands.marker_commands import CreateMarkerCommand
from src.core.feature_geometry_state import resolve_feature_geometry
from src.core.region_geometry import Geometry, RegionPolygon
from src.services.db_service import DatabaseService


class CreateNeighborRegionCommand(CreateMarkerCommand):
    """Recheck the source inside the creation transaction, then save once."""

    def __init__(
        self,
        marker_data: dict[str, Any],
        source_id: str,
        source_date: float,
        source_geometry: Geometry,
    ) -> None:
        """Capture the preview's source without retaining a database service."""
        super().__init__(marker_data)
        self.source_id = source_id
        self.source_date = source_date
        self.source_geometry = copy.deepcopy(source_geometry)
        self._saved_once = False

    def execute(self, db_service: DatabaseService) -> CommandResult:
        """Reject stale first saves; redo restores the independent saved shape."""
        if not self._saved_once:
            source = db_service.get_marker(self.source_id)
            if (
                source is None
                or source.map_id != self.map_id
                or source.feature_type != "region"
            ):
                return CommandResult(
                    False, "The source region was removed. Keep drawing."
                )
            resolved = resolve_feature_geometry(
                source,
                db_service.feature_geometry_repo.get_states(source.id),
                self.source_date,
            )
            if resolved.geometry != self.source_geometry:
                return CommandResult(False, "The source border changed. Preview again.")
        try:
            if self._marker.geometry is None:
                raise ValueError("The new region has no geometry.")
            RegionPolygon.from_geometry(self._marker.geometry).validated()
        except ValueError as exc:
            return CommandResult(False, str(exc))
        result = super().execute(db_service)
        if result.success:
            self._saved_once = True
        return result

    def to_dict(self) -> dict[str, Any]:
        """Retain exact geometry and first-save verification across history."""
        return {
            **super().to_dict(),
            "source_id": self.source_id,
            "source_date": self.source_date,
            "source_geometry": copy.deepcopy(self.source_geometry),
            "saved_once": self._saved_once,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CreateNeighborRegionCommand":
        """Restore the source guard and marker undo identity."""
        command = cls(
            data["marker_data"],
            data["source_id"],
            data["source_date"],
            data["source_geometry"],
        )
        command._actual_marker_id = data.get("actual_marker_id")
        command._is_executed = bool(data.get("is_executed", False))
        command._saved_once = bool(data.get("saved_once", False))
        return command
