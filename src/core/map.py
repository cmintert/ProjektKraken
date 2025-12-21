"""
Map Data Model.

Represents a map image with associated metadata.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class Map:
    """
    Represents a map in the worldbuilding environment.

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
    """

    name: str
    image_path: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the Map instance to a dictionary.

        Returns:
            Dict[str, Any]: Dictionary representation of the map.
        """
        return {
            "id": self.id,
            "name": self.name,
            "image_path": self.image_path,
            "description": self.description,
            "attributes": self.attributes,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Map":
        """
        Creates a Map instance from a dictionary.

        Args:
            data: Dictionary containing map data.

        Returns:
            Map: A new Map instance.
        """
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data["name"],
            image_path=data["image_path"],
            description=data.get("description", ""),
            attributes=data.get("attributes", {}),
            created_at=data.get("created_at", time.time()),
            modified_at=data.get("modified_at", time.time()),
        )
