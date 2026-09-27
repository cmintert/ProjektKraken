"""Resolve event anchors once per immutable query snapshot."""

from dataclasses import replace

from src.core.calendar import CalendarConverter
from src.core.events import Event
from src.core.temporal_expression import (
    ResolvedTemporalBounds,
    expression_from_attributes,
)


def resolve_event_anchors(
    events: list[Event],
    converter: CalendarConverter | None,
) -> dict[str, ResolvedTemporalBounds]:
    """Keep event identity even when a calendar or expression cannot be resolved."""
    anchors = {}
    for event in events:
        anchor_id = f"event:{event.id}"
        try:
            expression = expression_from_attributes(event.attributes)
            if expression is None:
                bounds = ResolvedTemporalBounds(event.lore_date, event.lore_date)
            elif converter is None:
                bounds = ResolvedTemporalBounds(
                    error="The event's calendar is unavailable."
                )
            else:
                bounds = expression.resolve_bounds(converter)
        except (ValueError, TypeError, KeyError) as exc:
            bounds = ResolvedTemporalBounds(error=str(exc))
        anchors[anchor_id] = replace(
            bounds,
            anchor_id=anchor_id,
            label=f"{event.name}: {bounds.label}" if bounds.label else event.name,
        )
    return anchors


def event_position_at(
    event: Event,
    lore_time: float,
    converter: CalendarConverter | None,
) -> tuple[bool, bool]:
    """Return definitely future/past flags without using an uncertain midpoint."""
    bounds = resolve_event_anchors([event], converter)[f"event:{event.id}"]
    if bounds.error:
        return False, False
    return (
        bounds.hard_start is not None and bounds.hard_start > lore_time,
        bounds.hard_end is not None
        and (
            bounds.hard_end < lore_time
            if bounds.hard_start == bounds.hard_end
            else bounds.hard_end <= lore_time
        ),
    )
