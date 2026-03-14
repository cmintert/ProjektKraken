"""MapFeature Data Model.

Implements the Hybrid Anchor/Geometry pattern for map features.
Every feature retains a single X/Y anchor coordinate for label placement
and fast lookups, with optional geometry for complex shapes (paths, regions).

Backward compatibility: ``Marker`` is an alias for ``MapFeature``.
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Valid feature_type discriminator values
FEATURE_TYPE_POINT = "point"
FEATURE_TYPE_PATH = "path"
FEATURE_TYPE_REGION = "region"
FEATURE_TYPE_MULTIPOINT = "multipoint"
VALID_FEATURE_TYPES = frozenset(
    {
        FEATURE_TYPE_POINT,
        FEATURE_TYPE_PATH,
        FEATURE_TYPE_REGION,
        FEATURE_TYPE_MULTIPOINT,
    }
)


@dataclass
class MapFeature:
    """Represents a geographic feature on a map (Hybrid Anchor/Geometry).

    A MapFeature links a map to an entity or event at a specific position.
    The *Anchor* (x, y) is always present and serves as the label placement
    point and O(1) spatial lookup key.  Complex shapes are stored in the
    optional *geometry* payload.

    Attributes:
        map_id: ID of the map this feature belongs to.
        object_id: ID of the linked entity or event.
        object_type: Type of linked object ('entity' or 'event').
        x: Anchor X coordinate (normalized 0.0–1.0).
        y: Anchor Y coordinate (normalized 0.0–1.0).
        id: Unique identifier for the feature.
        label: Optional display label.
        attributes: Flexible JSON attributes for custom data.
        created_at: Unix timestamp of creation.
        modified_at: Unix timestamp of last modification.
        feature_type: Discriminator — 'point', 'path', 'region', or 'multipoint'.
        geometry: Optional list of coordinate dicts ``[{x, y}, ...]``.
        style: Optional dict of visual overrides (stroke_width, fill_color, etc.).

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
    feature_type: str = FEATURE_TYPE_POINT
    geometry: Optional[List[Dict[str, float]]] = None
    style: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # Property accessors — avoid string comparisons in consuming code
    # ------------------------------------------------------------------

    @property
    def is_point(self) -> bool:
        """True when this feature is a simple point (no vector geometry)."""
        return self.feature_type == FEATURE_TYPE_POINT

    @property
    def is_path(self) -> bool:
        """True when this feature represents a line / path."""
        return self.feature_type == FEATURE_TYPE_PATH

    @property
    def is_region(self) -> bool:
        """True when this feature represents a polygon / region."""
        return self.feature_type == FEATURE_TYPE_REGION

    @property
    def is_multipoint(self) -> bool:
        """True when this feature represents a multipoint cluster."""
        return self.feature_type == FEATURE_TYPE_MULTIPOINT

    @property
    def points(self) -> List[Tuple[float, float]]:
        """Deserializes geometry into a list of (x, y) tuples.

        Falls back to the Anchor ``[(self.x, self.y)]`` when geometry
        is ``None`` or empty.

        Returns:
            List of (x, y) coordinate tuples.

        """
        if self.geometry:
            return [(pt["x"], pt["y"]) for pt in self.geometry]
        return [(self.x, self.y)]

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    def set_geometry(self, coords: Optional[List[Dict[str, float]]]) -> None:
        """Sets geometry and auto-recalculates the Anchor to the visual center.

        For paths the anchor becomes the midpoint; for regions it becomes
        the centroid.  If *coords* is ``None`` or empty the anchor is left
        unchanged and the feature becomes a plain point.

        Args:
            coords: List of ``{"x": float, "y": float}`` dicts, or None.

        """
        if not coords:
            self.geometry = None
            return

        self.geometry = coords
        cx, cy = self._compute_centroid(coords)
        self.x = cx
        self.y = cy

    def get_bounding_box(self) -> Tuple[float, float, float, float]:
        """Calculates the axis-aligned bounding box of the feature.

        Returns:
            Tuple of (min_x, min_y, max_x, max_y).

        """
        pts = self.points
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))

    # ------------------------------------------------------------------
    # GIS spatial computations (normalized coordinate space)
    # ------------------------------------------------------------------

    def compute_length(self, map_width: float = 1.0, map_height: float = 1.0) -> float:
        """Computes the total length of a path feature.

        For regions this returns 0.0; use ``compute_perimeter()`` instead.
        The result is in the same units as *map_width* / *map_height*
        (default: normalized 0-1 units; pass meters for real-world distance).

        Args:
            map_width: Real-world width of the map (e.g. meters).
            map_height: Real-world height of the map (e.g. meters).

        Returns:
            Total path length in the caller's units.

        """
        if self.feature_type != FEATURE_TYPE_PATH:
            return 0.0
        return self._segment_length_sum(self.points, map_width, map_height)

    def compute_perimeter(
        self, map_width: float = 1.0, map_height: float = 1.0
    ) -> float:
        """Computes the perimeter of a region feature.

        The polygon is implicitly closed (last vertex → first vertex).

        Args:
            map_width: Real-world width of the map (e.g. meters).
            map_height: Real-world height of the map (e.g. meters).

        Returns:
            Perimeter length in the caller's units.

        """
        if self.feature_type != FEATURE_TYPE_REGION:
            return 0.0
        pts = self.points
        if len(pts) < 3:
            return 0.0
        # Close the polygon by appending the first point
        closed = list(pts) + [pts[0]]
        return self._segment_length_sum(closed, map_width, map_height)

    def compute_area(self, map_width: float = 1.0, map_height: float = 1.0) -> float:
        """Computes the area of a region feature using the Shoelace formula.

        The result is in square units of the caller's coordinate system
        (default: normalized; pass meters for real-world area in m²).

        Args:
            map_width: Real-world width of the map.
            map_height: Real-world height of the map.

        Returns:
            Absolute area in the caller's square units.

        """
        if self.feature_type != FEATURE_TYPE_REGION:
            return 0.0
        pts = self.points
        if len(pts) < 3:
            return 0.0
        # Shoelace formula
        n = len(pts)
        total = 0.0
        for i in range(n):
            x0 = pts[i][0] * map_width
            y0 = pts[i][1] * map_height
            x1 = pts[(i + 1) % n][0] * map_width
            y1 = pts[(i + 1) % n][1] * map_height
            total += x0 * y1 - x1 * y0
        return abs(total) / 2.0

    def compute_segment_count(self) -> int:
        """Returns the number of line segments in the geometry.

        Returns:
            Number of segments (vertices - 1 for paths, vertices for regions).

        """
        pts = self.points
        if len(pts) < 2:
            return 0
        if self.feature_type == FEATURE_TYPE_REGION:
            return len(pts)  # closed polygon
        return len(pts) - 1  # open polyline

    @property
    def spatial_properties(self) -> Dict[str, Any]:
        """Returns a dict of computed spatial properties merged with user attributes.

        This is the primary interface for downstream code that needs
        lightweight GIS metadata (e.g. UI info panels, export).

        Returns:
            Dict with keys like ``length``, ``area``, ``perimeter``,
            ``segment_count``, ``bounding_box``, plus any user-defined
            attributes from ``self.attributes``.

        """
        props: Dict[str, Any] = {
            "feature_type": self.feature_type,
            "vertex_count": len(self.points),
            "segment_count": self.compute_segment_count(),
            "bounding_box": self.get_bounding_box(),
        }
        if self.is_path:
            props["length"] = self.compute_length()
        if self.is_region:
            props["area"] = self.compute_area()
            props["perimeter"] = self.compute_perimeter()
        # Merge user-defined spatial attributes (road_quality, river_depth, etc.)
        props.update(self.attributes)
        return props

    @staticmethod
    def _segment_length_sum(
        pts: List[Tuple[float, float]],
        map_width: float,
        map_height: float,
    ) -> float:
        """Sums Euclidean distances between consecutive point pairs.

        Args:
            pts: Ordered list of (x, y) tuples (normalized).
            map_width: Scale factor for X.
            map_height: Scale factor for Y.

        Returns:
            Total distance.

        """
        import math

        total = 0.0
        for i in range(len(pts) - 1):
            dx = (pts[i + 1][0] - pts[i][0]) * map_width
            dy = (pts[i + 1][1] - pts[i][1]) * map_height
            total += math.sqrt(dx * dx + dy * dy)
        return total

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Converts the MapFeature instance to a dictionary.

        Returns:
            Dict[str, Any]: Dictionary representation of the feature.

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
            "feature_type": self.feature_type,
            "geometry": self.geometry,
            "style": self.style,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MapFeature":
        """Creates a MapFeature instance from a dictionary.

        Handles JSON-encoded geometry and style strings (from database rows)
        as well as already-deserialized Python objects.

        Args:
            data: Dictionary containing feature data.

        Returns:
            MapFeature: A new MapFeature instance.

        """
        geometry_raw = data.get("geometry")
        geometry: Optional[List[Dict[str, float]]] = None
        if geometry_raw is not None:
            if isinstance(geometry_raw, str):
                try:
                    geometry = json.loads(geometry_raw)
                except (json.JSONDecodeError, TypeError):
                    geometry = None
            elif isinstance(geometry_raw, list):
                geometry = geometry_raw

        style_raw = data.get("style")
        style: Optional[Dict[str, Any]] = None
        if style_raw is not None:
            if isinstance(style_raw, str):
                try:
                    style = json.loads(style_raw)
                except (json.JSONDecodeError, TypeError):
                    style = None
            elif isinstance(style_raw, dict):
                style = style_raw

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
            feature_type=data.get("feature_type", FEATURE_TYPE_POINT),
            geometry=geometry,
            style=style,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_centroid(
        coords: List[Dict[str, float]],
    ) -> Tuple[float, float]:
        """Computes the arithmetic centroid of a coordinate list.

        Args:
            coords: Non-empty list of ``{"x": float, "y": float}`` dicts.

        Returns:
            Tuple (cx, cy) — the centroid.

        """
        n = len(coords)
        cx = sum(pt["x"] for pt in coords) / n
        cy = sum(pt["y"] for pt in coords) / n
        return (cx, cy)


# Backward-compatibility alias
Marker = MapFeature
