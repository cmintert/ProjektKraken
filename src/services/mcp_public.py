"""Copy public factual values without internal or path-bearing metadata."""

import math
import re
import unicodedata
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
        "tokens",
        "secrets",
    }
)
_RESTRICTED_TOKENS = frozenset(
    {
        "path",
        "paths",
        "credential",
        "credentials",
        "password",
        "passwords",
        "secret",
        "token",
    }
)
_COMPACT_KEYS = frozenset(
    {
        "apikey",
        "privatekey",
        "clientsecret",
        "accesstoken",
        "refreshtoken",
        "authtoken",
        "filepath",
        "imagepath",
        "assetsdir",
    }
)
_SECRET_SUFFIXES = (
    "apikey",
    "password",
    "credential",
    "credentials",
    "accesstoken",
    "refreshtoken",
    "authtoken",
    "clientsecret",
    "privatekey",
)


def _restricted_name(name: str) -> bool:
    name = unicodedata.normalize("NFKC", name).strip()
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    normalized = name.casefold()
    parts = re.findall(r"[^\W_]+", normalized)
    return (
        normalized.startswith("_")
        or "_".join(parts) in _HIDDEN_KEYS
        or bool(set(parts) & (_RESTRICTED_TOKENS | _COMPACT_KEYS))
        or any(part.endswith(_SECRET_SUFFIXES) for part in parts)
        or any(
            first == "api" and second == "key"
            for first, second in zip(parts, parts[1:])
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
    removed = [0]
    result = _project(value, removed)
    if removed[0] and isinstance(result, dict):
        counts = dict(result.get("omitted_counts", {}))
        counts["restricted_fields"] = counts.get("restricted_fields", 0) + removed[0]
        result["omitted_counts"] = counts
    return result


def _project(value: Any, removed: list[int]) -> Any:
    """Count suppressed fields without publishing their names or values."""
    if isinstance(value, dict):
        if _restricted_attribute(value):
            removed[0] += 1
            return None
        result = {}
        for key, item in value.items():
            if _restricted_name(str(key)):
                removed[0] += 1
            else:
                result[str(key)] = _project(item, removed)
        return result
    if isinstance(value, (list, tuple)):
        rows = []
        for item in value:
            if _restricted_attribute(item):
                removed[0] += 1
            else:
                rows.append(_project(item, removed))
        return rows
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value
