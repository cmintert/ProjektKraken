"""Evidence-based timeline extents, independent of representative coordinates."""

from dataclasses import dataclass
from typing import Literal

from src.core.calendar import CalendarConverter
from src.core.events import Event
from src.core.temporal_expression import (
    ResolvedTemporalBounds,
    TemporalExpression,
    TemporalPrecision,
    TemporalQualifier,
    expression_from_attributes,
)


@dataclass(frozen=True)
class TemporalDisplay:
    """One evidence projection for legacy and authored timeline events."""

    possible_start: float | None
    possible_end: float | None
    certain_start: float | None = None
    certain_end: float | None = None
    caption: str = "Timing unresolved"
    kind: Literal["point", "duration"] = "point"
    precision: TemporalPrecision | None = None
    qualifier: TemporalQualifier = TemporalQualifier.ASSERTED
    anchor: float = 0.0
    explicit_window: bool = False
    error: bool = False


def event_temporal_display(
    event: Event, converter: CalendarConverter | None
) -> TemporalDisplay:
    """Project all events without converting a layout anchor into evidence."""
    metadata = event.attributes.get("_temporal_v2", {})
    is_duration = event.lore_duration > 0 or bool(metadata.get("end_expression"))
    kind: Literal["point", "duration"] = "duration" if is_duration else "point"
    if not metadata.get("expression") and not metadata.get("end_expression"):
        try:
            caption = (
                converter.format_date(event.lore_date)
                if converter is not None
                else f"{event.lore_date:,.1f}"
            )
        except (ValueError, TypeError, IndexError, OverflowError):
            caption = f"{event.lore_date:,.1f}"
        if is_duration:
            legacy_end = event.lore_date + event.lore_duration
            return TemporalDisplay(
                event.lore_date,
                legacy_end,
                event.lore_date,
                legacy_end,
                f"Starts: {caption} · Duration: {event.lore_duration:g} days",
                kind=kind,
                anchor=event.lore_date,
            )
        return TemporalDisplay(
            event.lore_date,
            event.lore_date,
            caption=caption,
            anchor=event.lore_date,
        )
    try:
        expression = expression_from_attributes(event.attributes)
        if converter is None:
            return TemporalDisplay(
                None,
                None,
                caption="Calendar unavailable; timing unresolved",
                kind=kind,
                anchor=event.lore_date,
                error=True,
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
            return TemporalDisplay(
                None,
                None,
                caption=start.error,
                kind=kind,
                anchor=event.lore_date,
                error=True,
            )
        anchor = (
            expression.representative_time(converter)
            if expression is not None
            else event.lore_date
        )
        if not end_data and event.lore_duration <= 0:
            day_is_known = expression is None or (
                expression.precision
                in {
                    TemporalPrecision.DAY,
                    TemporalPrecision.HOUR,
                    TemporalPrecision.MINUTE,
                    TemporalPrecision.SECOND,
                }
                and expression.qualifier
                in {TemporalQualifier.ASSERTED, TemporalQualifier.CALCULATED}
                and expression.explicit_outer_start is None
                and expression.explicit_outer_end is None
            )
            return TemporalDisplay(
                start.hard_start,
                start.hard_end,
                caption=(text if day_is_known else f"{text} · exact date unknown"),
                precision=expression.precision if expression else None,
                qualifier=expression.qualifier
                if expression
                else TemporalQualifier.ASSERTED,
                anchor=anchor,
                explicit_window=bool(
                    expression
                    and (
                        expression.explicit_outer_start is not None
                        or expression.explicit_outer_end is not None
                    )
                ),
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
            return TemporalDisplay(
                None,
                None,
                caption=end.error,
                kind=kind,
                anchor=event.lore_date,
                error=True,
            )
        certain_start, certain_end = start.hard_end, end.hard_start
        if certain_start is None or certain_end is None or certain_end <= certain_start:
            certain_start = certain_end = None
        return TemporalDisplay(
            start.hard_start,
            end.hard_end,
            certain_start,
            certain_end,
            caption,
            kind=kind,
            precision=expression.precision if expression else None,
            qualifier=expression.qualifier
            if expression
            else TemporalQualifier.ASSERTED,
            anchor=anchor,
        )
    except (ValueError, TypeError, KeyError) as exc:
        return TemporalDisplay(
            None,
            None,
            caption=f"Timing unresolved: {exc}",
            kind=kind,
            anchor=event.lore_date,
            error=True,
        )
