"""Pure prompt variants retaining immutable experiment evidence."""

import hashlib
import json
from typing import Any

from src.core.mcp_access import McpFailure

MAX_VARIANT_CHARS = 8000
MIN_OUTPUT_TOKENS = 50
MAX_OUTPUT_TOKENS = 100000


def fingerprint(value: Any) -> str:
    """Hash detached evidence deterministically."""
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _exclude_blocks(
    baseline: dict[str, str], blocks: dict[str, str], excluded: list[str]
) -> dict[str, str]:
    """Remove only exact frozen sections while retaining other message bytes."""
    result = dict(baseline)
    prefixes = {"retrieved": "[Retrieved Context]", "spatial": "[Spatial Context]"}
    for key in excluded:
        block = blocks[key]
        prefix = prefixes.get(key)
        candidates = [f"{prefix}\n{block}", block] if prefix else [block]
        for candidate in candidates:
            if result["user"].count(candidate) == 1:
                result["user"] = result["user"].replace(candidate, "", 1)
                break
        else:
            raise McpFailure("INVALID_INPUT", "AMBIGUOUS_FROZEN_BLOCK")
    return result


def render_variant(
    baseline: dict[str, str],
    blocks: dict[str, str],
    variant: dict[str, Any],
) -> dict[str, str]:
    """Reorder whole immutable blocks with temporary surrounding instructions."""
    if not variant:
        return dict(baseline)
    if set(variant) - {
        "order",
        "headings",
        "instruction",
        "separator",
        "exclude",
        "max_tokens",
    }:
        raise McpFailure("INVALID_INPUT")
    excluded = variant.get("exclude", [])
    budget = variant.get("max_tokens")
    if (
        not isinstance(excluded, list)
        or any(not isinstance(key, str) for key in excluded)
        or set(excluded) - {"authoring", "retrieved", "spatial"}
        or set(excluded) - set(blocks)
        or (
            budget is not None
            and (
                type(budget) is not int
                or not MIN_OUTPUT_TOKENS <= budget <= MAX_OUTPUT_TOKENS
            )
        )
    ):
        raise McpFailure("INVALID_INPUT")
    retained = {key: value for key, value in blocks.items() if key not in excluded}
    order = variant.get("order", list(retained))
    headings = variant.get("headings", {})
    instruction = variant.get("instruction", "")
    separator = variant.get("separator", "\n\n")
    if (
        not isinstance(order, list)
        or any(not isinstance(key, str) for key in order)
        or len(order) != len(retained)
        or set(order) != set(retained)
        or not isinstance(headings, dict)
        or set(headings) - set(blocks)
        or any(not isinstance(value, str) for value in headings.values())
        or not isinstance(instruction, str)
        or not isinstance(separator, str)
        or len(json.dumps(variant)) > MAX_VARIANT_CHARS
    ):
        raise McpFailure("INVALID_INPUT")
    if not set(variant) - {"exclude", "max_tokens"}:
        return _exclude_blocks(baseline, blocks, excluded)
    parts = [headings.get(key, "") + "\n" + blocks[key] for key in order]
    return {
        "system": baseline["system"],
        "user": separator.join(parts) + "\n\n" + instruction,
    }
