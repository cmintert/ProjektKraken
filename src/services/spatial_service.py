"""Spatial Service Module.

Provides geometry utilities and spatial indexing for road networks.
Supports both native Python implementations and optional shapely/scipy
for better performance.
"""

import logging
import math
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    import shapely.geometry as shp
    from shapely.geometry import LineString, Point
    from shapely.strtree import STRtree

    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False
    logger.debug("Shapely not available, using native implementations")

try:
    from scipy.spatial import KDTree

    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logger.debug("SciPy not available, using native implementations")


class SpatialService:
    """Provides spatial operations for road networks.

    This service handles geometry calculations, spatial indexing,
    and segment operations needed for road network manipulation.
    """

    def __init__(self, use_shapely: bool = True, use_scipy: bool = True) -> None:
        """Initializes the SpatialService.

        Args:
            use_shapely: Use shapely if available (default: True).
            use_scipy: Use scipy if available (default: True).
        """
        self.use_shapely = use_shapely and SHAPELY_AVAILABLE
        self.use_scipy = use_scipy and SCIPY_AVAILABLE

        if self.use_shapely:
            logger.debug("Using Shapely for geometry operations")
        if self.use_scipy:
            logger.debug("Using SciPy for spatial indexing")

    @staticmethod
    def distance(
        x1: float, y1: float, x2: float, y2: float
    ) -> float:
        """Calculates Euclidean distance between two points.

        Args:
            x1: X coordinate of first point.
            y1: Y coordinate of first point.
            x2: X coordinate of second point.
            y2: Y coordinate of second point.

        Returns:
            float: Distance between points.
        """
        dx = x2 - x1
        dy = y2 - y1
        return math.sqrt(dx * dx + dy * dy)

    @staticmethod
    def polyline_length(coords: List[List[float]]) -> float:
        """Calculates total length of a polyline.

        Args:
            coords: List of [x, y] coordinate pairs.

        Returns:
            float: Total length of the polyline.
        """
        if len(coords) < 2:
            return 0.0

        total = 0.0
        for i in range(len(coords) - 1):
            x1, y1 = coords[i]
            x2, y2 = coords[i + 1]
            total += SpatialService.distance(x1, y1, x2, y2)
        return total

    @staticmethod
    def bbox(coords: List[List[float]]) -> Tuple[float, float, float, float]:
        """Calculates bounding box for a set of coordinates.

        Args:
            coords: List of [x, y] coordinate pairs.

        Returns:
            Tuple[float, float, float, float]: (min_x, min_y, max_x, max_y).
        """
        if not coords:
            return (0.0, 0.0, 0.0, 0.0)

        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        return (min(xs), min(ys), max(xs), max(ys))

    @staticmethod
    def point_to_segment_distance(
        px: float, py: float, x1: float, y1: float, x2: float, y2: float
    ) -> Tuple[float, float, float]:
        """Calculates distance from point to line segment.

        Args:
            px: Point x coordinate.
            py: Point y coordinate.
            x1: Segment start x.
            y1: Segment start y.
            x2: Segment end x.
            y2: Segment end y.

        Returns:
            Tuple[float, float, float]: (distance, closest_x, closest_y).
        """
        # Vector from start to end
        dx = x2 - x1
        dy = y2 - y1

        # Segment length squared
        seg_len_sq = dx * dx + dy * dy

        if seg_len_sq == 0:
            # Segment is a point
            dist = SpatialService.distance(px, py, x1, y1)
            return (dist, x1, y1)

        # Parameter t represents position along segment [0, 1]
        t = ((px - x1) * dx + (py - y1) * dy) / seg_len_sq
        t = max(0.0, min(1.0, t))  # Clamp to [0, 1]

        # Closest point on segment
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy

        dist = SpatialService.distance(px, py, closest_x, closest_y)
        return (dist, closest_x, closest_y)

    @staticmethod
    def segment_intersection(
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        x3: float,
        y3: float,
        x4: float,
        y4: float,
        tolerance: float = 1e-10,
    ) -> Optional[Tuple[float, float]]:
        """Calculates intersection point of two line segments.

        Uses parametric line equation to find intersection.

        Args:
            x1, y1: First segment start.
            x2, y2: First segment end.
            x3, y3: Second segment start.
            x4, y4: Second segment end.
            tolerance: Numerical tolerance for parallel lines.

        Returns:
            Optional[Tuple[float, float]]: (x, y) if intersection exists, else None.
        """
        # Direction vectors
        dx1 = x2 - x1
        dy1 = y2 - y1
        dx2 = x4 - x3
        dy2 = y4 - y3

        # Determinant (cross product)
        det = dx1 * dy2 - dy1 * dx2

        if abs(det) < tolerance:
            # Lines are parallel or coincident
            return None

        # Parameters for intersection point
        t1 = ((x3 - x1) * dy2 - (y3 - y1) * dx2) / det
        t2 = ((x3 - x1) * dy1 - (y3 - y1) * dx1) / det

        # Check if intersection is within both segments
        if 0 <= t1 <= 1 and 0 <= t2 <= 1:
            ix = x1 + t1 * dx1
            iy = y1 + t1 * dy1
            return (ix, iy)

        return None

    def find_polyline_intersections(
        self,
        coords1: List[List[float]],
        coords2: List[List[float]],
        tolerance: float = 1e-10,
    ) -> List[Tuple[float, float, int, int]]:
        """Finds all intersection points between two polylines.

        Args:
            coords1: First polyline coordinates.
            coords2: Second polyline coordinates.
            tolerance: Numerical tolerance.

        Returns:
            List of (x, y, seg_idx1, seg_idx2) for each intersection.
        """
        intersections = []

        for i in range(len(coords1) - 1):
            x1, y1 = coords1[i]
            x2, y2 = coords1[i + 1]

            for j in range(len(coords2) - 1):
                x3, y3 = coords2[j]
                x4, y4 = coords2[j + 1]

                intersection = self.segment_intersection(
                    x1, y1, x2, y2, x3, y3, x4, y4, tolerance
                )
                if intersection:
                    ix, iy = intersection
                    intersections.append((ix, iy, i, j))

        return intersections

    def split_polyline_at_point(
        self, coords: List[List[float]], point: Tuple[float, float], seg_idx: int
    ) -> Tuple[List[List[float]], List[List[float]]]:
        """Splits a polyline at a specific point on a segment.

        Args:
            coords: Polyline coordinates.
            point: (x, y) point where to split.
            seg_idx: Index of segment containing the point.

        Returns:
            Tuple of two polylines (before, after).
        """
        if seg_idx < 0 or seg_idx >= len(coords) - 1:
            raise ValueError(f"Invalid segment index: {seg_idx}")

        px, py = point

        # Build first polyline (up to and including split point)
        before = coords[: seg_idx + 1] + [[px, py]]

        # Build second polyline (from split point onwards)
        after = [[px, py]] + coords[seg_idx + 1 :]

        return (before, after)

    def snap_to_nearest_node(
        self,
        x: float,
        y: float,
        nodes: List[Tuple[float, float]],
        threshold: float = 10.0,
    ) -> Optional[int]:
        """Finds the nearest node within threshold distance.

        Args:
            x: Query point x.
            y: Query point y.
            nodes: List of (x, y) node coordinates.
            threshold: Maximum distance to snap.

        Returns:
            Optional[int]: Index of nearest node if within threshold, else None.
        """
        if not nodes:
            return None

        if self.use_scipy and len(nodes) > 100:
            # Use KDTree for large node sets
            tree = KDTree(nodes)
            dist, idx = tree.query([x, y])
            if dist <= threshold:
                return int(idx)
            return None
        else:
            # Linear search for small node sets
            best_idx = None
            best_dist = threshold

            for i, (nx, ny) in enumerate(nodes):
                dist = self.distance(x, y, nx, ny)
                if dist < best_dist:
                    best_dist = dist
                    best_idx = i

            return best_idx

    def simplify_polyline(
        self, coords: List[List[float]], tolerance: float = 1.0
    ) -> List[List[float]]:
        """Simplifies a polyline using Douglas-Peucker algorithm.

        Args:
            coords: Polyline coordinates.
            tolerance: Maximum distance for point removal.

        Returns:
            Simplified polyline coordinates.
        """
        if len(coords) <= 2:
            return coords

        if self.use_shapely:
            # Use shapely's built-in simplification
            line = LineString(coords)
            simplified = line.simplify(tolerance, preserve_topology=True)
            return list(simplified.coords)
        else:
            # Native Douglas-Peucker implementation
            return self._douglas_peucker(coords, tolerance)

    def _douglas_peucker(
        self, coords: List[List[float]], tolerance: float
    ) -> List[List[float]]:
        """Douglas-Peucker polyline simplification.

        Args:
            coords: Polyline coordinates.
            tolerance: Maximum distance for point removal.

        Returns:
            Simplified polyline coordinates.
        """
        if len(coords) <= 2:
            return coords

        # Find point with maximum distance from line segment
        start = coords[0]
        end = coords[-1]
        max_dist = 0.0
        max_idx = 0

        for i in range(1, len(coords) - 1):
            point = coords[i]
            dist, _, _ = self.point_to_segment_distance(
                point[0], point[1], start[0], start[1], end[0], end[1]
            )
            if dist > max_dist:
                max_dist = dist
                max_idx = i

        # If max distance is greater than tolerance, recursively simplify
        if max_dist > tolerance:
            # Recursive call on both halves
            left = self._douglas_peucker(coords[: max_idx + 1], tolerance)
            right = self._douglas_peucker(coords[max_idx:], tolerance)
            # Combine results (remove duplicate middle point)
            return left[:-1] + right
        else:
            # All points can be removed except endpoints
            return [coords[0], coords[-1]]

    def merge_nearby_nodes(
        self, nodes: List[Tuple[float, float, str]], threshold: float = 5.0
    ) -> List[Tuple[str, str]]:
        """Finds pairs of nodes that should be merged based on proximity.

        Args:
            nodes: List of (x, y, node_id) tuples.
            threshold: Distance threshold for merging.

        Returns:
            List of (node_id1, node_id2) pairs to merge.
        """
        merge_pairs = []

        for i in range(len(nodes)):
            x1, y1, id1 = nodes[i]
            for j in range(i + 1, len(nodes)):
                x2, y2, id2 = nodes[j]
                dist = self.distance(x1, y1, x2, y2)
                if dist < threshold:
                    merge_pairs.append((id1, id2))

        return merge_pairs
