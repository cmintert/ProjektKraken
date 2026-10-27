"""Resolve event anchors once per immutable query snapshot."""

import math
from dataclasses import replace

from src.core.calendar import CalendarConverter
from src.core.events import Event
from src.core.temporal_expression import (
    ResolvedTemporalBounds,
    TemporalExpression,
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
                coordinate = float(event.lore_date)
                if not math.isfinite(coordinate):
                    raise ValueError("Event date must be finite")
                bounds = ResolvedTemporalBounds(coordinate, coordinate)
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
            base_anchor=anchor_id,
            transition=(anchor_id, "days", "0x0.0p+0"),
            upper_inclusive=bounds.hard_start == bounds.hard_end,
            label=f"{event.name}: {bounds.label}" if bounds.label else event.name,
        )
        anchors[f"{anchor_id}:end"] = _event_end(event, anchors[anchor_id], converter)
    return anchors


def _event_end(
    event: Event, start: ResolvedTemporalBounds, converter: CalendarConverter | None
) -> ResolvedTemporalBounds:
    """Prefer the independently authored end over any representative duration."""
    identity = f"event:{event.id}:end"
    try:
        metadata = event.attributes.get("_temporal_v2", {})
        if not isinstance(metadata, dict):
            raise ValueError("Unsupported temporal metadata")
        if metadata.get("end_expression"):
            end = (
                TemporalExpression.from_dict(metadata["end_expression"]).resolve_bounds(
                    converter
                )
                if converter
                else ResolvedTemporalBounds(error="Calendar unavailable.")
            )
            return replace(
                end,
                anchor_id=identity,
                base_anchor=identity,
                transition=(identity, "days", "0x0.0p+0"),
                label=f"{event.name} — end: {end.label or 'Date unknown'}",
            )
        duration = float(event.lore_duration)
        if math.isfinite(duration) and duration > 0:
            from src.core.temporal_shift import shift_anchor

            return replace(
                shift_anchor(start, {"offset_days": duration}, converter),
                label=f"{event.name} — end ({duration:g} days after start)",
            )
        return ResolvedTemporalBounds(
            anchor_id=identity,
            error="This event has no authored end.",
            label=f"{event.name} — end",
        )
    except (ValueError, TypeError, KeyError) as exc:
        return ResolvedTemporalBounds(anchor_id=identity, error=str(exc))


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
