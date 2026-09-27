"""Centralize semantic event coordinates and precision-preserving moves."""

from dataclasses import replace

from src.core.calendar import CalendarConverter
from src.core.events import Event
from src.core.temporal_expression import (
    TEMPORAL_ATTRIBUTE,
    TemporalExpression,
    expression_from_attributes,
    move_expression,
)


def move_temporal_event(
    event: Event, target: float, converter: CalendarConverter
) -> Event:
    """Move in the author's component precision without fabricating components."""
    expression = expression_from_attributes(event.attributes)
    if expression is None:
        return replace(event, lore_date=target)
    moved = move_expression(expression, target, converter)
    attributes = {
        **event.attributes,
        TEMPORAL_ATTRIBUTE: {
            **event.attributes.get(TEMPORAL_ATTRIBUTE, {}),
            "schema": 1,
            "expression": moved.to_dict(),
        },
    }
    duration = event.lore_duration
    metadata = attributes[TEMPORAL_ATTRIBUTE]
    if metadata.get("end_expression"):
        end = TemporalExpression.from_dict(metadata["end_expression"])
        delta = moved.representative_time(converter) - expression.representative_time(
            converter
        )
        end = move_expression(
            end, end.representative_time(converter) + delta, converter
        )
        metadata["end_expression"] = end.to_dict()
        duration = max(
            0.0,
            end.representative_time(converter) - moved.representative_time(converter),
        )
    return replace(
        event,
        attributes=attributes,
        lore_date=moved.representative_time(converter),
        lore_duration=duration,
    )
