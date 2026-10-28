"""Interpret scalar API edits without overwriting authoritative endpoint sources."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any

from src.core.calendar import CalendarConverter
from src.core.event_timing.definitions import (
    EVENT_TIMING_SCHEMA,
    EndpointDefinition,
    EventTimingDefinition,
    finite,
)
from src.core.events import Event
from src.core.temporal_expression import TemporalExpression, move_expression


def normalize_scalar_patch(
    current: Event,
    patch: dict[str, Any],
    converter: CalendarConverter | None,
    *,
    preserve_timing: bool = False,
) -> dict[str, Any]:
    """Scalar callers must deliberately author a date or duration, never detach."""
    result = deepcopy(patch)
    if preserve_timing:
        if {"lore_date", "lore_duration"} & result.keys():
            raise ValueError("A content-only save cannot change Event timing")
        if "attributes" in result:
            if "_temporal_v2" in current.attributes:
                result["attributes"]["_temporal_v2"] = deepcopy(
                    current.attributes["_temporal_v2"]
                )
            else:
                result["attributes"].pop("_temporal_v2", None)
        return result
    metadata = current.attributes.get("_temporal_v2", {})
    supplied = patch.get("attributes", current.attributes)
    if supplied.get("_temporal_v2") != current.attributes.get("_temporal_v2"):
        return result
    if not isinstance(metadata, dict) or metadata.get("schema") != EVENT_TIMING_SCHEMA:
        return result
    definition = EventTimingDefinition.from_event(current)
    if "lore_date" in patch and (
        patch["lore_date"] != current.lore_date or isinstance(patch["lore_date"], bool)
    ):
        start = definition.start
        if start.kind == "event":
            raise ValueError(
                "This start follows another Event. Edit its offset or detach it explicitly."
            )
        if start.expression is not None:
            if converter is None:
                raise ValueError("The Event's calendar is unavailable")
            expression = move_expression(
                TemporalExpression.from_dict(start.expression),
                finite(patch["lore_date"]),
                converter,
            )
            start = EndpointDefinition(expression=expression.to_dict())
        else:
            start = EndpointDefinition(instant=finite(patch["lore_date"]))
        definition = replace(definition, start=start)
    if "lore_duration" in patch and (
        patch["lore_duration"] != current.lore_duration
        or isinstance(patch["lore_duration"], bool)
    ):
        definition = EventTimingDefinition(
            definition.start, "duration", duration_days=finite(patch["lore_duration"])
        )
    if "lore_date" in patch or "lore_duration" in patch:
        result["attributes"] = definition.apply(supplied)
    return result
