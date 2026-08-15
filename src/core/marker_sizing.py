"""Per-marker icon sizing settings."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

MARKER_SIZING_ATTRIBUTE = "_v_marker_sizing"

DEFAULT_MAP_WIDTH_PERCENT = 2.5
DEFAULT_SCREEN_SIZE_PX = 24.0


class MarkerSizingMode(str, Enum):
    """How point-marker artwork responds to view zoom."""

    MAP_RELATIVE = "map_relative"
    SCREEN_FIXED = "screen_fixed"


class MarkerMapSizeUnit(str, Enum):
    """Unit used for the map-relative marker diameter."""

    MAP_WIDTH_PERCENT = "map_width_percent"
    METERS = "meters"


@dataclass(frozen=True)
class MarkerSizingSettings:
    """Validated, serializable per-marker sizing configuration."""

    mode: MarkerSizingMode = MarkerSizingMode.MAP_RELATIVE
    map_unit: MarkerMapSizeUnit = MarkerMapSizeUnit.MAP_WIDTH_PERCENT
    map_value: float = DEFAULT_MAP_WIDTH_PERCENT
    screen_px: float = DEFAULT_SCREEN_SIZE_PX

    @classmethod
    def from_attributes(cls, attributes: Mapping[str, Any]) -> "MarkerSizingSettings":
        """Resolve settings from marker attributes, applying safe defaults."""
        payload = attributes.get(MARKER_SIZING_ATTRIBUTE)
        if not isinstance(payload, Mapping):
            return cls()
        return cls.from_dict(payload)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MarkerSizingSettings":
        """Build settings from a potentially invalid JSON mapping."""
        try:
            mode = MarkerSizingMode(payload.get("mode", MarkerSizingMode.MAP_RELATIVE))
        except (TypeError, ValueError):
            mode = MarkerSizingMode.MAP_RELATIVE

        try:
            map_unit = MarkerMapSizeUnit(
                payload.get("map_unit", MarkerMapSizeUnit.MAP_WIDTH_PERCENT)
            )
        except (TypeError, ValueError):
            map_unit = MarkerMapSizeUnit.MAP_WIDTH_PERCENT

        map_value = _positive_float(
            payload.get("map_value"), DEFAULT_MAP_WIDTH_PERCENT
        )
        screen_px = _positive_float(
            payload.get("screen_px"), DEFAULT_SCREEN_SIZE_PX
        )
        return cls(
            mode=mode,
            map_unit=map_unit,
            map_value=map_value,
            screen_px=screen_px,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation for marker attributes."""
        return {
            "mode": self.mode.value,
            "map_unit": self.map_unit.value,
            "map_value": self.map_value,
            "screen_px": self.screen_px,
        }

    def map_diameter_scene_units(
        self,
        image_width: float,
        map_width_meters: float,
    ) -> float:
        """Resolve the map-relative diameter in map-image scene units."""
        safe_image_width = max(0.0, float(image_width))
        if safe_image_width <= 0:
            return DEFAULT_SCREEN_SIZE_PX
        if self.map_unit is MarkerMapSizeUnit.METERS:
            if map_width_meters > 0:
                return safe_image_width * self.map_value / map_width_meters
            return safe_image_width * DEFAULT_MAP_WIDTH_PERCENT / 100.0
        return safe_image_width * self.map_value / 100.0


def _positive_float(value: Any, default: float) -> float:
    """Return a positive finite float or the supplied default."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed) or parsed <= 0:
        return default
    return parsed
