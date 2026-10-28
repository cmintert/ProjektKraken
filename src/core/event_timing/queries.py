"""Start-position searches over canonical detached Event projections."""

from src.core.calendar import CalendarConverter
from src.core.event_timing.projection import project_event
from src.core.event_timing.solver import resolve_world
from src.core.events import Event


def canonical_events(
    events: list[Event], converter: CalendarConverter | None
) -> list[Event]:
    """Resolve semantic records jointly, leaving raw repository records untouched."""
    if not any("_temporal_v2" in event.attributes for event in events):
        return list(events)
    result = resolve_world(events, converter)
    return sorted(
        (project_event(event, result) for event in events),
        key=lambda event: (event.date_sort_key(), event.id),
    )


def starts_in_range(events: list[Event], start: float, end: float) -> list[Event]:
    """Retain inclusive start-position search semantics; unplaced starts are absent."""
    return [
        event
        for event in events
        if event.lore_date is not None and start <= event.lore_date <= end
    ]
