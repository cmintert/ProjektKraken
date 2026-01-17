"""
Geometry Utilities.

Provides helper functions for ensuring windows and widgets remain visible on screen,
handling multi-monitor boundary checks, and sanitizing geometry rectangles.
"""

from typing import Optional

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication, QScreen


class GeometryUtils:
    """
    Static utility class for geometry validation and sanitization.
    """

    @staticmethod
    def ensure_on_screen(rect: QRect) -> QRect:
        """
        Adjusts the given rectangle to ensure it is visible on the nearest screen.

        Algorithm:
        1. Find the screen that contains the largest area of the rect.
        2. If no screen overlaps, find the nearest screen to the rect's center.
        3. Clamp the rect to fit within that screen's available geometry.

        Args:
            rect: The window geometry to validate.

        Returns:
            QRect: The adjusted geometry, guaranteed to be visible.
        """
        # If no screens available (headless?), return as is
        screens = QGuiApplication.screens()
        if not screens:
            return rect

        # 1. Find screen with largest intersection
        max_area = 0
        best_screen: Optional[QScreen] = None

        for screen in screens:
            available_geo = screen.availableGeometry()
            intersect = available_geo.intersected(rect)
            area = intersect.width() * intersect.height()
            if area > max_area:
                max_area = area
                best_screen = screen

        # 2. If no intersection, find closest screen
        if not best_screen:
            center = rect.center()
            min_dist = float("inf")
            for screen in screens:
                screen_center = screen.availableGeometry().center()
                # Simple Manhattan distance for speed
                dist = abs(center.x() - screen_center.x()) + abs(
                    center.y() - screen_center.y()
                )
                if dist < min_dist:
                    min_dist = dist
                    best_screen = screen

        # Should be guaranteed to have best_screen now if screens existed
        if not best_screen:
            best_screen = QGuiApplication.primaryScreen()

        # 3. Clamp to available geometry
        available_geo = best_screen.availableGeometry()

        # Create localized rect to modify
        new_rect = QRect(rect)

        # Ensure size fits
        if new_rect.width() > available_geo.width():
            new_rect.setWidth(available_geo.width())
        if new_rect.height() > available_geo.height():
            new_rect.setHeight(available_geo.height())

        # Ensure position is inside
        # Right/Bottom check first (pull back in)
        if new_rect.right() > available_geo.right():
            new_rect.moveRight(available_geo.right())
        if new_rect.bottom() > available_geo.bottom():
            new_rect.moveBottom(available_geo.bottom())

        # Left/Top check second (prioritize top-left visibility)
        if new_rect.left() < available_geo.left():
            new_rect.moveLeft(available_geo.left())
        if new_rect.top() < available_geo.top():
            new_rect.moveTop(available_geo.top())

        return new_rect

    @staticmethod
    def is_safe_geometry(rect: QRect, min_intersection_percent: float = 0.5) -> bool:
        """
        Checks if a rectangle is sufficiently visible on any screen.

        Args:
            rect: The geometry to check.
            min_intersection_percent: Required visible percentage (0.0 - 1.0).

        Returns:
            bool: True if safe, False if potentially off-screen.
        """
        screens = QGuiApplication.screens()
        total_intersection_area = 0
        rect_area = rect.width() * rect.height()

        if rect_area <= 0:
            return False

        for screen in screens:
            intersect = screen.availableGeometry().intersected(rect)
            total_intersection_area += intersect.width() * intersect.height()

        return (total_intersection_area / rect_area) >= min_intersection_percent
