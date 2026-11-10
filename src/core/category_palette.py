"""World-owned type identities and stable assignments to theme palette slots."""

import json
from collections import Counter
from collections.abc import Iterable, Mapping

CATEGORY_ROLES = tuple(f"category_{index}" for index in range(24))
# Palette entries are ordered by offline maximin perceptual spacing across themes.
CATEGORY_ORDER = tuple(range(len(CATEGORY_ROLES)))
_IDENTITY_SIZE = 2


def category_key(item_kind: str, category: str) -> str:
    """Keep exact authored type identity and kind without delimiter ambiguity."""
    if item_kind not in {"entity", "event"} or not isinstance(category, str):
        raise ValueError("Unsupported category identity")
    return json.dumps([item_kind, category], ensure_ascii=False, separators=(",", ":"))


def assign_categories(
    saved: Mapping[str, int], categories: Iterable[tuple[str, str]]
) -> dict[str, int]:
    """Allocate unused slots first; retain inactive assignments for undo/re-add."""
    result = dict(saved)
    for key, slot in result.items():
        identity = json.loads(key)
        if (
            not isinstance(identity, list)
            or len(identity) != _IDENTITY_SIZE
            or category_key(*identity) != key
            or type(slot) is not int
            or not 0 <= slot < len(CATEGORY_ROLES)
        ):
            raise ValueError("Invalid saved type color assignment")
    counts = Counter(result.values())
    for key in sorted({category_key(*category) for category in categories}):
        if key in result:
            continue
        slot = min(CATEGORY_ORDER, key=lambda candidate: counts[candidate])
        result[key] = slot
        counts[slot] += 1
    return result


def category_role(
    item_kind: str, category: str, assignments: Mapping[str, int]
) -> str | None:
    """Render a supplied slot; a missing snapshot retains object identity color."""
    slot = assignments.get(category_key(item_kind, category))
    return CATEGORY_ROLES[slot] if slot is not None else None
