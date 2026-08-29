"""Panel identity and placement registry for the workspace shell."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PySide6.QtWidgets import QWidget

ZoneName = Literal["left", "center", "right", "bottom"]
ZONE_NAMES: tuple[ZoneName, ...] = ("left", "center", "right", "bottom")


@dataclass(frozen=True)
class PanelDefinition:
    """Describe one reusable feature panel.

    Args:
        id: Stable semantic panel identifier.
        title: User-facing tab title.
        widget: Existing feature widget instance.
        default_zone: Factory location for the panel.
        activity_id: Optional activity-bar identifier.
    """

    id: str
    title: str
    widget: QWidget
    default_zone: ZoneName
    activity_id: str | None = None


class PanelRegistry:
    """Own panel definitions and their current fixed-zone locations."""

    def __init__(self) -> None:
        """Create an empty registry."""
        self._definitions: dict[str, PanelDefinition] = {}
        self._locations: dict[str, ZoneName] = {}

    def register(self, definition: PanelDefinition) -> None:
        """Register a unique panel definition."""
        if definition.id in self._definitions:
            raise ValueError(f"Panel already registered: {definition.id}")
        if definition.default_zone not in ZONE_NAMES:
            raise ValueError(f"Unknown default zone: {definition.default_zone}")
        if any(item.widget is definition.widget for item in self._definitions.values()):
            raise ValueError("A widget instance cannot represent multiple panels")
        self._definitions[definition.id] = definition
        self._locations[definition.id] = definition.default_zone

    def definition(self, panel_id: str) -> PanelDefinition:
        """Return the definition for *panel_id*."""
        try:
            return self._definitions[panel_id]
        except KeyError as exc:
            raise KeyError(f"Unknown panel: {panel_id}") from exc

    def panel(self, panel_id: str) -> QWidget:
        """Return the registered feature widget."""
        return self.definition(panel_id).widget

    def panel_ids(self) -> list[str]:
        """Return panel identifiers in registration order."""
        return list(self._definitions)

    def definitions(self) -> list[PanelDefinition]:
        """Return definitions in registration order."""
        return list(self._definitions.values())

    def location(self, panel_id: str) -> ZoneName:
        """Return the panel's current zone."""
        self.definition(panel_id)
        return self._locations[panel_id]

    def set_location(self, panel_id: str, zone: ZoneName) -> None:
        """Record that *panel_id* now belongs to *zone*."""
        self.definition(panel_id)
        if zone not in ZONE_NAMES:
            raise ValueError(f"Unknown zone: {zone}")
        self._locations[panel_id] = zone
