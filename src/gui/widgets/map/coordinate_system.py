"""
Map Coordinate System Module.

Handles translation between different coordinate spaces:
1. Normalized Coordinates: (0.0, 0.0) top-left to (1.0, 1.0) bottom-right.
2. Scene Coordinates: Pixel coordinates on the map image.

Strictly Cartesian. No spherical projections or geodetic logic.
"""

from typing import Tuple
from PySide6.QtCore import QPointF, QRectF


class MapCoordinateSystem:
    """
    Manages coordinate transformations for the map.
    """

    def __init__(self) -> None:
        """
        Initializes the MapCoordinateSystem.

        Creates a coordinate system with an empty scene rectangle.
        Call set_scene_rect() after initialization to define the map bounds.
        """
        self._scene_rect = QRectF()

    def set_scene_rect(self, rect: QRectF) -> None:
        """
        Updates the boundaries of the scene (the map image dimensions).

        Args:
            rect: The bounding rectangle of the map image in scene coordinates.
        """
        self._scene_rect = rect

    def to_scene(self, x: float, y: float) -> QPointF:
        """
        Converts normalized coordinates to scene coordinates.

        Args:
            x: Normalized X [0.0, 1.0].
            y: Normalized Y [0.0, 1.0].

        Returns:
            QPointF: Point in scene coordinates.
        """
        if self._scene_rect.isEmpty():
            return QPointF(0.0, 0.0)

        scene_x = self._scene_rect.left() + (x * self._scene_rect.width())
        scene_y = self._scene_rect.top() + (y * self._scene_rect.height())
        return QPointF(scene_x, scene_y)

    def to_normalized(self, scene_pos: QPointF) -> Tuple[float, float]:
        """
        Converts scene coordinates to normalized coordinates.

        Args:
            scene_pos: Point in scene coordinates.

        Returns:
            Tuple[float, float]: (x, y) normalized coordinates.
        """
        if (
            self._scene_rect.isEmpty()
            or self._scene_rect.width() == 0
            or self._scene_rect.height() == 0
        ):
            return 0.0, 0.0

        rel_x = scene_pos.x() - self._scene_rect.left()
        rel_y = scene_pos.y() - self._scene_rect.top()

        norm_x = rel_x / self._scene_rect.width()
        norm_y = rel_y / self._scene_rect.height()

        return norm_x, norm_y

    def clamp_normalized(self, x: float, y: float) -> Tuple[float, float]:
        """
        Clamps coordinates to the [0.0, 1.0] range.

        Args:
            x: Raw normalized X.
            y: Raw normalized Y.

        Returns:
            Tuple[float, float]: Clamped (x, y).
        """
        return max(0.0, min(1.0, x)), max(0.0, min(1.0, y))
