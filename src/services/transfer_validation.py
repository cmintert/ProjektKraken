"""Validate supplied structures before any import materialization or projection."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from src.core.event_timing.definitions import EVENT_TIMING_SCHEMA, EventTimingDefinition
from src.core.recurrence import RECURRENCE_ATTRIBUTE, RecurrenceRule
from src.core.temporal_boundary_resolver import BoundaryResolver
from src.core.temporal_expression import MAX_LORE_DAY, TemporalExpression
from src.core.temporal_state import validate_payload

if TYPE_CHECKING:
    from src.services.import_service import ImportService


def validate_temporal(attributes: dict[str, Any]) -> None:
    """Validate supported timing definitions, retaining opaque future versions."""
    metadata = attributes.get("_temporal_v2")
    if metadata is None:
        return
    if not isinstance(metadata, dict):
        raise ValueError("Temporal metadata must be a JSON object.")
    if metadata.get("schema", 1) == EVENT_TIMING_SCHEMA:
        EventTimingDefinition.from_dict(metadata["timing"])
    elif metadata.get("schema", 1) == 1:
        for key in ("expression", "end_expression"):
            if key in metadata:
                TemporalExpression.from_dict(metadata[key])


def validate_window(attributes: dict[str, Any]) -> None:
    """Validate known boundary shapes even when their references are unresolved."""
    window = attributes.get("temporal")
    if window is None:
        for key in ("valid_from", "valid_to"):
            value = attributes.get(key)
            if value is not None and (
                isinstance(value, bool) or not math.isfinite(float(value))
            ):
                raise ValueError(f"{key} must be a finite day coordinate or null.")
        start, end = attributes.get("valid_from"), attributes.get("valid_to")
        if (
            start is not None
            and end is not None
            and not attributes.get("valid_from_event")
            and not attributes.get("valid_to_event")
            and float(start) >= float(end)
        ):
            raise ValueError("Temporal interval start must be before its end.")
        return
    if not isinstance(window, dict):
        raise ValueError("Temporal relation metadata must be a JSON object.")
    if window.get("schema", 1) not in {1, 2}:
        return
    resolver = BoundaryResolver(None, {}, None, None, {})
    for key in ("at", "start", "end"):
        if key in window:
            boundary = window[key]
            resolver.boundary(boundary)
            if "expression" in boundary:
                TemporalExpression.from_dict(boundary["expression"])


def validate_record(kind: str, row: dict[str, Any], parser: ImportService) -> list[str]:
    """Normalize text timing only after outer types and assertions are valid."""
    errors: list[str] = []
    if kind != "relations" and (
        not isinstance(row.get("name"), str) or not row["name"].strip()
    ):
        errors.append("A name is required.")
    attributes = row.get("attributes", {})
    if not isinstance(attributes, dict):
        return errors + ["Attributes must be a JSON object."]
    if "tags" in row and (
        not isinstance(row["tags"], list)
        or any(not isinstance(tag, str) for tag in row["tags"])
    ):
        errors.append("Tags must be a JSON list of names.")
    try:
        if kind == "events" and RECURRENCE_ATTRIBUTE in attributes:
            recurrence = attributes[RECURRENCE_ATTRIBUTE]
            if not isinstance(recurrence, dict):
                raise ValueError("Recurrence metadata must be a JSON object.")
            if recurrence.get("schema", 1) == 1:
                RecurrenceRule.from_dict(recurrence)
        validate_temporal(attributes)
        validate_window(attributes)
        if "payload" in attributes:
            validate_payload(attributes["payload"])
        validate_duration(row)
        if kind == "events" and not errors:
            normalize_event(row, parser)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        errors.append(str(exc))
    return errors


def validate_duration(row: dict[str, Any]) -> None:
    """Reject invalid assertions before a projection can clamp their values."""
    duration = row.get("lore_duration")
    if duration is not None and (
        isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or not math.isfinite(duration)
        or duration < 0
    ):
        raise ValueError("Duration must be a nonnegative finite number of days.")


def normalize_event(row: dict[str, Any], parser: ImportService) -> None:
    """Preserve a string's authored meaning rather than coercing it to days."""
    metadata = row.get("attributes", {}).get("_temporal_v2")
    if metadata is not None:
        return
    value = row.get("lore_date")
    if isinstance(value, str) and value.strip():
        if parser._db.get_active_calendar_config() is None:
            raise ValueError(
                "Choose an active world calendar before importing text dates."
            )
        normalized = parser._preserve_temporal_input(row)
        if "_temporal_v2" not in normalized.get("attributes", {}):
            raise ValueError(f"Invalid date {value!r}.")
        row.update(normalized)
    elif (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or abs(value) > MAX_LORE_DAY
    ):
        raise ValueError(
            "An event date must be supported finite days or authored text."
        )
