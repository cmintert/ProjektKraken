"""Lossless compound offsets, applied in years, months, then lore days."""

from __future__ import annotations

import math
from typing import Any

MAX_OFFSET_COMPONENT = 1e12


def offset_steps(offset: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Validate compound magnitudes and expand the explicit direction once."""
    if offset.get("unit") != "compound":
        return (offset,)
    if set(offset) - {"unit", "direction", "years", "months", "days", "calendar_id"}:
        raise ValueError("Unsupported compound offset fields")
    direction = offset.get("direction")
    if isinstance(direction, bool) or direction not in {-1, 1}:
        raise ValueError("Choose an offset direction")
    steps = []
    for unit in ("years", "months", "days"):
        raw = offset.get(unit, 0)
        value = float(raw)
        if (
            isinstance(raw, bool)
            or not math.isfinite(value)
            or not 0 <= value <= MAX_OFFSET_COMPONENT
        ):
            raise ValueError("Offset components must be between zero and 10^12")
        if unit != "days" and not value.is_integer():
            raise ValueError("Calendar offsets require whole units")
        if value:
            if unit != "days" and not offset.get("calendar_id"):
                raise ValueError("Calendar offsets require a calendar")
            steps.append(
                {
                    "unit": unit,
                    "value": direction * value,
                    "calendar_id": offset.get("calendar_id"),
                }
            )
    return tuple(steps) or ({"unit": "days", "value": 0.0},)
