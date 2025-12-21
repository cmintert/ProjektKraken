"""
Timeline Scene and Playhead Items Module.

Provides scene and playhead components for the timeline visualization.
"""

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QCursor, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsLineItem, QGraphicsScene

from src.core.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class TimelineScene(QGraphicsScene):
    """
    Custom Graphics Scene for the Timeline.
    Sets the background color consistent with the app theme.
    """

    def __init__(self, parent=None):
        """
        Initializes the TimelineScene.

        Args:
            parent (QObject, optional): The parent object. Defaults to None.
        """
        super().__init__(parent)
        self.tm = ThemeManager()
        self.tm.theme_changed.connect(self._update_theme)
        self._update_theme(self.tm.get_theme())

    def _update_theme(self, theme):
        """Updates the scene background."""
        self.setBackgroundBrush(QBrush(QColor(theme["app_bg"])))


class PlayheadItem(QGraphicsLineItem):
    """
    Draggable vertical line representing the current playback position.
    """

    def __init__(self, parent=None):
        """
        Initializes the PlayheadItem.

        Args:
            parent: Parent graphics item.
        """
        super().__init__(0, -100000, 0, 100000, parent)

        # Style
        pen = QPen(QColor(255, 100, 100), 2)  # Red playhead
        pen.setCosmetic(True)
        self.setPen(pen)

        # Make draggable
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

        # Cursor hint
        self.setCursor(QCursor(Qt.SizeHorCursor))

        # Set high Z value to appear on top
        self.setZValue(100)

        # Callback for movement
        self.on_moved = None

        # Track vertical extent
        self._top = -100000.0
        self._bottom = 100000.0  # Vertically infinite-ish

    def shape(self):
        """
        Define a wider hit area for easier grabbing.
        Returns a path roughly 10px wide centered on the line.
        """
        path = QPainterPath()
        # Create a rectangle 20px wide centered on x=0
        # Spanning the vertical extent (or just a large range if infinite)
        # Using a finite but large range ensures it works within reasonable view limits
        path.addRect(-10, -100000, 20, 200000)
        return path

    def itemChange(self, change, value):
        """
        Handles item changes to constrain dragging to horizontal only.

        Args:
            change: The type of change.
            value: The new value.

        Returns:
            The constrained value.
        """
        if change == QGraphicsItem.ItemPositionChange:
            # Constrain to horizontal movement only
            new_pos = value
            new_pos.setY(0)

            # Notify listener if set (interactive drag)
            if self.scene() and self.on_moved:
                # Check if this change is likely from mouse interaction
                # (simplest is just to emit always)
                self.on_moved(new_pos.x())

            return new_pos
        return super().itemChange(change, value)

    def set_time(self, time: float, scale_factor: float):
        """
        Sets the playhead position to the given time.

        Args:
            time: The time position in lore_date units.
            scale_factor: Pixels per day conversion factor.
        """
        self._time = time
        x = time * scale_factor
        self.setPos(x, 0)

    def get_time(self, scale_factor: float) -> float:
        """
        Gets the current time position of the playhead.

        Args:
            scale_factor: Pixels per day conversion factor.

        Returns:
            The current time in lore_date units.
        """
        return self.x() / scale_factor


class CurrentTimeLineItem(QGraphicsLineItem):
    """
    Non-draggable vertical line representing the current time in the world.
    This is distinct from the playhead and represents the "now" of the world.
    """

    def __init__(self, parent=None):
        """
        Initializes the CurrentTimeLineItem.

        Args:
            parent: Parent graphics item.
        """
        super().__init__(0, -100000, 0, 100000, parent)

        # Style - distinct from playhead (blue instead of red)
        pen = QPen(QColor(100, 150, 255), 3)  # Blue current time line, thicker
        pen.setCosmetic(True)
        pen.setStyle(Qt.DashLine)  # Dashed to distinguish from playhead
        self.setPen(pen)

        # Not draggable - set programmatically only
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)

        # Set high Z value but below playhead
        self.setZValue(99)

        # Track current time position
        self._time = 0.0

    def set_time(self, time: float, scale_factor: float):
        """
        Sets the current time line position to the given time.

        Args:
            time: The time position in lore_date units.
            scale_factor: Pixels per day conversion factor.
        """
        self._time = time
        x = time * scale_factor
        self.setPos(x, 0)

    def get_time(self, scale_factor: float) -> float:
        """
        Gets the current time position.

        Args:
            scale_factor: Pixels per day conversion factor.

        Returns:
            The current time in lore_date units.
        """
        return self.x() / scale_factor
