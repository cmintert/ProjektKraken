"""Explicit, versioned workspace layout state and normalization."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any, cast

from src.gui.workspace.panel_registry import ZONE_NAMES, PanelRegistry, ZoneName

WORKSPACE_LAYOUT_VERSION = 2
_MIN_ZONE_SIZE = 80
_MAX_ZONE_SIZE = 4096

DEFAULT_WORKSPACE_LAYOUT: dict[str, Any] = {
    "layout_version": WORKSPACE_LAYOUT_VERSION,
    "zones": {
        "left": {
            "visible": True,
            "size": 270,
            "panels": ["project"],
            "active": "project",
        },
        "center": {
            "visible": True,
            "size": 800,
            "panels": ["entity", "event", "map", "graph", "longform"],
            "active": "entity",
        },
        "right": {
            "visible": True,
            "size": 340,
            "panels": ["analysis", "ai_search"],
            "active": "analysis",
        },
        "bottom": {
            "visible": True,
            "size": 210,
            "panels": ["timeline", "history"],
            "active": "timeline",
        },
    },
}


def _default_size(zone: ZoneName) -> int:
    return int(DEFAULT_WORKSPACE_LAYOUT["zones"][zone]["size"])


def _normalized_size(value: object, zone: ZoneName) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return _default_size(zone)
    return max(_MIN_ZONE_SIZE, min(_MAX_ZONE_SIZE, int(value)))


def _saved_zone(saved_zones: object, zone: ZoneName) -> Mapping[str, object]:
    if not isinstance(saved_zones, Mapping):
        return {}
    candidate = saved_zones.get(zone)
    return candidate if isinstance(candidate, Mapping) else {}


def normalize_layout(
    saved_layout: object,
    registry: PanelRegistry,
) -> dict[str, Any]:
    """Return a complete, safe workspace layout for the current registry.

    Unknown panels and zones are ignored, duplicates keep their first valid
    occurrence, and newly registered panels are added to their default zones.
    An incompatible version falls back to the deterministic factory layout.
    """
    compatible = (
        isinstance(saved_layout, Mapping)
        and saved_layout.get("layout_version") == WORKSPACE_LAYOUT_VERSION
    )
    source: Mapping[str, object]
    if compatible:
        source = cast(Mapping[str, object], saved_layout)
    else:
        source = deepcopy(DEFAULT_WORKSPACE_LAYOUT)

    saved_zones = source.get("zones", {})
    known = set(registry.panel_ids())
    assigned: set[str] = set()
    panels_by_zone: dict[ZoneName, list[str]] = {zone: [] for zone in ZONE_NAMES}

    for zone in ZONE_NAMES:
        zone_data = _saved_zone(saved_zones, zone)
        raw_panels = zone_data.get("panels", [])
        if not isinstance(raw_panels, Sequence) or isinstance(raw_panels, str):
            continue
        for raw_panel_id in raw_panels:
            if not isinstance(raw_panel_id, str):
                continue
            if raw_panel_id not in known or raw_panel_id in assigned:
                continue
            panels_by_zone[zone].append(raw_panel_id)
            assigned.add(raw_panel_id)

    for definition in registry.definitions():
        if definition.id not in assigned:
            panels_by_zone[definition.default_zone].append(definition.id)
            assigned.add(definition.id)

    normalized_zones: dict[str, dict[str, object]] = {}
    for zone in ZONE_NAMES:
        zone_data = _saved_zone(saved_zones, zone)
        panels = panels_by_zone[zone]
        active = zone_data.get("active")
        if not isinstance(active, str) or active not in panels:
            active = panels[0] if panels else None

        requested_visible = zone_data.get("visible", True)
        visible = requested_visible if isinstance(requested_visible, bool) else True
        if zone == "center":
            visible = True
        elif not panels:
            visible = False

        normalized_zones[zone] = {
            "visible": visible,
            "size": _normalized_size(zone_data.get("size"), zone),
            "panels": panels,
            "active": active,
        }

    return {
        "layout_version": WORKSPACE_LAYOUT_VERSION,
        "zones": normalized_zones,
    }
