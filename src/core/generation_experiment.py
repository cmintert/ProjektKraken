"""Pure prompt variants retaining immutable experiment evidence."""

import hashlib
import json
from typing import Any

from src.core.mcp_access import McpFailure

MAX_VARIANT_CHARS = 8000


def fingerprint(value: Any) -> str:
    """Hash detached evidence deterministically."""
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def render_variant(
    baseline: dict[str, str],
    blocks: dict[str, str],
    variant: dict[str, Any],
) -> dict[str, str]:
    """Reorder whole immutable blocks with temporary surrounding instructions."""
    if not variant:
        return dict(baseline)
    if set(variant) - {"order", "headings", "instruction", "separator"}:
        raise McpFailure("INVALID_INPUT")
    order = variant.get("order", list(blocks))
    headings = variant.get("headings", {})
    instruction = variant.get("instruction", "")
    separator = variant.get("separator", "\n\n")
    if (
        not isinstance(order, list)
        or any(not isinstance(key, str) for key in order)
        or len(order) != len(blocks)
        or set(order) != set(blocks)
        or not isinstance(headings, dict)
        or set(headings) - set(blocks)
        or any(not isinstance(value, str) for value in headings.values())
        or not isinstance(instruction, str)
        or not isinstance(separator, str)
        or len(json.dumps(variant)) > MAX_VARIANT_CHARS
    ):
        raise McpFailure("INVALID_INPUT")
    parts = [headings.get(key, "") + "\n" + blocks[key] for key in order]
    return {
        "system": baseline["system"],
        "user": separator.join(parts) + "\n\n" + instruction,
    }
