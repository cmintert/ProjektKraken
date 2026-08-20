"""Per-marker icon sizing settings."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

MARKER_SIZING_ATTRIBUTE = "_v_marker_sizing"
MARKER_SIZING_SOURCE_ATTRIBUTE = "_v_marker_sizing_source"

DEFAULT_MAP_WIDTH_PERCENT = 1.5
DEFAULT_SCREEN_SIZE_PX = 24.0
DEFAULT_MAP_MARKER_DIAMETER_PX = 50.0
MIN_MAP_WIDTH_PERCENT = 0.1
MAX_MAP_WIDTH_PERCENT = 100.0
MIN_MAP_SIZE_METERS = 0.01
MIN_SCREEN_SIZE_PX = 8.0
MAX_SCREEN_SIZE_PX = 256.0


class MarkerSizingMode(str, Enum):
    """How point-marker artwork responds to view zoom."""

    MAP_RELATIVE = "map_relative"
    SCREEN_FIXED = "screen_fixed"


class MarkerMapSizeUnit(str, Enum):
    """Unit used for the map-relative marker diameter."""

    MAP_WIDTH_PERCENT = "map_width_percent"
    METERS = "meters"


class MarkerSizingSource(str, Enum):
    """Whether the active size follows icon defaults or a marker override."""

    ICON_DEFAULT = "icon_default"
    CUSTOM = "custom"


@dataclass(frozen=True)
class MarkerSizingSettings:
    """Validated, serializable per-marker sizing configuration."""

    mode: MarkerSizingMode = MarkerSizingMode.MAP_RELATIVE
    map_unit: MarkerMapSizeUnit = MarkerMapSizeUnit.MAP_WIDTH_PERCENT
    map_value: float = DEFAULT_MAP_WIDTH_PERCENT
    screen_px: float = DEFAULT_SCREEN_SIZE_PX

    @classmethod
    def for_map_image_width(
        cls,
        image_width: float,
        native_diameter_px: float = DEFAULT_MAP_MARKER_DIAMETER_PX,
    ) -> "MarkerSizingSettings":
        """Return the default relative size for a map's native image width.

        The stored percentage resolves to the requested canonical diameter at
        native scale, then grows and shrinks with the map during zooming.
        """
        safe_width = max(0.0, float(image_width))
        if safe_width <= 0:
            return cls()
        diameter = _positive_float(
            native_diameter_px,
            DEFAULT_MAP_MARKER_DIAMETER_PX,
        )
        percent = diameter / safe_width * 100.0
        return cls(
            map_value=max(
                MIN_MAP_WIDTH_PERCENT,
                min(MAX_MAP_WIDTH_PERCENT, percent),
            )
        )

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

    def with_scaled_active_size(
        self,
        multiplier: float,
        map_width_meters: float,
    ) -> "MarkerSizingSettings":
        """Return this setting with its active creator-facing size scaled.

        Map-relative percentages and calibrated physical footprints have
        different valid ranges. In particular, a metric footprint must not be
        capped at ``100`` simply because percentages are capped at 100 percent.
        """
        safe_multiplier = max(0.0, float(multiplier))
        if self.mode is MarkerSizingMode.SCREEN_FIXED:
            return replace(
                self,
                screen_px=max(
                    MIN_SCREEN_SIZE_PX,
                    min(MAX_SCREEN_SIZE_PX, self.screen_px * safe_multiplier),
                ),
            )
        if self.map_unit is MarkerMapSizeUnit.METERS:
            value = max(MIN_MAP_SIZE_METERS, self.map_value * safe_multiplier)
            if map_width_meters > 0:
                value = min(value, max(MIN_MAP_SIZE_METERS, map_width_meters))
            return replace(self, map_value=value)
        return replace(
            self,
            map_value=max(
                MIN_MAP_WIDTH_PERCENT,
                min(MAX_MAP_WIDTH_PERCENT, self.map_value * safe_multiplier),
            ),
        )


def _positive_float(value: Any, default: float) -> float:
    """Return a positive finite float or the supplied default."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed) or parsed <= 0:
        return default
    return parsed
