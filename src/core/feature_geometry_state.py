"""Temporal replacement geometry for path and region map features."""

from __future__ import annotations

import copy
import math
import time
import uuid
from bisect import bisect_right
from dataclasses import dataclass, field
from typing import Any, Literal, Sequence

from src.core.marker import FEATURE_TYPE_PATH, FEATURE_TYPE_REGION, MapFeature

Geometry = list[dict[str, float]]
GeometrySource = Literal["base", "dated"]


def validate_feature_geometry(feature_type: str, geometry: Geometry) -> None:
    """Validate one normalized path or region geometry.

    Args:
        feature_type: Map feature discriminator.
        geometry: Normalized coordinate dictionaries.

    Raises:
        ValueError: If the feature type or coordinates are invalid.
    """
    minimum = 2 if feature_type == FEATURE_TYPE_PATH else 3
    if feature_type not in {FEATURE_TYPE_PATH, FEATURE_TYPE_REGION}:
        raise ValueError("Dated geometry is available only for paths and regions.")
    if len(geometry) < minimum:
        raise ValueError(
            f"{feature_type.title()} geometry requires at least {minimum} vertices."
        )
    for point in geometry:
        if set(point) != {"x", "y"}:
            raise ValueError("Every geometry vertex must contain only x and y.")
        x = float(point["x"])
        y = float(point["y"])
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Geometry coordinates must be finite.")
        if not 0.0 <= x <= 1.0 or not 0.0 <= y <= 1.0:
            raise ValueError("Geometry coordinates must be between 0.0 and 1.0.")


def calculate_feature_anchor(geometry: Geometry) -> tuple[float, float]:
    """Return the existing arithmetic-mean anchor for a geometry."""
    if not geometry:
        raise ValueError("Geometry cannot be empty.")
    count = len(geometry)
    return (
        sum(float(point["x"]) for point in geometry) / count,
        sum(float(point["y"]) for point in geometry) / count,
    )


@dataclass(frozen=True)
class FeatureGeometryState:
    """A complete geometry that becomes effective at one lore date."""

    marker_id: str
    effective_date: float
    geometry: Geometry
    anchor_x: float
    anchor_y: float
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe independent snapshot."""
        return {
            "id": self.id,
            "marker_id": self.marker_id,
            "effective_date": self.effective_date,
            "geometry": copy.deepcopy(self.geometry),
            "anchor_x": self.anchor_x,
            "anchor_y": self.anchor_y,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeatureGeometryState":
        """Reconstruct a state from a repository or command snapshot."""
        geometry = [
            {"x": float(point["x"]), "y": float(point["y"])}
            for point in data["geometry"]
        ]
        return cls(
            id=str(data.get("id") or uuid.uuid4()),
            marker_id=str(data["marker_id"]),
            effective_date=float(data["effective_date"]),
            geometry=geometry,
            anchor_x=float(data["anchor_x"]),
            anchor_y=float(data["anchor_y"]),
            created_at=float(data.get("created_at", time.time())),
            modified_at=float(data.get("modified_at", time.time())),
        )


@dataclass(frozen=True)
class ResolvedFeatureGeometry:
    """The geometry and provenance selected for one playhead date."""

    geometry: Geometry
    anchor_x: float
    anchor_y: float
    source_type: GeometrySource
    state_id: str | None = None
    effective_date: float | None = None


def resolve_feature_geometry(
    marker: MapFeature,
    states: Sequence[FeatureGeometryState],
    playhead_date: float,
) -> ResolvedFeatureGeometry:
    """Resolve Base Geometry or the latest dated replacement at the playhead."""
    ordered = sorted(states, key=lambda state: state.effective_date)
    index = bisect_right(
        [state.effective_date for state in ordered], float(playhead_date)
    )
    if index == 0:
        return ResolvedFeatureGeometry(
            geometry=copy.deepcopy(marker.geometry or []),
            anchor_x=float(marker.x),
            anchor_y=float(marker.y),
            source_type="base",
        )
    state = ordered[index - 1]
    return ResolvedFeatureGeometry(
        geometry=copy.deepcopy(state.geometry),
        anchor_x=state.anchor_x,
        anchor_y=state.anchor_y,
        source_type="dated",
        state_id=state.id,
        effective_date=state.effective_date,
    )
