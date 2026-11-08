"""Copy public factual values without internal or path-bearing metadata."""

import math
from typing import Any

_HIDDEN_KEYS = frozenset(
    {
        "attachments",
        "path",
        "file_path",
        "assets_dir",
        "image_path",
        "api_key",
        "password",
        "token",
        "secret",
        "credentials",
    }
)


def _restricted_name(name: str) -> bool:
    normalized = name.casefold().replace(" ", "_").replace("-", "_")
    return (
        normalized.startswith("_")
        or normalized in _HIDDEN_KEYS
        or any(
            marker in normalized
            for marker in (
                "path",
                "credential",
                "api_key",
                "password",
                "secret",
                "token",
            )
        )
    )


def _restricted_attribute(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and "value" in value
        and _restricted_name(str(value.get("name", "")))
    )


def public_projection(value: Any) -> Any:
    """Copy bounded factual values, removing internal and path-bearing metadata."""
    if isinstance(value, dict):
        if _restricted_attribute(value):
            return None
        return {
            str(key): public_projection(item)
            for key, item in value.items()
            if not _restricted_name(str(key))
        }
    if isinstance(value, (list, tuple)):
        return [
            public_projection(item) for item in value if not _restricted_attribute(item)
        ]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value
