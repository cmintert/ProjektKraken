"""Resolve event anchors once per immutable query snapshot."""

from src.core.calendar import CalendarConverter
from src.core.events import Event
from src.core.temporal_expression import (
    ResolvedTemporalBounds,
)


def resolve_event_anchors(
    events: list[Event],
    converter: CalendarConverter | None,
) -> dict[str, ResolvedTemporalBounds]:
    """Keep event identity even when a calendar or expression cannot be resolved."""
    from src.core.event_timing.solver import resolve_world

    return resolve_world(events, converter).anchors()


def event_position_at(
    event: Event,
    lore_time: float,
    converter: CalendarConverter | None,
    anchors: dict[str, ResolvedTemporalBounds] | None = None,
) -> tuple[bool, bool]:
    """Return definitely future/past flags without using an uncertain midpoint."""
    bounds = (
        anchors if anchors is not None else resolve_event_anchors([event], converter)
    )[f"event:{event.id}"]
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
