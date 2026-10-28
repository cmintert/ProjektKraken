"""Read imported authored timing without inventing dates for references."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.core.event_timing.definitions import (
    EVENT_TIMING_SCHEMA,
    EventTimingDefinition,
    finite,
)


def imported_coordinates(
    data: dict[str, Any], parser: Callable[..., tuple[float, float, bool]], result: Any
) -> tuple[float | None, float | None, bool]:
    """Keep reference-only and future records nullable until world resolution."""
    metadata = data.get("attributes", {}).get("_temporal_v2", {})
    if isinstance(metadata, dict) and metadata.get("schema", 1) != 1:
        if metadata.get("schema") == EVENT_TIMING_SCHEMA:
            EventTimingDefinition.from_dict(metadata["timing"])
        return None, None, True
    date, duration, explicit = parser(data.get("lore_date"), result)
    return date, duration or finite(data.get("lore_duration") or 0), explicit


def prepare_merge_timing(
    data: dict[str, Any], parser: Callable[..., tuple[float, float, bool]], result: Any
) -> bool | None:
    """Normalize only supplied timing, leaving absent scalar fields untouched."""
    metadata = data.get("attributes", {}).get("_temporal_v2", {})
    if "lore_date" not in data and not metadata.get("timing"):
        data["lore_date"] = None
        return None
    date, duration, explicit = imported_coordinates(data, parser, result)
    data["lore_date"] = date
    if duration is not None:
        data["lore_duration"] = duration
    return explicit
