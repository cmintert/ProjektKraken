"""Road Data Model.

Represents roads, road segments, and nodes for map-based navigation.
Stored in pixel space within map.attributes["_roads"].
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class RoadNode:
    """Represents a node in a road network.

    Nodes are intersections or endpoints of road segments.
    Coordinates are in pixel space relative to the map image.

    Attributes:
        id: Unique identifier for the node.
        x: X coordinate in pixels.
        y: Y coordinate in pixels.
        attributes: Flexible attributes (e.g., type, name).
    """

    x: float
    y: float
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Converts the RoadNode to a dictionary.

        Returns:
            Dict[str, Any]: Dictionary representation.
        """
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "attributes": self.attributes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoadNode":
        """Creates a RoadNode from a dictionary.

        Args:
            data: Dictionary containing node data.

        Returns:
            RoadNode: New node instance.
        """
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            x=data["x"],
            y=data["y"],
            attributes=data.get("attributes", {}),
        )

    def distance_to(self, other: "RoadNode") -> float:
        """Calculates Euclidean distance to another node.

        Args:
            other: Target node.

        Returns:
            float: Distance in pixels.
        """
        dx = self.x - other.x
        dy = self.y - other.y
        return (dx * dx + dy * dy) ** 0.5


@dataclass
class RoadSegment:
    """Represents a segment of road between two nodes.

    Segments can have intermediate coordinates (polyline) for curved roads.

    Attributes:
        start_node_id: ID of the starting node.
        end_node_id: ID of the ending node.
        id: Unique identifier for the segment.
        road_id: Optional ID of parent road (for grouping).
        coords: List of [x, y] coordinates forming the segment path.
                First and last coords should match start/end nodes.
        length_px: Length of segment in pixels.
        attributes: Flexible attributes (speed, oneway, surface, layer, etc.).
    """

    start_node_id: str
    end_node_id: str
    coords: List[List[float]]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    road_id: Optional[str] = None
    length_px: float = 0.0
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Converts the RoadSegment to a dictionary.

        Returns:
            Dict[str, Any]: Dictionary representation.
        """
        return {
            "id": self.id,
            "start_node_id": self.start_node_id,
            "end_node_id": self.end_node_id,
            "road_id": self.road_id,
            "coords": self.coords,
            "length_px": self.length_px,
            "attributes": self.attributes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoadSegment":
        """Creates a RoadSegment from a dictionary.

        Args:
            data: Dictionary containing segment data.

        Returns:
            RoadSegment: New segment instance.
        """
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            start_node_id=data["start_node_id"],
            end_node_id=data["end_node_id"],
            road_id=data.get("road_id"),
            coords=data.get("coords", []),
            length_px=data.get("length_px", 0.0),
            attributes=data.get("attributes", {}),
        )


@dataclass
class Road:
    """Represents a named road composed of multiple segments.

    Roads group related segments (e.g., "Main Street").

    Attributes:
        name: Display name of the road.
        id: Unique identifier.
        segment_ids: List of segment IDs that make up this road.
        attributes: Flexible attributes (type, surface, etc.).
    """

    name: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    segment_ids: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Road to a dictionary.

        Returns:
            Dict[str, Any]: Dictionary representation.
        """
        return {
            "id": self.id,
            "name": self.name,
            "segment_ids": self.segment_ids,
            "attributes": self.attributes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Road":
        """Creates a Road from a dictionary.

        Args:
            data: Dictionary containing road data.

        Returns:
            Road: New road instance.
        """
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data["name"],
            segment_ids=data.get("segment_ids", []),
            attributes=data.get("attributes", {}),
        )


@dataclass
class RoadNetwork:
    """Represents a complete road network for a map.

    Stored in map.attributes["_roads"] as JSON.

    Attributes:
        nodes: Dictionary of node_id -> RoadNode.
        segments: List of RoadSegment objects.
        roads: List of Road objects.
        meta: Metadata (px_per_meter, units, created_at, modified_at).
    """

    nodes: Dict[str, RoadNode] = field(default_factory=dict)
    segments: List[RoadSegment] = field(default_factory=list)
    roads: List[Road] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Initialize metadata if not present."""
        if "created_at" not in self.meta:
            self.meta["created_at"] = time.time()
        if "modified_at" not in self.meta:
            self.meta["modified_at"] = time.time()
        if "px_per_meter" not in self.meta:
            self.meta["px_per_meter"] = 1.0  # Default: 1 pixel = 1 meter
        if "units" not in self.meta:
            self.meta["units"] = "meters"

    def to_dict(self) -> Dict[str, Any]:
        """Converts the RoadNetwork to a dictionary.

        Returns:
            Dict[str, Any]: Dictionary representation suitable for JSON storage.
        """
        return {
            "meta": self.meta,
            "nodes": {
                node_id: node.to_dict() for node_id, node in self.nodes.items()
            },
            "segments": [seg.to_dict() for seg in self.segments],
            "roads": [road.to_dict() for road in self.roads],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoadNetwork":
        """Creates a RoadNetwork from a dictionary.

        Args:
            data: Dictionary containing road network data.

        Returns:
            RoadNetwork: New network instance.
        """
        nodes = {
            node_id: RoadNode.from_dict(node_data)
            for node_id, node_data in data.get("nodes", {}).items()
        }
        segments = [RoadSegment.from_dict(seg) for seg in data.get("segments", [])]
        roads = [Road.from_dict(road) for road in data.get("roads", [])]
        meta = data.get("meta", {})

        return cls(nodes=nodes, segments=segments, roads=roads, meta=meta)

    def add_node(self, node: RoadNode) -> None:
        """Adds a node to the network.

        Args:
            node: Node to add.
        """
        self.nodes[node.id] = node
        self.meta["modified_at"] = time.time()

    def add_segment(self, segment: RoadSegment) -> None:
        """Adds a segment to the network.

        Args:
            segment: Segment to add.
        """
        self.segments.append(segment)
        self.meta["modified_at"] = time.time()

    def add_road(self, road: Road) -> None:
        """Adds a road to the network.

        Args:
            road: Road to add.
        """
        self.roads.append(road)
        self.meta["modified_at"] = time.time()

    def get_node(self, node_id: str) -> Optional[RoadNode]:
        """Retrieves a node by ID.

        Args:
            node_id: Node identifier.

        Returns:
            Optional[RoadNode]: Node if found, else None.
        """
        return self.nodes.get(node_id)

    def get_segment(self, segment_id: str) -> Optional[RoadSegment]:
        """Retrieves a segment by ID.

        Args:
            segment_id: Segment identifier.

        Returns:
            Optional[RoadSegment]: Segment if found, else None.
        """
        for seg in self.segments:
            if seg.id == segment_id:
                return seg
        return None

    def get_road(self, road_id: str) -> Optional[Road]:
        """Retrieves a road by ID.

        Args:
            road_id: Road identifier.

        Returns:
            Optional[Road]: Road if found, else None.
        """
        for road in self.roads:
            if road.id == road_id:
                return road
        return None

    def remove_node(self, node_id: str) -> None:
        """Removes a node from the network.

        Args:
            node_id: Node identifier to remove.
        """
        if node_id in self.nodes:
            del self.nodes[node_id]
            self.meta["modified_at"] = time.time()

    def remove_segment(self, segment_id: str) -> None:
        """Removes a segment from the network.

        Args:
            segment_id: Segment identifier to remove.
        """
        self.segments = [seg for seg in self.segments if seg.id != segment_id]
        self.meta["modified_at"] = time.time()

    def remove_road(self, road_id: str) -> None:
        """Removes a road from the network.

        Args:
            road_id: Road identifier to remove.
        """
        self.roads = [road for road in self.roads if road.id != road_id]
        self.meta["modified_at"] = time.time()
