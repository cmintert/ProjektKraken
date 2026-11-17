"""Ephemeral split geometry, deliberately separate from persisted MapFeature."""

from dataclasses import dataclass
from typing import Any

from src.core.region_geometry import Point, RegionPolygon


@dataclass(frozen=True)
class ProjectedGeometry:
    """Every clipped display component with its authoritative source identity."""

    source_id: str
    source_map: str
    target_map: str
    feature_type: str
    polygons: tuple[RegionPolygon, ...] = ()
    lines: tuple[tuple[Point, ...], ...] = ()
    state_id: str | None = None
    effective_date: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize independent display rings and provenance without storage IDs."""
        return {
            "source_id": self.source_id,
            "source_map": self.source_map,
            "target_map": self.target_map,
            "feature_type": self.feature_type,
            "polygons": [p.to_geometry() for p in self.polygons],
            "lines": [[[x, y] for x, y in line] for line in self.lines],
            "state_id": self.state_id,
            "effective_date": self.effective_date,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectedGeometry":
        """Reconstruct a disposable frame, never an authoring feature."""
        return cls(
            source_id=data["source_id"],
            source_map=data["source_map"],
            target_map=data["target_map"],
            feature_type=data["feature_type"],
            polygons=tuple(
                RegionPolygon.from_geometry(p) for p in data.get("polygons", [])
            ),
            lines=tuple(
                tuple((float(x), float(y)) for x, y in line)
                for line in data.get("lines", [])
            ),
            state_id=data.get("state_id"),
            effective_date=data.get("effective_date"),
        )
