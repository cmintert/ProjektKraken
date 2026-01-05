"""
Marker Data Model.

Represents a marker on a map that points to an entity or event.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, NamedTuple


class MarkerState(NamedTuple):
    x: float
    y: float
    visible: bool


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

    def _ensure_temporal_init(self) -> None:
        """Initializes the temporal attribute structure if missing."""
        if "temporal" not in self.attributes:
            self.attributes["temporal"] = {
                "enabled": True,
                "interpolation": "linear",
                "keyframes": [],
            }
        # Backward compatibility safety
        if "keyframes" not in self.attributes["temporal"]:
            self.attributes["temporal"]["keyframes"] = []

    def add_keyframe(
        self, t: float, x: float, y: float, keyframe_type: str = "path"
    ) -> None:
        """
        Adds or updates a keyframe at time t.

        Args:
            t: Lore date for the keyframe.
            x: Normalized X coordinate.
            y: Normalized Y coordinate.
            keyframe_type: 'start', 'end', or 'path'.
        """
        self._ensure_temporal_init()
        keyframes = self.attributes["temporal"]["keyframes"]

        # Check for existing keyframe at this exact time
        for i, kf in enumerate(keyframes):
            if kf["t"] == t:
                # Update existing
                keyframes[i] = {"t": t, "x": x, "y": y, "type": keyframe_type}
                return

        # Insert new keyframe sorted
        new_kf = {"t": t, "x": x, "y": y, "type": keyframe_type}

        # Keep sorted
        inserted = False
        for i, kf in enumerate(keyframes):
            if kf["t"] > t:
                keyframes.insert(i, new_kf)
                inserted = True
                break

        if not inserted:
            keyframes.append(new_kf)

    def remove_keyframe(self, t: float) -> None:
        """Removes a keyframe at exactly time t."""
        self._ensure_temporal_init()
        keyframes = self.attributes["temporal"]["keyframes"]
        self.attributes["temporal"]["keyframes"] = [k for k in keyframes if k["t"] != t]

    def get_state_at(self, t: float) -> MarkerState:
        """
        Calculates the marker state (position and visibility) at time t.

        Args:
            t: current lore date.

        Returns:
            MarkerState(x, y, visible)
        """
        # If temporal is not enabled or empty, return static state
        if "temporal" not in self.attributes or not self.attributes["temporal"].get(
            "enabled", True
        ):
            return MarkerState(self.x, self.y, True)

        keyframes = self.attributes["temporal"].get("keyframes", [])
        if not keyframes:
            return MarkerState(self.x, self.y, True)

        # Import bisect
        import bisect

        # Create a list of times for bisection
        times = [kf["t"] for kf in keyframes]

        # Find insertion point
        idx = bisect.bisect_right(times, t)

        # Case: Before first keyframe
        if idx == 0:
            first = keyframes[0]
            if first.get("type") == "start":
                return MarkerState(first["x"], first["y"], False)
            # Default behavior currently holds the first keyframe position
            return MarkerState(first["x"], first["y"], True)

        # Case: After last keyframe
        if idx == len(keyframes):
            last = keyframes[-1]
            if last.get("type") == "end":
                return MarkerState(last["x"], last["y"], False)
            return MarkerState(last["x"], last["y"], True)

        # Case: Between keyframes (interpolate)
        prev = keyframes[idx - 1]
        next_kf = keyframes[idx]

        # Check types for visibility gaps
        if prev.get("type") == "end":
            # We are after an end, but before the next point.
            # If next is 'start', we are in the void.
            return MarkerState(prev["x"], prev["y"], False)

        # Linear Interpolation
        t0 = prev["t"]
        t1 = next_kf["t"]

        # Guard zero division (should be impossible due to existing check?)
        if t1 == t0:
            return MarkerState(prev["x"], prev["y"], True)

        fraction = (t - t0) / (t1 - t0)

        lerp_x = prev["x"] + (next_kf["x"] - prev["x"]) * fraction
        lerp_y = prev["y"] + (next_kf["y"] - prev["y"]) * fraction

        return MarkerState(lerp_x, lerp_y, True)

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
