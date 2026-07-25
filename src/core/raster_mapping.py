"""Pure raster value-to-world-object mapping helpers."""

from __future__ import annotations

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


def make_empty_vem(mode: str = "exact") -> dict[str, Any]:
    """Return an empty canonical value/entity mapping."""
    return {"mode": mode, "mappings": []}


def normalize_value_entity_map(value: Any) -> dict[str, Any]:
    """Normalize legacy flat maps and current structured mappings."""
    if not value:
        return make_empty_vem()
    if not isinstance(value, dict):
        logger.warning("Ignoring invalid raster mapping type: %s", type(value))
        return make_empty_vem()
    if "mappings" in value:
        mappings = []
        for raw in value.get("mappings", []):
            item = dict(raw)
            item.setdefault("id", str(uuid.uuid4()))
            mappings.append(item)
        return {"mode": value.get("mode", "exact"), "mappings": mappings}

    mappings = []
    for raw_value, entity_id in value.items():
        try:
            numeric_value = int(raw_value)
        except (TypeError, ValueError):
            continue
        mappings.append(
            {
                "id": str(uuid.uuid4()),
                "value": numeric_value,
                "entity_id": entity_id
                if isinstance(entity_id, str)
                else None,
                "label": "",
            }
        )
    return {"mode": "exact", "mappings": mappings}


def validate_no_overlaps(value: dict[str, Any]) -> list[str]:
    """Return descriptions of overlapping exact values or ranges."""
    mode = value.get("mode", "exact")
    intervals: list[tuple[int, int, str]] = []
    for mapping in value.get("mappings", []):
        label = mapping.get("label") or str(
            mapping.get("value", mapping.get("min", "?"))
        )
        if mode == "exact" and mapping.get("value") is not None:
            point = int(mapping["value"])
            intervals.append((point, point, label))
        elif (
            mode != "exact"
            and mapping.get("min") is not None
            and mapping.get("max") is not None
        ):
            intervals.append(
                (int(mapping["min"]), int(mapping["max"]), label)
            )

    errors: list[str] = []
    for index, (low, high, label) in enumerate(intervals):
        for other_low, other_high, other_label in intervals[index + 1 :]:
            if low <= other_high and other_low <= high:
                errors.append(
                    f"Mapping '{label}' ({low}–{high}) overlaps "
                    f"'{other_label}' ({other_low}–{other_high})."
                )
    return errors


def lookup_label_for_value(
    layer_metadata: dict[str, Any], value: int
) -> str | None:
    """Resolve a raster value to its exact/range mapping label."""
    mapping = normalize_value_entity_map(
        layer_metadata.get("value_entity_map")
    )
    mode = mapping.get("mode", "exact")
    for entry in mapping.get("mappings", []):
        try:
            matches = (
                int(entry.get("value")) == value
                if mode == "exact"
                else int(entry.get("min")) <= value <= int(entry.get("max"))
            )
        except (TypeError, ValueError):
            continue
        if matches:
            label = entry.get("label")
            return str(label) if label else None
    return None
