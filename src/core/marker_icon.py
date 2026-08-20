"""Stable metadata describing marker icon artwork."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Mapping

from src.core.marker_appearance import MarkerIconAnchor

DEFAULT_MARKER_ICON_ID = "map.pin"
DEFAULT_NATIVE_DIAMETER_PX = 50.0


class MarkerIconSource(str, Enum):
    """Where a marker icon asset originates."""

    DEFAULT = "default"
    CUSTOM = "custom"


@dataclass(frozen=True)
class MarkerIconDefinition:
    """Format-independent identity and rendering defaults for one icon."""

    id: str
    name: str
    asset_path: str
    source: MarkerIconSource
    default_native_diameter_px: float = DEFAULT_NATIVE_DIAMETER_PX
    anchor: MarkerIconAnchor = field(default_factory=MarkerIconAnchor)
    category: str | None = None

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
        *,
        source: MarkerIconSource | None = None,
    ) -> "MarkerIconDefinition":
        """Build a validated definition from manifest-style data."""
        icon_id = _required_text(payload.get("id"), "id")
        name = _required_text(payload.get("name"), "name")
        asset_path = _safe_relative_path(payload.get("asset_path"))
        resolved_source = source or MarkerIconSource(
            payload.get("source", MarkerIconSource.DEFAULT.value)
        )
        anchor_payload = payload.get("anchor")
        anchor = (
            MarkerIconAnchor.from_dict(anchor_payload)
            if isinstance(anchor_payload, Mapping)
            else MarkerIconAnchor()
        )
        category_value = payload.get("category")
        category = (
            category_value.strip()
            if isinstance(category_value, str) and category_value.strip()
            else None
        )
        return cls(
            id=icon_id,
            name=name,
            asset_path=asset_path,
            source=resolved_source,
            default_native_diameter_px=_positive_float(
                payload.get("default_native_diameter_px"),
                DEFAULT_NATIVE_DIAMETER_PX,
            ),
            anchor=anchor,
            category=category,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""
        payload: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "asset_path": self.asset_path,
            "source": self.source.value,
            "default_native_diameter_px": self.default_native_diameter_px,
            "anchor": self.anchor.to_dict(),
        }
        if self.category is not None:
            payload["category"] = self.category
        return payload


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Marker icon {field_name} must be a non-empty string")
    return value.strip()


def _safe_relative_path(value: Any) -> str:
    path_text = _required_text(value, "asset_path").replace("\\", "/")
    path = PurePosixPath(path_text)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Marker icon asset_path must stay within its asset root")
    return path.as_posix()


def _positive_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed) or parsed <= 0:
        return default
    return parsed
