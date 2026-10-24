"""Detached activity workspace definitions; no widgets or world data."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WorkspaceDefinition:
    """Stable built-in workspace identity and navigation presentation."""

    id: str
    name: str
    icon: str


BUILTIN_WORKSPACES = (
    WorkspaceDefinition("overview", "Overview", "workspace-overview"),
    WorkspaceDefinition("writing", "Writing", "note-pencil"),
    WorkspaceDefinition("chronology", "Chronology", "clock"),
    WorkspaceDefinition("cartography", "Cartography", "workspace-map"),
    WorkspaceDefinition("connections", "Connections", "workspace-connections"),
    WorkspaceDefinition("research", "Research", "workspace-search"),
)
BUILTIN_IDS = frozenset(item.id for item in BUILTIN_WORKSPACES)
WORKSPACE_LAYOUT_VERSION = 2
WORKSPACE_COLLECTION_KEY = "activity_workspaces_v1"


def workspace_default(workspace_id: str, inspector: str = "entity") -> dict[str, Any]:
    """Build a fresh layout for an activity without selecting an object.

    Other registered panels are added by the shell's normalizer, so tools remain
    available without duplicating widgets or discarding their live state.
    """
    if workspace_id not in BUILTIN_IDS:
        raise ValueError(f"Unknown built-in workspace: {workspace_id}")
    inspector = inspector if inspector in ("entity", "event") else "entity"
    companion = "event" if inspector == "entity" else "entity"
    zones: dict[str, Any] = {
        "left": dict(visible=True, size=270, panels=["project"], active="project"),
        "center": dict(
            visible=True, size=800, panels=[inspector, companion], active=inspector
        ),
        "right": dict(
            visible=False, size=340, panels=["analysis", "ai_search"], active="analysis"
        ),
        "bottom": dict(
            visible=False, size=210, panels=["timeline", "history"], active="timeline"
        ),
    }
    if workspace_id == "overview":
        zones["right"]["visible"] = True
        zones["bottom"]["visible"] = True
    elif workspace_id == "writing":
        zones["center"]["panels"].append("longform")
        zones["center"]["size"] = 1140
    elif workspace_id == "chronology":
        zones["bottom"].update(visible=True, size=300)
    elif workspace_id in ("cartography", "connections"):
        tool = "map" if workspace_id == "cartography" else "graph"
        zones["center"].update(panels=[tool], active=tool)
        zones["right"].update(
            visible=True, panels=[inspector, companion], active=inspector
        )
        zones["bottom"]["visible"] = workspace_id == "cartography"
    elif workspace_id == "research":
        zones["right"].update(visible=True, active="ai_search")
    return deepcopy(
        {
            "layout_version": WORKSPACE_LAYOUT_VERSION,
            "zones": zones,
            "closed_panels": {},
        }
    )
