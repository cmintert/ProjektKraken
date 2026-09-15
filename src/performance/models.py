"""Shared data models for the large-world measurement suite."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class FixtureProfile:
    """Deterministic workload shape used by one measurement run."""

    name: str
    event_count: int
    entity_count: int
    relation_count: int
    tag_count: int = 64
    description_size: int = 96
    dense_dates: bool = False
    marker_count: int = 0
    moving_marker_count: int = 0
    geometry_state_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable profile representation."""
        return asdict(self)


@dataclass
class MetricSeries:
    """Named collection of duration or resource samples."""

    unit: str
    samples: list[float] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


PROFILES: dict[str, FixtureProfile] = {
    "standard": FixtureProfile("standard", 10_000, 25_000, 40_000),
    "dense-time": FixtureProfile(
        "dense-time", 10_000, 25_000, 40_000, dense_dates=True
    ),
    "relation-heavy": FixtureProfile(
        "relation-heavy", 10_000, 25_000, 200_000, tag_count=128
    ),
    "large-content": FixtureProfile(
        "large-content", 10_000, 25_000, 40_000, description_size=2048
    ),
    "temporal-map": FixtureProfile(
        "temporal-map",
        10_000,
        25_000,
        40_000,
        marker_count=3_000,
        moving_marker_count=1_000,
        geometry_state_count=1_000,
    ),
}

