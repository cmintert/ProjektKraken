"""Serializable boundaries retain shared event identity and unknown/open intent."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.core.temporal_expression import TemporalExpression


@dataclass(frozen=True)
class TemporalAnchorRef:
    """An identifiable instant shared by all dependent boundaries."""

    anchor_id: str
    relation: str = "at"
    offset_days: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe reference."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TemporalAnchorRef:
        """Reconstruct an anchor reference."""
        return cls(**data)


@dataclass(frozen=True)
class TemporalBoundary:
    """An expression, anchor, explicitly open side, or unknown side."""

    expression: TemporalExpression | None = None
    anchor: TemporalAnchorRef | None = None
    status: str = "known"

    def to_dict(self) -> dict[str, Any]:
        """Serialize without substituting unknown sides with infinity."""
        result: dict[str, Any] = {"status": self.status}
        if self.expression is not None:
            result["expression"] = self.expression.to_dict()
        if self.anchor is not None:
            result["anchor"] = self.anchor.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TemporalBoundary:
        """Read a boundary independently of any database or UI."""
        return cls(
            expression=TemporalExpression.from_dict(data["expression"])
            if "expression" in data
            else None,
            anchor=TemporalAnchorRef.from_dict(data["anchor"])
            if "anchor" in data
            else None,
            status=data.get("status", "known"),
        )


@dataclass(frozen=True)
class TemporalIntervalSpec:
    """Half-open state interval whose boundaries may be uncertain."""

    start: TemporalBoundary
    end: TemporalBoundary

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe interval."""
        return {"start": self.start.to_dict(), "end": self.end.to_dict()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TemporalIntervalSpec:
        """Reconstruct an interval, preserving absent sides as unknown."""
        return cls(
            TemporalBoundary.from_dict(data.get("start", {"status": "unknown"})),
            TemporalBoundary.from_dict(data.get("end", {"status": "unknown"})),
        )
