"""Snapping Manager Module.

Provides geometry-aware snapping for the map view, allowing vertices to
snap to nearby features during drawing and vertex editing.

The ``SnappingManager`` class leverages Qt's built-in BSP spatial index
(``QGraphicsScene.items()``) for efficient O(log n) candidate lookup,
then performs precise point-to-vertex and point-to-segment distance
calculations to find the best snap target.

Snap types are prioritised:
    1. **Vertex** — snaps to existing feature vertices (highest priority).
    2. **Edge** — snaps to the closest point on a feature edge/segment.

Usage::

    manager = SnappingManager(scene)
    result = manager.snap_point(cursor_pos, view_transform, exclude)
    if result.snapped:
        use result.pos instead of cursor_pos
"""

import logging
import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QTransform
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene

from src.gui.constants import MAP_SNAP_RADIUS_PX

logger = logging.getLogger(__name__)

_DEGENERATE_SEGMENT_EPSILON = 1e-12
_MINIMUM_SEGMENT_POINT_COUNT = 2


class SnapType(Enum):
    """Classification of how a point was snapped."""

    NONE = auto()
    VERTEX = auto()
    EDGE = auto()


@dataclass
class SnapResult:
    """Result of a snap query.

    Attributes:
        snapped: True if a valid snap target was found.
        pos: The snapped position (scene coordinates), or the original
            query position if no snap target was found.
        snap_type: The type of snap that occurred.
        source_item: The QGraphicsItem that provided the snap target,
            or None if no snap occurred.
        distance: Distance in scene units from the query to the snap point.

    """

    snapped: bool = False
    pos: QPointF = field(default_factory=lambda: QPointF(0, 0))
    snap_type: SnapType = SnapType.NONE
    source_item: Optional[QGraphicsItem] = None
    distance: float = float("inf")


def point_to_segment_distance(
    p: QPointF, a: QPointF, b: QPointF
) -> tuple[float, QPointF]:
    """Computes the closest point on segment AB to point P.

    Uses vector projection with clamping to find the nearest point
    on the finite line segment (not the infinite line).

    Args:
        p: The query point.
        a: Start of the segment.
        b: End of the segment.

    Returns:
        Tuple of (distance, closest_point) where distance is the
        Euclidean distance from P to the closest point on AB.

    """
    ab_x = b.x() - a.x()
    ab_y = b.y() - a.y()
    len_sq = ab_x * ab_x + ab_y * ab_y

    if len_sq < _DEGENERATE_SEGMENT_EPSILON:
        # Degenerate segment (A == B)
        dx = p.x() - a.x()
        dy = p.y() - a.y()
        return math.sqrt(dx * dx + dy * dy), QPointF(a)

    # Project P onto AB: t = dot(AP, AB) / |AB|²
    t = ((p.x() - a.x()) * ab_x + (p.y() - a.y()) * ab_y) / len_sq
    t = max(0.0, min(1.0, t))

    # Closest point on segment
    cx = a.x() + t * ab_x
    cy = a.y() + t * ab_y
    closest = QPointF(cx, cy)

    dx = p.x() - cx
    dy = p.y() - cy
    return math.sqrt(dx * dx + dy * dy), closest


class SnappingManager:
    """Manages snapping for the map view.

    Finds nearby feature vertices and edges within a configurable
    screen-pixel radius. Uses the scene's BSP index for efficient
    spatial queries.

    Args:
        scene: The QGraphicsScene containing map features.
        snap_radius_px: Snap radius in screen pixels (default from constants).

    """

    def __init__(
        self,
        scene: QGraphicsScene,
        snap_radius_px: float = MAP_SNAP_RADIUS_PX,
    ) -> None:
        """Initialize vertex and edge snapping for a graphics scene."""
        self._scene = scene
        self._snap_radius_px = snap_radius_px
        self._enabled = True

    @property
    def enabled(self) -> bool:
        """Whether snapping is currently enabled."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Enable or disable snapping."""
        self._enabled = value

    @property
    def snap_radius_px(self) -> float:
        """The snap radius in screen pixels."""
        return self._snap_radius_px

    @snap_radius_px.setter
    def snap_radius_px(self, value: float) -> None:
        """Set the snap radius in screen pixels."""
        self._snap_radius_px = max(1.0, value)

    def snap_point(
        self,
        query_pos: QPointF,
        view_transform: QTransform,
        exclude_items: Optional[Set[QGraphicsItem]] = None,
    ) -> SnapResult:
        """Finds the best snap target near a query position.

        Priority order:
            1. Vertex snap (closest vertex of a nearby feature).
            2. Edge snap (closest point on a nearby segment).

        The snap radius is specified in screen pixels and converted
        to scene units using the current view transform.

        Args:
            query_pos: Query position in scene coordinates.
            view_transform: The current view transform for
                screen-to-scene conversion.
            exclude_items: Set of items to exclude from snapping
                (e.g. the feature currently being edited).

        Returns:
            SnapResult with the best snap target, or an un-snapped
            result containing the original query_pos.

        """
        if not self._enabled:
            return SnapResult(pos=QPointF(query_pos))

        # Convert screen pixel radius → scene units
        view_scale = view_transform.m11()
        if view_scale <= 0:
            view_scale = 1.0
        scene_radius = self._snap_radius_px / view_scale

        exclude = exclude_items or set()

        # Query scene BSP index for nearby items
        search_rect = QRectF(
            query_pos.x() - scene_radius,
            query_pos.y() - scene_radius,
            scene_radius * 2,
            scene_radius * 2,
        )
        candidates = self._scene.items(search_rect)

        best_vertex = SnapResult(pos=QPointF(query_pos))
        best_edge = SnapResult(pos=QPointF(query_pos))

        for item in candidates:
            if item in exclude:
                continue

            # Only snap to feature items that have geometry
            geometry = getattr(item, "_geometry", None)
            pixmap_item = getattr(item, "pixmap_item", None)
            if not geometry or not pixmap_item:
                continue

            rect = pixmap_item.sceneBoundingRect()
            if rect.width() <= 0 or rect.height() <= 0:
                continue

            scene_points = self._geometry_to_scene(geometry, rect)

            # Check vertex snap (priority 1)
            vertex_result = self._check_vertices(
                query_pos, scene_points, scene_radius, item
            )
            if vertex_result.snapped and vertex_result.distance < best_vertex.distance:
                best_vertex = vertex_result

            # Check edge snap (priority 2)
            edge_result = self._check_edges(query_pos, scene_points, scene_radius, item)
            if edge_result.snapped and edge_result.distance < best_edge.distance:
                best_edge = edge_result

        # Vertex snap has priority over edge snap
        if best_vertex.snapped:
            return best_vertex
        if best_edge.snapped:
            return best_edge

        return SnapResult(pos=QPointF(query_pos))

    @staticmethod
    def _geometry_to_scene(
        geometry: List[Dict[str, float]], rect: QRectF
    ) -> List[QPointF]:
        """Converts normalized geometry to scene coordinates.

        Args:
            geometry: List of ``{'x': float, 'y': float}`` dicts.
            rect: The pixmap bounding rectangle in scene coordinates.

        Returns:
            List of QPointF in scene coordinates.

        """
        points: List[QPointF] = []
        for pt in geometry:
            sx = rect.left() + pt["x"] * rect.width()
            sy = rect.top() + pt["y"] * rect.height()
            points.append(QPointF(sx, sy))
        return points

    @staticmethod
    def _check_vertices(
        query: QPointF,
        scene_points: List[QPointF],
        radius: float,
        item: QGraphicsItem,
    ) -> SnapResult:
        """Finds the closest vertex within the snap radius.

        Args:
            query: Query position in scene coordinates.
            scene_points: Feature vertices in scene coordinates.
            radius: Snap radius in scene units.
            item: The source feature item.

        Returns:
            SnapResult for the closest vertex, or an un-snapped result.

        """
        best = SnapResult(pos=QPointF(query))
        for pt in scene_points:
            dx = pt.x() - query.x()
            dy = pt.y() - query.y()
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < radius and dist < best.distance:
                best = SnapResult(
                    snapped=True,
                    pos=QPointF(pt),
                    snap_type=SnapType.VERTEX,
                    source_item=item,
                    distance=dist,
                )
        return best

    @staticmethod
    def _check_edges(
        query: QPointF,
        scene_points: List[QPointF],
        radius: float,
        item: QGraphicsItem,
    ) -> SnapResult:
        """Finds the closest point on any segment within the snap radius.

        Args:
            query: Query position in scene coordinates.
            scene_points: Feature vertices in scene coordinates.
            radius: Snap radius in scene units.
            item: The source feature item.

        Returns:
            SnapResult for the closest edge point, or an un-snapped result.

        """
        best = SnapResult(pos=QPointF(query))
        n = len(scene_points)
        if n < _MINIMUM_SEGMENT_POINT_COUNT:
            return best

        # Check all segments. For closed polygons (RegionItem),
        # also check the closing segment.
        # NOTE: Import here to avoid circular dependency —
        # feature_items.py imports from constants.py which is
        # shared with this module.
        from src.gui.widgets.map.feature_items import RegionItem

        seg_count = n if isinstance(item, RegionItem) else n - 1
        for i in range(seg_count):
            a = scene_points[i]
            b = scene_points[(i + 1) % n]
            dist, closest = point_to_segment_distance(query, a, b)
            if dist < radius and dist < best.distance:
                best = SnapResult(
                    snapped=True,
                    pos=QPointF(closest),
                    snap_type=SnapType.EDGE,
                    source_item=item,
                    distance=dist,
                )
        return best
