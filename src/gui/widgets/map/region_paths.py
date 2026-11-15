"""Qt paths for normalized region rings."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainterPath, QPolygonF

from src.core.region_geometry import Geometry, Point, geometry_rings, ring_points


def scene_point(point: Point, rect: QRectF) -> QPointF:
    """Map normalized coordinates to the image on the scene."""
    x, y = point
    return QPointF(rect.left() + x * rect.width(), rect.top() + y * rect.height())


def region_path(geometry: Geometry, rect: QRectF) -> QPainterPath:
    """Build a fill path with separate subpaths for the perimeter and each rim."""
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.OddEvenFill)
    for ring in geometry_rings(geometry):
        if ring:
            path.addPolygon(
                QPolygonF([scene_point(p, rect) for p in ring_points(ring)])
            )
            path.closeSubpath()
    return path
