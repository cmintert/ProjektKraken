"""Map Data Model.

Represents a map image with associated metadata, and the hierarchical
layer tree used for organising markers, paths, and regions on the map.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.app.constants import (
    MAP_LAYER_DEFAULT_MAX_ZOOM,
    MAP_LAYER_DEFAULT_MIN_ZOOM,
    MAP_LAYER_DEFAULT_OPACITY,
    MAP_LAYER_TYPE_GROUP,
)


@dataclass
class MapLayerNode:
    """A single node in the hierarchical layer tree.

    Nodes can be **groups** (containers for other nodes) or **data layers**
    (marker, path, region) that reference concrete graphics items.

    Attributes:
        id: Unique identifier for the node.
        name: Human-readable display name.
        layer_type: Discriminator — 'group', 'marker', 'path', or 'region'.
        visible: Whether this node is visible.
        opacity: Local opacity (0.0–1.0).  Effective opacity is the product
            of this value and all ancestor opacities.
        expanded: Whether the node is expanded in the layer panel UI.
        children: Ordered child nodes (only meaningful for groups).
        min_zoom: Minimum zoom level at which this layer is visible.
        max_zoom: Maximum zoom level at which this layer is visible.
        mutually_exclusive: If ``True``, only one child of this group
            may be visible at a time (radio-button behaviour).
        start_date: Optional lore date when this layer becomes visible.
        end_date: Optional lore date when this layer stops being visible.

    """

    name: str
    layer_type: str = MAP_LAYER_TYPE_GROUP
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    visible: bool = True
    opacity: float = MAP_LAYER_DEFAULT_OPACITY
    expanded: bool = True
    children: List["MapLayerNode"] = field(default_factory=list)
    min_zoom: float = MAP_LAYER_DEFAULT_MIN_ZOOM
    max_zoom: float = MAP_LAYER_DEFAULT_MAX_ZOOM
    mutually_exclusive: bool = False
    start_date: Optional[float] = None
    end_date: Optional[float] = None

    # --- helpers -----------------------------------------------------------

    def effective_opacity(self, parent_opacity: float = 1.0) -> float:
        """Compute the effective opacity considering the parent chain.

        Args:
            parent_opacity: Accumulated opacity from ancestor nodes.

        Returns:
            float: The product of *parent_opacity* and this node's opacity.

        """
        return parent_opacity * self.opacity

    def effective_visible(self, parent_visible: bool = True) -> bool:
        """Compute effective visibility considering the parent chain.

        Args:
            parent_visible: Accumulated visibility from ancestor nodes.

        Returns:
            bool: ``True`` only if *both* the parent chain and this node
                are visible.

        """
        return parent_visible and self.visible

    # --- serialisation -----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Recursively serialise the node to a plain dict.

        Returns:
            Dict[str, Any]: JSON-friendly dictionary.

        """
        return {
            "id": self.id,
            "name": self.name,
            "layer_type": self.layer_type,
            "visible": self.visible,
            "opacity": self.opacity,
            "expanded": self.expanded,
            "children": [c.to_dict() for c in self.children],
            "min_zoom": self.min_zoom,
            "max_zoom": self.max_zoom if self.max_zoom != float("inf") else None,
            "mutually_exclusive": self.mutually_exclusive,
            "start_date": self.start_date,
            "end_date": self.end_date,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MapLayerNode":
        """Deserialise a node (and all descendants) from a dict.

        Args:
            data: Dictionary previously produced by :meth:`to_dict`.

        Returns:
            MapLayerNode: Reconstructed node tree.

        """
        max_zoom_raw = data.get("max_zoom")
        max_zoom = (
            float("inf")
            if max_zoom_raw is None
            else float(max_zoom_raw)
        )
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data["name"],
            layer_type=data.get("layer_type", MAP_LAYER_TYPE_GROUP),
            visible=data.get("visible", True),
            opacity=float(data.get("opacity", MAP_LAYER_DEFAULT_OPACITY)),
            expanded=data.get("expanded", True),
            children=[
                cls.from_dict(c) for c in data.get("children", [])
            ],
            min_zoom=float(data.get("min_zoom", MAP_LAYER_DEFAULT_MIN_ZOOM)),
            max_zoom=max_zoom,
            mutually_exclusive=data.get("mutually_exclusive", False),
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
        )


@dataclass
class Map:
    """Represents a map in the worldbuilding environment.

    A map is an image file that can have markers placed on it to indicate
    locations of entities or events.

    Attributes:
        id: Unique identifier for the map.
        name: Display name of the map.
        image_path: File system path to the map image.
        description: Optional description of the map.
        attributes: Flexible JSON attributes for custom data.
        created_at: Unix timestamp of creation.
        modified_at: Unix timestamp of last modification.
        layers: Root node of the hierarchical layer tree (optional).

    """

    name: str
    image_path: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
    layers: Optional[MapLayerNode] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Map instance to a dictionary.

        Returns:
            Dict[str, Any]: Dictionary representation of the map.

        """
        result: Dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "image_path": self.image_path,
            "description": self.description,
            "attributes": self.attributes,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }
        if self.layers is not None:
            result["layers"] = self.layers.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Map":
        """Creates a Map instance from a dictionary.

        Args:
            data: Dictionary containing map data.

        Returns:
            Map: A new Map instance.

        """
        layers_data = data.get("layers")
        layers = MapLayerNode.from_dict(layers_data) if layers_data else None
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data["name"],
            image_path=data["image_path"],
            description=data.get("description", ""),
            attributes=data.get("attributes", {}),
            created_at=data.get("created_at", time.time()),
            modified_at=data.get("modified_at", time.time()),
            layers=layers,
        )
