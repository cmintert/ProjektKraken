"""Versioned timing definitions; compatibility coordinates are never evidence."""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from src.core.events import Event

EVENT_TIMING_SCHEMA = 2


def finite(value: Any) -> float:
    """Read a finite number without accepting booleans or invented defaults."""
    if isinstance(value, bool):
        raise ValueError("Timing values must be finite numbers")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Timing values must be finite numbers")
    return number


@dataclass(frozen=True)
class EndpointDefinition:
    """Exactly one manual assertion or calculated Event endpoint."""

    kind: Literal["manual", "event"] = "manual"
    instant: float | None = None
    expression: dict[str, Any] | None = None
    anchor_id: str | None = None
    endpoint: Literal["start", "end"] = "start"
    offset: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Reject ambiguous endpoint authorities."""
        if self.kind == "manual":
            if (self.instant is None) == (self.expression is None):
                raise ValueError("Choose one manual date or expression")
            if self.instant is not None:
                object.__setattr__(self, "instant", finite(self.instant))
            if self.anchor_id is not None or self.offset is not None:
                raise ValueError("A manual date cannot also follow an Event")
        elif self.kind == "event":
            self._validate_reference()
        else:
            raise ValueError("Unsupported endpoint source")

    def _validate_reference(self) -> None:
        if not self.anchor_id or not self.anchor_id.startswith("event:"):
            raise ValueError("Choose a source Event")
        if self.endpoint not in {"start", "end"}:
            raise ValueError("Choose a source start or end")
        if self.instant is not None or self.expression is not None:
            raise ValueError("A followed date cannot also contain manual evidence")
        offset = self.offset or {"unit": "days", "value": 0.0}
        unit, value = offset.get("unit"), finite(offset.get("value", 0))
        if unit not in {"days", "months", "years"}:
            raise ValueError("Choose days, months or years")
        if unit != "days" and (not value.is_integer() or not offset.get("calendar_id")):
            raise ValueError("Calendar offsets require whole units and a calendar")
        object.__setattr__(self, "offset", {**deepcopy(offset), "value": value})

    @property
    def source(self) -> str:
        """Return the canonical endpoint identity used by the dependency graph."""
        if self.anchor_id is None:
            raise ValueError("A manual endpoint has no source")
        return self.anchor_id + (":end" if self.endpoint == "end" else "")

    def to_dict(self) -> dict[str, Any]:
        """Return detached JSON data."""
        return {key: value for key, value in asdict(self).items() if value is not None}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EndpointDefinition:
        """Reject unsupported fields rather than discarding authored meaning."""
        return cls(**deepcopy(data))


@dataclass(frozen=True)
class EventTimingDefinition:
    """An explicit start and exactly one authority for the Event's end."""

    start: EndpointDefinition
    end_mode: Literal["none", "duration", "independent"] = "none"
    end: EndpointDefinition | None = None
    duration_days: float | None = None

    def __post_init__(self) -> None:
        """Validate the end authority, including explicit zero duration."""
        if self.end_mode == "duration":
            if self.duration_days is None or finite(self.duration_days) < 0:
                raise ValueError("Duration must be nonnegative")
            if self.end is not None:
                raise ValueError("Choose duration or independent end")
            object.__setattr__(self, "duration_days", finite(self.duration_days))
        elif self.end_mode == "independent":
            if self.end is None or self.duration_days is not None:
                raise ValueError("An independent end needs its own date source")
        elif (
            self.end_mode != "none"
            or self.end is not None
            or self.duration_days is not None
        ):
            raise ValueError("Unsupported end definition")

    def to_dict(self) -> dict[str, Any]:
        """Serialize the authoritative timing definition."""
        result: dict[str, Any] = {
            "start": self.start.to_dict(),
            "end_mode": self.end_mode,
        }
        if self.end is not None:
            result["end"] = self.end.to_dict()
        if self.duration_days is not None:
            result["duration_days"] = self.duration_days
        return result

    def require_supported_expressions(self) -> None:
        """Prevent authoring controls from reinterpreting opaque expression schemas."""
        from src.core.temporal_expression import TemporalExpression

        for endpoint in (self.start, self.end):
            if endpoint is not None and endpoint.expression is not None:
                TemporalExpression.from_dict(endpoint.expression)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EventTimingDefinition:
        """Read the explicit end discriminator without inferring zero as absence."""
        values = deepcopy(data)
        values["start"] = EndpointDefinition.from_dict(values["start"])
        if values.get("end") is not None:
            values["end"] = EndpointDefinition.from_dict(values["end"])
        return cls(**values)

    @classmethod
    def from_event(cls, event: Event) -> EventTimingDefinition:
        """Adapt legacy evidence without interpreting a projection as an assertion."""
        metadata = event.attributes.get("_temporal_v2", {})
        if not isinstance(metadata, dict) or metadata.get("schema", 1) not in {1, 2}:
            raise ValueError("Unsupported Event timing metadata")
        if metadata.get("schema", 1) == EVENT_TIMING_SCHEMA:
            return cls.from_dict(metadata["timing"])
        expression = metadata.get("expression")
        start = (
            EndpointDefinition(expression=deepcopy(expression))
            if expression
            else EndpointDefinition(instant=finite(event.lore_date))
        )
        if metadata.get("end_expression"):
            return cls(
                start,
                "independent",
                EndpointDefinition(expression=deepcopy(metadata["end_expression"])),
            )
        if event.lore_duration is not None and event.lore_duration > 0:
            return cls(start, "duration", duration_days=finite(event.lore_duration))
        return cls(start)

    def apply(self, attributes: dict[str, Any]) -> dict[str, Any]:
        """Replace timing only, preserving chronology and source evidence."""
        result = deepcopy(attributes)
        metadata = result.setdefault("_temporal_v2", {})
        if not isinstance(metadata, dict) or metadata.get("schema", 1) not in {1, 2}:
            raise ValueError("Unsupported Event timing metadata")
        metadata.pop("expression", None)
        metadata.pop("end_expression", None)
        metadata.update(schema=2, timing=self.to_dict())
        return result
