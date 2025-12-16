"""Core Maps Module.

Defines the GameMap and MapMarker dataclasses for map management.

The GameMap class represents a map asset with calibration data:
- Resolution-independent storage using normalized coordinates
- Scale calibration for distance/area calculations
- Reference dimensions for aspect ratio tracking

The MapMarker class represents an object (Entity or Event) placed on a map:
- Normalized coordinates (0.0-1.0) for resolution independence
- Links to either entities or events via object_id and object_type
- Flexible JSON attributes for per-marker overrides
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Literal
import uuid
import time


@dataclass
class GameMap:
    """
    Represents a map asset with calibration and metadata.
    
    Attributes:
        name: Display name of the map
        image_filename: Relative path to image (under assets/maps/)
        real_width: Real-world width of the map area
        distance_unit: Unit of measurement (m, km, mi, etc.)
        reference_width: Image width in pixels at calibration time
        reference_height: Image height in pixels at calibration time
        attributes: Flexible JSON storage for custom metadata
        id: Unique identifier (auto-generated UUID)
        created_at: Timestamp when map was created
        modified_at: Timestamp when map was last modified
    """

    name: str
    image_filename: str
    real_width: float
    distance_unit: str
    reference_width: int
    reference_height: int
    attributes: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)

    def __post_init__(self):
        """Validates map dimensions."""
        if self.reference_width <= 0 or self.reference_height <= 0:
            raise ValueError("Reference dimensions must be positive integers")
        if self.real_width <= 0:
            raise ValueError("Real width must be positive")

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the GameMap instance to a dictionary for storage or serialization.

        Returns:
            Dict[str, Any]: A dictionary containing all the map's data.
        """
        return {
            "id": self.id,
            "name": self.name,
            "image_filename": self.image_filename,
            "real_width": self.real_width,
            "distance_unit": self.distance_unit,
            "reference_width": self.reference_width,
            "reference_height": self.reference_height,
            "attributes": self.attributes,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GameMap":
        """
        Creates a GameMap instance from a dictionary.

        Args:
            data: Dictionary containing map data.

        Returns:
            GameMap: A new GameMap instance.
        """
        return cls(
            id=data["id"],
            name=data["name"],
            image_filename=data["image_filename"],
            real_width=data["real_width"],
            distance_unit=data["distance_unit"],
            reference_width=data["reference_width"],
            reference_height=data["reference_height"],
            attributes=data.get("attributes", {}),
            created_at=data["created_at"],
            modified_at=data["modified_at"],
        )

    @property
    def real_height(self) -> float:
        """
        Computes the real-world height based on aspect ratio.

        Returns:
            float: Real-world height in distance_unit.
        """
        aspect_ratio = self.reference_height / self.reference_width
        return self.real_width * aspect_ratio


@dataclass
class MapMarker:
    """
    Represents an Entity or Event placed on a map.

    Attributes:
        map_id: Reference to the map this marker is on
        object_id: ID of the entity or event
        object_type: Type of object ('entity' or 'event')
        x: Normalized x coordinate (0.0-1.0)
        y: Normalized y coordinate (0.0-1.0)
        attributes: Flexible JSON storage (icon overrides, labels, visibility)
        id: Unique identifier (auto-generated UUID)
    """

    map_id: str
    object_id: str
    object_type: Literal["entity", "event"]
    x: float
    y: float
    attributes: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        """Validates coordinate ranges and object type."""
        if not 0.0 <= self.x <= 1.0:
            raise ValueError(f"x coordinate must be in [0.0, 1.0], got {self.x}")
        if not 0.0 <= self.y <= 1.0:
            raise ValueError(f"y coordinate must be in [0.0, 1.0], got {self.y}")
        if self.object_type not in ("entity", "event"):
            raise ValueError(
                f"object_type must be 'entity' or 'event', got {self.object_type}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the MapMarker instance to a dictionary for storage or serialization.

        Returns:
            Dict[str, Any]: A dictionary containing all the marker's data.
        """
        return {
            "id": self.id,
            "map_id": self.map_id,
            "object_id": self.object_id,
            "object_type": self.object_type,
            "x": self.x,
            "y": self.y,
            "attributes": self.attributes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MapMarker":
        """
        Creates a MapMarker instance from a dictionary.

        Args:
            data: Dictionary containing marker data.

        Returns:
            MapMarker: A new MapMarker instance.
        """
        return cls(
            id=data["id"],
            map_id=data["map_id"],
            object_id=data["object_id"],
            object_type=data["object_type"],
            x=data["x"],
            y=data["y"],
            attributes=data.get("attributes", {}),
        )
