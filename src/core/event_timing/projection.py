"""Calculated Event views and compatibility snapshots, independent of storage."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any

from src.core.event_timing.definitions import EVENT_TIMING_SCHEMA, EventTimingDefinition
from src.core.event_timing.resolution import EndpointResolution, TemporalWorldResolution
from src.core.events import Event


def endpoint_signature(endpoint: EndpointResolution | None) -> Any:
    """Describe ranges, failures and joint identity using JSON-safe values."""
    if endpoint is None:
        return None
    return {
        "ranges": [
            (str(item.lower), str(item.upper), item.lower_closed, item.upper_closed)
            for item in endpoint.ranges
        ],
        "coordinate": endpoint.coordinate,
        "error": endpoint.error,
        "verified": endpoint.verified,
        "network": endpoint.provenance[0] if endpoint.provenance else None,
        "root": (
            endpoint.authored.base_anchor,
            endpoint.authored.day_offset,
            endpoint.authored.transition,
        ),
    }


def project_event(event: Event, result: TemporalWorldResolution) -> Event:
    """Return a detached view while retaining every authored timing assertion."""
    start = result.endpoints[f"event:{event.id}"]
    try:
        definition = EventTimingDefinition.from_event(event)
    except (ValueError, TypeError, KeyError):
        return replace(event, lore_date=None, lore_duration=None)
    # Schema-1 numeric values remain authored legacy instants. Semantic evidence
    # and schema-2 timing can safely receive calculated compatibility values.
    semantic = (
        bool(event.attributes.get("_temporal_v2", {}).get("expression"))
        or event.attributes.get("_temporal_v2", {}).get("schema") == EVENT_TIMING_SCHEMA
    )
    date = start.coordinate if semantic else event.lore_date
    duration = (
        definition.duration_days
        if definition.end_mode == "duration"
        else result.exact_duration(event.id)
    )
    if definition.end_mode == "none":
        duration = 0.0
    attributes = deepcopy(event.attributes)
    metadata = attributes.setdefault("_temporal_v2", {})
    metadata["projection"] = {
        "definition": definition.to_dict(),
        "calendar_json": result.calendar_json,
        "start": _presentation_endpoint(start, result),
        "end": _presentation_endpoint(
            result.endpoints.get(f"event:{event.id}:end"), result
        ),
        "duration": duration,
        "has_end": definition.end_mode != "none",
        "duration_authored": definition.end_mode == "duration",
    }
    return replace(event, lore_date=date, lore_duration=duration, attributes=attributes)


def _presentation_endpoint(
    endpoint: EndpointResolution | None, result: TemporalWorldResolution
) -> Any:
    """Carry authored meaning through references without classifying appearance."""
    if endpoint is None:
        return None
    snapshot = endpoint_signature(endpoint)
    node = endpoint.identity
    seen: set[str] = set()
    while node in result.definitions and node not in seen:
        seen.add(node)
        definition = result.definitions[node]
        if definition.kind == "manual":
            snapshot["meaning"] = {
                "expression": deepcopy(definition.expression),
                "instant": definition.instant,
                "derived": node != endpoint.identity,
            }
            break
        node = definition.source
    snapshot.setdefault("meaning", {})
    return snapshot
