from dataclasses import dataclass, field
from typing import Dict, Any
import uuid
import time


@dataclass
class Entity:
    """
    Represents a timeless object (Character, Location, Artifact).
    """

    name: str
    type: str  # e.g., "character", "location", "faction"
    description: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the Entity instance to a dictionary for storage or serialization.

        Returns:
            Dict[str, Any]: A dictionary containing all the entity's data.
        """
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "description": self.description,
            "attributes": self.attributes,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Entity":
        """
        Creates an Entity instance from a dictionary.

        Args:
            data (Dict[str, Any]): A dictionary containing entity data.

        Returns:
            Entity: A new Entity instance.
        """
        d = data.copy()
        return cls(**d)
