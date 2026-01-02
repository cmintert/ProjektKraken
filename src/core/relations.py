"""Core Relations Module.

Defines the Relation dataclass representing directed relationships between objects.

The Relation class represents connections between events and entities with:
- Directed edges (source → target)
- Flexible type system (caused, located_in, involved, etc.)
- JSON attributes for metadata (weight, dates, confidence, etc.)
- Support for multi-edges (duplicate source/target pairs allowed)
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class Relation:
    """
    Represents a directed relationship between two objects.

    Relations connect events to events, entities to entities, or
    events to entities. They support:
    - Typed relationships (caused, located_in, involved, etc.)
    - Flexible attributes for metadata
    - Multi-edges (multiple relations between same source/target)

    Attributes:
        source_id: ID of the source object (event or entity).
        target_id: ID of the target object (event or entity).
        rel_type: Type of relationship (e.g., "caused", "located_in").
        attributes: Flexible JSON storage for metadata.
        id: Unique identifier (auto-generated UUID).
        created_at: Creation timestamp (auto-generated).

    Common attribute keys:
        weight: Numeric strength (float, for graph analysis)
        start_date: When relationship began (float, lore_date format)
        end_date: When relationship ended (float, lore_date format)
        confidence: Certainty level (float, 0.0-1.0)
        source: Citation or reference (str)
        notes: Additional context (str)
    """

    source_id: str
    target_id: str
    rel_type: str
    attributes: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the Relation instance to a dictionary for storage or serialization.

        Returns:
            Dict[str, Any]: A dictionary containing all the relation's data.
        """
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "rel_type": self.rel_type,
            "attributes": self.attributes,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Relation":
        """
        Creates a Relation instance from a dictionary.

        Args:
            data: A dictionary containing relation data.

        Returns:
            Relation: A new Relation instance.
        """
        d = data.copy()
        # Handle explicit None from database (overrides default_factory)
        if "attributes" in d and d["attributes"] is None:
            d["attributes"] = {}
        return cls(**d)

    @property
    def weight(self) -> float:
        """
        Returns the weight of this relation for graph analysis.

        Returns:
            float: Weight value (default 1.0 if not set).
        """
        return self.attributes.get("weight", 1.0)

    @weight.setter
    def weight(self, value: float) -> None:
        """
        Sets the weight of this relation.

        Args:
            value: Weight value (typically 0.0-1.0 but not enforced).
        """
        self.attributes["weight"] = value

    @property
    def confidence(self) -> float:
        """
        Returns the confidence/certainty of this relation.

        Returns:
            float: Confidence value (default 1.0 if not set).
        """
        return self.attributes.get("confidence", 1.0)

    @confidence.setter
    def confidence(self, value: float) -> None:
        """
        Sets the confidence/certainty of this relation.

        Args:
            value: Confidence value (0.0 = uncertain, 1.0 = certain).
        """
        self.attributes["confidence"] = value
