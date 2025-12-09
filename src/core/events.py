from dataclasses import dataclass, field
from typing import Dict, Any
import uuid
import time


@dataclass
class Event:
    """
    Represents a specific point or span in time.
    Core unit of the Timeline.
    """

    name: str
    lore_date: float
    description: str = ""
    type: str = "generic"
    lore_duration: float = 0.0
    attributes: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the Event instance to a dictionary for storage or serialization.

        Returns:
            Dict[str, Any]: A dictionary containing all the event's data,
                            strictly typed keys.
        """
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "lore_date": self.lore_date,
            "lore_duration": self.lore_duration,
            "description": self.description,
            "attributes": self.attributes,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """
        Creates an Event instance from a dictionary.

        Args:
            data (Dict[str, Any]): A dictionary containing event data.

        Returns:
            Event: A new Event instance populated with the data.
        """
        # Create a shallow copy to avoid modifying input
        d = data.copy()
        # Extract fields that might be in 'attributes' if using a flat structure,
        # but here we expect the DB Service to provide them structured.
        return cls(**d)
