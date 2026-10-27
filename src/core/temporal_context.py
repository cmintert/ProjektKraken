"""Detached, immutable temporal context shared by previews and commands."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cached_property

from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.events import Event
from src.core.temporal_anchors import resolve_event_anchors
from src.core.temporal_constraints import TemporalConstraint
from src.core.temporal_expression import ResolvedTemporalBounds


@dataclass(frozen=True)
class TemporalResolutionContext:
    """Serialized sources ensure no live event/calendar object can be mutated."""

    events_json: str = "[]"
    calendar_json: str | None = None
    revision: int = 0

    @classmethod
    def build(
        cls, events: list[Event], converter: CalendarConverter | None, revision: int = 0
    ) -> TemporalResolutionContext:
        """Capture the complete authored facts, never their layout coordinates alone."""
        return cls(
            json.dumps([event.to_dict() for event in events]),
            converter._config.to_json() if converter else None,
            revision,
        )

    def converter(self) -> CalendarConverter | None:
        """Construct a private converter from the captured configuration."""
        return (
            CalendarConverter(CalendarConfig.from_json(self.calendar_json))
            if self.calendar_json
            else None
        )

    def events(self) -> list[Event]:
        """Return independent event records for presentation."""
        return [Event.from_dict(row) for row in json.loads(self.events_json)]

    def anchors(self) -> dict[str, ResolvedTemporalBounds]:
        """Resolve all endpoints once when a consumer replaces its context."""
        return dict(self._resolved_anchors)

    @cached_property
    def _resolved_anchors(self) -> tuple[tuple[str, ResolvedTemporalBounds], ...]:
        return tuple(resolve_event_anchors(self.events(), self.converter()).items())

    def constraints(self) -> tuple[TemporalConstraint, ...]:
        """Read supported chronology assertions without changing their owners."""
        result = []
        for event in self.events():
            metadata = event.attributes.get("_temporal_v2", {})
            if not isinstance(metadata, dict):
                continue
            for record in metadata.get("constraints", []):
                try:
                    result.append(TemporalConstraint.from_dict(record))
                except (ValueError, TypeError, KeyError):
                    continue  # The chronology validator reports malformed saved rules.
        return tuple(result)
