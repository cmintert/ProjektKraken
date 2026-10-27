"""Lossless temporal draft assembly and edit validation."""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from src.core.temporal_expression import MAX_LORE_DAY, TemporalExpression
from src.core.temporal_window import TemporalWindow


def supported_boundary(value: Any) -> bool:
    """Check editable structure without interpreting or rewriting future metadata."""
    if not isinstance(value, dict):
        return False
    if value.get("status", "known") not in {
        "known",
        "open",
        "unknown",
        "not_applicable",
    }:
        return False
    try:
        if "exact" in value and not math.isfinite(float(value["exact"])):
            return False
        if "expression" in value:
            TemporalExpression.from_dict(value["expression"])
        if "anchor" in value:
            anchor = value["anchor"]
            if not isinstance(anchor, dict):
                return False
            if anchor.get("endpoint", "start") not in {"start", "end"}:
                return False
            if anchor.get("relation", "at") not in {"at", "before", "after"}:
                return False
            offset = anchor.get("offset", {"unit": "days"})
            if not isinstance(offset, dict) or offset.get("unit", "days") not in {
                "days",
                "months",
                "years",
            }:
                return False
            amount = offset.get("value", anchor.get("offset_days", 0))
            if (
                amount is None
                or not math.isfinite(float(amount))
                or abs(float(amount)) > MAX_LORE_DAY
            ):
                return False
        return True
    except (ValueError, TypeError, KeyError):
        return False


def updated_spec(
    original: dict[str, Any], changes: dict[str, Any], behavior: str = "stateful"
) -> dict[str, Any]:
    """Upgrade explicit advanced edits while retaining untouched legacy meaning."""
    result = deepcopy(original)
    result.setdefault("schema", 1)
    result.setdefault("behavior", behavior)
    advanced = any(
        isinstance(v, dict)
        and isinstance(v.get("anchor"), dict)
        and "offset" in v["anchor"]
        for v in changes.values()
    )
    if advanced and result.get("schema") == 1:
        for side in ("start", "end", "at"):
            boundary = result.get(side, {})
            if isinstance(boundary, dict) and "anchor" in boundary:
                boundary["anchor"].setdefault("semantics", "legacy_v1")
        result["schema"] = 2
    result.update(
        deepcopy({key: value for key, value in changes.items() if key != "schema"})
    )
    return result


def edit_error(window: TemporalWindow) -> str | None:
    """Distinguish impossible edits from valid but unavailable historical evidence."""
    if window.is_empty:
        return "The dates describe an empty interval. Choose different start and end dates."
    if window.error and any(
        term in window.error.lower()
        for term in (
            "must be",
            "whole numbers",
            "cannot precede",
            "unsupported event boundary",
            "finite",
            "object",
            "invalid temporal boundary",
        )
    ):
        return window.error
    return None
