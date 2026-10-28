"""Detached, immutable temporal context shared by previews and commands."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from functools import cached_property
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.event_timing.resolution import TemporalWorldResolution

from src.core.calendar import CalendarConfig, CalendarConverter
from src.core.events import Event
from src.core.temporal_constraints import TemporalConstraint
from src.core.temporal_expression import ResolvedTemporalBounds


@dataclass(frozen=True)
class TemporalResolutionContext:
    """Serialized sources ensure no live event/calendar object can be mutated."""

    events_json: str = "[]"
    calendar_json: str | None = None
    revision: int = 0
    resolved_json: str | None = None

    @classmethod
    def build(
        cls,
        events: list[Event],
        converter: CalendarConverter | None,
        revision: int = 0,
        resolved_json: str | None = None,
    ) -> TemporalResolutionContext:
        """Capture the complete authored facts, never their layout coordinates alone."""
        return cls(
            json.dumps([event.to_dict() for event in events]),
            converter._config.to_json() if converter else None,
            revision,
            resolved_json,
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

    def view_events(self) -> list[Event]:
        """Provide detached canonical placements without changing source records."""
        from src.core.event_timing.projection import project_event

        return [project_event(event, self.resolution) for event in self.events()]

    @cached_property
    def resolution(self) -> TemporalWorldResolution:
        """Reuse one joint model for every consumer of this immutable generation."""
        from src.core.event_timing.resolution import TemporalWorldResolution
        from src.core.event_timing.solver import resolve_world

        if self.resolved_json is not None:
            return TemporalWorldResolution.from_dict(json.loads(self.resolved_json))
        return resolve_world(self.events(), self.converter())

    @cached_property
    def _resolved_anchors(self) -> tuple[tuple[str, ResolvedTemporalBounds], ...]:
        anchors = self.resolution.anchors()
        names = {f"event:{event.id}": event.name for event in self.events()}
        return tuple(
            (
                node,
                replace(
                    bounds,
                    label=names.get(node.removesuffix(":end"), node)
                    + (" — end" if node.endswith(":end") else ""),
                ),
            )
            for node, bounds in anchors.items()
        )

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
