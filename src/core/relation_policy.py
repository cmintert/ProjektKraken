"""Read-only safety checks for changes to authored relation endpoints."""

from collections.abc import Mapping
from typing import Any

from src.core.temporal_editing import supported_boundary


def _has_source_bound_timing(attributes: Mapping[str, Any]) -> bool:
    if any(
        attributes.get(key)
        for key in ("valid_from_event", "valid_to_event", "valid_at_event")
    ):
        return True
    temporal = attributes.get("temporal")
    if temporal is None:
        return False
    if not isinstance(temporal, Mapping) or temporal.get("schema", 1) not in (1, 2):
        return True
    if temporal.keys() - {"schema", "behavior", "start", "end", "at"}:
        return True
    return any(
        _boundary_may_depend_on_source(temporal[key])
        for key in ("start", "end", "at")
        if key in temporal
    )


def _boundary_may_depend_on_source(boundary: Any) -> bool:
    if not isinstance(boundary, Mapping):
        return True
    if boundary.keys() - {"status", "exact", "expression", "binding", "anchor"}:
        return True
    return "binding" in boundary or not supported_boundary(boundary)


def endpoint_change_error(
    saved: Mapping[str, Any],
    source_id: str,
    target_id: str,
    attributes: Mapping[str, Any],
) -> str | None:
    """Protect state-change recipients and source-bound timing on reorientation."""
    source_changed = source_id != saved["source_id"]
    target_changed = target_id != saved["target_id"]
    previous = saved.get("attributes") or {}
    if (source_changed or target_changed) and (
        previous.get("payload") or attributes.get("payload")
    ):
        return "Keep the endpoints of a relation with state changes."
    if source_changed and (
        _has_source_bound_timing(previous) or _has_source_bound_timing(attributes)
    ):
        return "Keep the source of a relation with source-event or unsupported timing."
    return None
