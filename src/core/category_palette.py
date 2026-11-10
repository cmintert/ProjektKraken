"""Stable category assignments; the theme owns all display colors."""

import hashlib

CATEGORY_ROLES = tuple(f"category_{index}" for index in range(8))
_STANDARD_CATEGORIES = {
    "character": 0,
    "person": 0,
    "location": 1,
    "place": 1,
    "faction": 2,
    "organization": 2,
    "item": 3,
    "object": 3,
    "concept": 4,
    "species": 5,
    "event": 6,
    "generic": 7,
}


def category_role(item_kind: str, category: str) -> str:
    """Return a stable role without depending on which types are currently visible."""
    normalized = category.strip().casefold()
    index = _STANDARD_CATEGORIES.get(normalized)
    if index is None:
        seed = f"{item_kind}:{normalized}".encode()
        index = int.from_bytes(hashlib.sha256(seed).digest()[:4]) % len(CATEGORY_ROLES)
    return CATEGORY_ROLES[index]
