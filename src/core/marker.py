"""
Marker Data Model.

Represents a marker on a map that points to an entity or event.
"""

import uuid
import time
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class Marker:
    """
    Represents a marker on a map.

    A marker links a map to an entity or event at a specific position.
    Positions are stored as normalized coordinates [0.0, 1.0] relative to
    the map image dimensions.

    Attributes:
        map_id: ID of the map this marker is on.
        object_id: ID of the entity or event this marker points to.
        object_type: Type of object ('entity' or 'event').
        x: Normalized X coordinate (0.0 = left edge, 1.0 = right edge).
        y: Normalized Y coordinate (0.0 = top edge, 1.0 = bottom edge).
        id: Unique identifier for the marker.
        label: Optional display label for the marker.
        attributes: Flexible JSON attributes for custom data.
        created_at: Unix timestamp of creation.
        modified_at: Unix timestamp of last modification.
    """

    map_id: str
    object_id: str
    object_type: str
    x: float
    y: float
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    label: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the Marker instance to a dictionary.

        Returns:
            Dict[str, Any]: Dictionary representation of the marker.
        """
        return {
            "id": self.id,
            "map_id": self.map_id,
            "object_id": self.object_id,
            "object_type": self.object_type,
            "x": self.x,
            "y": self.y,
            "label": self.label,
            "attributes": self.attributes,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Marker":
        """
        Creates a Marker instance from a dictionary.

        Args:
            data: Dictionary containing marker data.

        Returns:
            Marker: A new Marker instance.
        """
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            map_id=data["map_id"],
            object_id=data["object_id"],
            object_type=data["object_type"],
            x=data["x"],
            y=data["y"],
            label=data.get("label", ""),
            attributes=data.get("attributes", {}),
            created_at=data.get("created_at", time.time()),
            modified_at=data.get("modified_at", time.time()),
        )
