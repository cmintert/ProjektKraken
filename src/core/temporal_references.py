"""Structural traversal of event references without rewriting authored prose."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_REFERENCE_KEYS = frozenset({"anchor_id", "anchor_a", "anchor_b"})


def event_reference_ids(value: Any) -> set[str]:
    """Collect stable event identities in persisted temporal reference fields."""
    if isinstance(value, list):
        return set().union(*(event_reference_ids(item) for item in value))
    if not isinstance(value, dict):
        return set()
    result = set()
    for key, item in value.items():
        if (
            key in _REFERENCE_KEYS
            and isinstance(item, str)
            and item.startswith("event:")
        ):
            result.add(item.removeprefix("event:"))
        result.update(event_reference_ids(item))
    return result


def remap_temporal_references(
    attributes: dict[str, Any], identities: dict[str, str]
) -> dict[str, Any]:
    """Remap known temporal schemas only; retain unsupported metadata verbatim."""
    result = deepcopy(attributes)
    for name in ("temporal", "_temporal_v2"):
        metadata = result.get(name)
        if isinstance(metadata, dict) and metadata.get("schema", 1) in {1, 2}:
            _remap(metadata, identities)
    return result


def _remap(value: Any, identities: dict[str, str]) -> None:
    if isinstance(value, list):
        for item in value:
            _remap(item, identities)
    elif isinstance(value, dict):
        for key, item in value.items():
            if (
                key in _REFERENCE_KEYS
                and isinstance(item, str)
                and item.startswith("event:")
            ):
                original = item.removeprefix("event:")
                if original in identities:
                    value[key] = f"event:{identities[original]}"
            else:
                _remap(item, identities)
