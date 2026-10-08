"""Independent occurrence, authored length and presence for presentation."""

from dataclasses import dataclass, replace

from src.core.calendar import CalendarConverter
from src.core.events import Event
from src.core.temporal_display import TemporalDisplay, event_temporal_display
from src.core.temporal_expression import TemporalPrecision, TemporalQualifier


def is_precise_occurrence(display: TemporalDisplay) -> bool:
    """Identify precise points without promoting a layout anchor to evidence."""
    return (
        not display.error
        and not display.explicit_window
        and display.possible_start is not None
        and display.possible_end is not None
        and display.qualifier
        in {TemporalQualifier.ASSERTED, TemporalQualifier.CALCULATED}
        and display.precision
        in {None, TemporalPrecision.MINUTE, TemporalPrecision.SECOND}
    )


@dataclass(frozen=True)
class TemporalPresentation:
    """Three independent channels; presence retains its existing contract."""

    start: TemporalDisplay
    end: TemporalDisplay | None
    authored_duration: float | None
    presence: TemporalDisplay

    @property
    def layered(self) -> bool:
        """Show separate rows for uncertain starts or independent endpoints."""
        return not self.presence.error and (
            self.end is not None
            or (
                self.authored_duration is not None
                and not is_precise_occurrence(self.start)
            )
        )


def event_temporal_presentation(
    event: Event, converter: CalendarConverter | None
) -> TemporalPresentation:
    """Resolve presentation through existing semantics, without modifying data."""
    metadata = event.attributes.get("_temporal_v2", {})
    start_metadata = {**metadata}
    end_data = start_metadata.pop("end_expression", None)
    start_event = replace(
        event,
        lore_duration=0,
        attributes={**event.attributes, "_temporal_v2": start_metadata},
    )
    start = event_temporal_display(start_event, converter)
    end = None
    if end_data:
        end_event = replace(
            start_event,
            attributes={"_temporal_v2": {"schema": 1, "expression": end_data}},
        )
        end = event_temporal_display(end_event, converter)
    return TemporalPresentation(
        start,
        end,
        event.lore_duration if event.lore_duration > 0 and not end_data else None,
        event_temporal_display(event, converter),
    )


def event_navigation_context(
    event: Event, converter: CalendarConverter | None
) -> dict[str, object]:
    """Return a serializable description of an event navigation target."""
    start = event_temporal_presentation(event, converter).start
    return {
        "event_id": event.id,
        "name": event.name,
        "caption": start.caption,
        "uncertain": not is_precise_occurrence(start),
        "unresolved": start.error,
        "time": event.lore_date,
    }
