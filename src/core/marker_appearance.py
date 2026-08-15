"""Validated, serializable appearance settings for point markers."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping

from src.core.marker_sizing import MARKER_SIZING_ATTRIBUTE, MarkerSizingSettings
from src.core.style_constants import (
    MAX_BORDER_WIDTH,
    MAX_SCALE,
    MIN_BORDER_WIDTH,
    MIN_SCALE,
    V_BORDER,
    V_BORDER_WIDTH,
    V_FILL,
    V_SIZE_SCALE,
)

MARKER_ICON_ATTRIBUTE = "icon"
MARKER_ICON_ANCHOR_ATTRIBUTE = "_v_icon_anchor"

MARKER_APPEARANCE_ATTRIBUTE_KEYS = frozenset(
    {
        MARKER_ICON_ATTRIBUTE,
        V_FILL,
        V_BORDER,
        V_BORDER_WIDTH,
        V_SIZE_SCALE,
        MARKER_SIZING_ATTRIBUTE,
        MARKER_ICON_ANCHOR_ATTRIBUTE,
    }
)


@dataclass(frozen=True)
class MarkerIconAnchor:
    """Normalized point in marker artwork pinned to the map coordinate."""

    x: float = 0.5
    y: float = 0.5

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MarkerIconAnchor":
        """Build a clamped anchor from a potentially invalid mapping."""
        return cls(
            x=_unit_float(payload.get("x"), 0.5),
            y=_unit_float(payload.get("y"), 0.5),
        )

    def to_dict(self) -> dict[str, float]:
        """Return a JSON-safe anchor payload."""
        return {"x": self.x, "y": self.y}

    @property
    def is_centered(self) -> bool:
        """Return whether this anchor matches the legacy centred behaviour."""
        return math.isclose(self.x, 0.5) and math.isclose(self.y, 0.5)


@dataclass(frozen=True)
class MarkerAppearance:
    """Complete copyable appearance of one point marker.

    Optional values represent inherited/default styling and are omitted from
    serialized attributes. The anchor is always serialized so pasting a
    legacy centred appearance resets an off-centre target reliably.
    """

    icon: str | None = None
    fill: str | None = None
    border: str | None = None
    border_width: int | None = None
    size_scale: float | None = None
    sizing: MarkerSizingSettings | None = None
    anchor: MarkerIconAnchor = field(default_factory=MarkerIconAnchor)

    @classmethod
    def from_attributes(cls, attributes: Mapping[str, Any]) -> "MarkerAppearance":
        """Extract only copyable appearance values from marker attributes."""
        anchor_payload = attributes.get(MARKER_ICON_ANCHOR_ATTRIBUTE)
        anchor = (
            MarkerIconAnchor.from_dict(anchor_payload)
            if isinstance(anchor_payload, Mapping)
            else MarkerIconAnchor()
        )
        sizing_payload = attributes.get(MARKER_SIZING_ATTRIBUTE)
        sizing = (
            MarkerSizingSettings.from_dict(sizing_payload)
            if isinstance(sizing_payload, Mapping)
            else None
        )
        return cls(
            icon=_optional_string(attributes.get(MARKER_ICON_ATTRIBUTE)),
            fill=_optional_string(attributes.get(V_FILL)),
            border=_optional_string(attributes.get(V_BORDER)),
            border_width=_optional_int(
                attributes.get(V_BORDER_WIDTH),
                MIN_BORDER_WIDTH,
                MAX_BORDER_WIDTH,
            ),
            size_scale=_optional_float(
                attributes.get(V_SIZE_SCALE), MIN_SCALE, MAX_SCALE
            ),
            sizing=sizing,
            anchor=anchor,
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MarkerAppearance":
        """Build an appearance from its serialized attribute mapping."""
        return cls.from_attributes(payload)

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical copy/paste and command payload."""
        payload: dict[str, Any] = {
            MARKER_ICON_ANCHOR_ATTRIBUTE: self.anchor.to_dict()
        }
        optional_values = {
            MARKER_ICON_ATTRIBUTE: self.icon,
            V_FILL: self.fill,
            V_BORDER: self.border,
            V_BORDER_WIDTH: self.border_width,
            V_SIZE_SCALE: self.size_scale,
        }
        payload.update(
            {key: value for key, value in optional_values.items() if value is not None}
        )
        if self.sizing is not None:
            payload[MARKER_SIZING_ATTRIBUTE] = self.sizing.to_dict()
        return payload

    def apply_to_attributes(self, attributes: Mapping[str, Any]) -> dict[str, Any]:
        """Replace only appearance keys while preserving semantic attributes."""
        updated = {
            key: value
            for key, value in attributes.items()
            if key not in MARKER_APPEARANCE_ATTRIBUTE_KEYS
        }
        updated.update(self.to_dict())
        return updated


def _unit_float(value: Any, default: float) -> float:
    """Return a finite float clamped to the inclusive zero-to-one range."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed):
        return default
    return max(0.0, min(1.0, parsed))


def _optional_float(value: Any, minimum: float, maximum: float) -> float | None:
    """Return a bounded finite float, or ``None`` when no override exists."""
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return max(minimum, min(maximum, parsed))


def _optional_int(value: Any, minimum: int, maximum: int) -> int | None:
    """Return a bounded integer, or ``None`` when no override exists."""
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return max(minimum, min(maximum, parsed))


def _optional_string(value: Any) -> str | None:
    """Return a non-empty string override, or ``None``."""
    if not isinstance(value, str) or not value:
        return None
    return value
