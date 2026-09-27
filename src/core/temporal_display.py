"""Evidence-based timeline extents, independent of representative coordinates."""

from dataclasses import dataclass

from src.core.calendar import CalendarConverter
from src.core.events import Event
from src.core.temporal_expression import (
    ResolvedTemporalBounds,
    TemporalExpression,
    expression_from_attributes,
)


@dataclass(frozen=True)
class TemporalDisplay:
    """Possible extent and certainly occupied interior; None means unbounded."""

    possible_start: float | None
    possible_end: float | None
    certain_start: float | None = None
    certain_end: float | None = None
    caption: str = "Timing unresolved"


def event_temporal_display(
    event: Event, converter: CalendarConverter | None
) -> TemporalDisplay | None:
    """Project evidence without converting a layout midpoint into a start date."""
    metadata = event.attributes.get("_temporal_v2", {})
    if not metadata.get("expression") and not metadata.get("end_expression"):
        return None
    try:
        expression = expression_from_attributes(event.attributes)
        if converter is None:
            return TemporalDisplay(
                None, None, caption="Calendar unavailable; timing unresolved"
            )
        start = (
            expression.resolve_bounds(converter)
            if expression
            else ResolvedTemporalBounds(event.lore_date, event.lore_date)
        )
        text = (
            expression.display_text(converter)
            if expression
            else converter.format_date(event.lore_date)
        )
        end_data = metadata.get("end_expression")
        if start.error:
            return TemporalDisplay(None, None, caption=start.error)
        if not end_data and event.lore_duration <= 0:
            return TemporalDisplay(
                start.hard_start,
                start.hard_end,
                caption=f"Occurrence: {text} · exact date unknown",
            )
        if end_data:
            end_expression = TemporalExpression.from_dict(end_data)
            end = end_expression.resolve_bounds(converter)
            caption = f"Starts: {text} · Ends: {end_expression.display_text(converter)}"
        else:
            duration = event.lore_duration
            end = ResolvedTemporalBounds(
                None if start.hard_start is None else start.hard_start + duration,
                None if start.hard_end is None else start.hard_end + duration,
            )
            caption = f"Starts: {text} · Duration: {duration:g} days"
        if end.error:
            return TemporalDisplay(None, None, caption=end.error)
        certain_start, certain_end = start.hard_end, end.hard_start
        if certain_start is None or certain_end is None or certain_end <= certain_start:
            certain_start = certain_end = None
        return TemporalDisplay(
            start.hard_start, end.hard_end, certain_start, certain_end, caption
        )
    except (ValueError, TypeError, KeyError) as exc:
        return TemporalDisplay(None, None, caption=f"Timing unresolved: {exc}")
