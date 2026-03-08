"""Brush preset storage for raster layer painting."""

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List

from PySide6.QtCore import QSettings

SETTINGS_RASTER_BRUSH_PRESETS_KEY = "raster/brush_presets"

_SETTINGS_APP = "ProjektKraken"
_SETTINGS_KEY = "ChristianMintert"


@dataclass
class BrushPreset:
    """A saved set of raster brush settings.

    Attributes:
        name: Human-readable preset name.
        tool_mode: Active tool — ``"brush"``, ``"fill"``, or ``"gradient"``.
        size: Brush size in pixels.
        falloff: Brush falloff [0.0, 1.0].
        paint_value: The 16-bit raster value to paint.
        id: Unique preset UUID.
    """

    name: str
    tool_mode: str
    size: int = 20
    falloff: float = 0.0
    paint_value: int = 1
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to JSON-friendly dict."""
        return {
            "id": self.id,
            "name": self.name,
            "tool_mode": self.tool_mode,
            "size": self.size,
            "falloff": self.falloff,
            "paint_value": self.paint_value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BrushPreset":
        """Deserialise from dict."""
        return cls(
            name=str(data.get("name", "Preset")),
            tool_mode=str(data.get("tool_mode", "brush")),
            size=int(data.get("size", 20)),
            falloff=float(data.get("falloff", 0.0)),
            paint_value=int(data.get("paint_value", 1)),
            id=str(data.get("id", str(uuid.uuid4()))),
        )


class PresetStore:
    """Load and save BrushPreset list from QSettings."""

    @staticmethod
    def load() -> List[BrushPreset]:
        """Load all saved presets from persistent settings.

        Returns:
            List of :class:`BrushPreset` objects (may be empty).
        """
        settings = QSettings(_SETTINGS_APP, _SETTINGS_KEY)
        raw = settings.value(SETTINGS_RASTER_BRUSH_PRESETS_KEY, "[]")
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [BrushPreset.from_dict(d) for d in data]
        except Exception:
            pass
        return []

    @staticmethod
    def save(presets: List[BrushPreset]) -> None:
        """Persist the given preset list to QSettings.

        Args:
            presets: Presets to save.
        """
        settings = QSettings(_SETTINGS_APP, _SETTINGS_KEY)
        settings.setValue(
            SETTINGS_RASTER_BRUSH_PRESETS_KEY,
            json.dumps([p.to_dict() for p in presets]),
        )
