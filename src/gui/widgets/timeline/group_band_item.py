"""
Group Band Item Module.

Provides the GroupBandItem widget for displaying tag-based grouping bands
on the timeline. Bands are thin, colored, collapsible elements that stack
above the timeline lanes.
"""

import logging

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsObject

from src.core.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class GroupBandItem(QGraphicsObject):
    """
    A thin colored band representing a tag group on the timeline.

    Features:
    - Colored bar with tag name
    - Collapsible to show just a thin line with ticks
    - Tooltip showing count and date span
    - Context menu for tag operations
    - Click to expand/collapse
    """

    # Signals
    expand_requested = Signal(str)  # tag_name
    collapse_requested = Signal(str)  # tag_name
    context_menu_requested = Signal(str, object)  # tag_name, QPoint
    reorder_requested = Signal(str, int)  # tag_name, new_index

    # Constants
    BAND_HEIGHT_COLLAPSED = 24  # Keep same height as expanded
    BAND_HEIGHT_EXPANDED = 24  # Full height when expanded
    BAND_MARGIN = 2  # Margin between bands

    def __init__(
        self,
        tag_name: str,
        color: str,
        count: int,
        earliest_date: float,
        latest_date: float,
        is_collapsed: bool = False,
        parent=None,
    ):
        """
        Initializes the GroupBandItem.

        Args:
            tag_name: The name of the tag this band represents
            color: Hex color string (e.g., "#FF0000")
            count: Number of events in this group
            earliest_date: Earliest event date in the group
            latest_date: Latest event date in the group
            is_collapsed: Whether the band starts collapsed
            parent: Parent graphics item
        """
        super().__init__(parent)

        self.tag_name = tag_name
        self._color = QColor(color)
        self.count = count
        self.earliest_date = earliest_date if earliest_date is not None else 0.0
        self.latest_date = latest_date if latest_date is not None else 0.0
        self.is_collapsed = is_collapsed

        # Event positions for tick marks
        self.event_dates = []  # List of lore_dates for events in this group

        # Visual settings
        self.setAcceptHoverEvents(True)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setZValue(50)  # Above timeline content, below playhead

        # Interaction state
        self._hovered = False
        self._pressed = False

        # Theme
        self.theme = ThemeManager().get_theme()
        ThemeManager().theme_changed.connect(self._on_theme_changed)

        # Tooltip
        self._update_tooltip()

    def _on_theme_changed(self, theme):
        """Update theme and refresh."""
        self.theme = theme
        self.update()

    def _update_tooltip(self):
        """Update the tooltip with current metadata."""
        if self.count == 0:
            tooltip = f"{self.tag_name}\nNo events"
        else:
            date_range = f"{self.earliest_date:.1f} - {self.latest_date:.1f}"
            span = self.latest_date - self.earliest_date
            tooltip = (
                f"<b>{self.tag_name}</b><br>"
                f"Events: {self.count}<br>"
                f"Range: {date_range}<br>"
                f"Span: {span:.1f}"
            )
        self.setToolTip(tooltip)

    def boundingRect(self) -> QRectF:
        """
        Returns the bounding rectangle for the band.

        The band spans horizontally across the entire visible timeline
        (effectively infinite) and has a height based on collapsed state.
        """
        height = (
            self.BAND_HEIGHT_COLLAPSED
            if self.is_collapsed
            else self.BAND_HEIGHT_EXPANDED
        )
        # Return a very wide rect to span the timeline
        return QRectF(-1e12, 0, 2e12, height)

    def paint(self, painter: QPainter, option, widget=None):
        """
        Paints the group band.

        Args:
            painter: The QPainter to use for drawing
            option: Style options (unused)
            widget: The widget being painted on (unused)
        """
        painter.setRenderHint(QPainter.Antialiasing)

        height = (
            self.BAND_HEIGHT_COLLAPSED
            if self.is_collapsed
            else self.BAND_HEIGHT_EXPANDED
        )

        # Get visible rect from the view
        if widget:
            view_rect = widget.rect()
            # Map to scene coordinates
            scene_rect = painter.transform().inverted()[0].mapRect(QRectF(view_rect))
        else:
            # Fallback to a large rect
            scene_rect = QRectF(-10000, 0, 20000, height)

        # Background color (slightly transparent)
        bg_color = QColor(self._color)
        if self.is_collapsed:
            bg_color.setAlphaF(0.6)
        else:
            bg_color.setAlphaF(0.3)

        # Hover effect
        if self._hovered and not self.is_collapsed:
            bg_color = bg_color.lighter(120)

        # Draw background
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRect(scene_rect.left(), 0, scene_rect.width(), height)

        # Draw border
        border_color = QColor(self._color).darker(120)
        painter.setPen(QPen(border_color, 1))
        painter.drawLine(
            int(scene_rect.left()),
            int(height - 1),
            int(scene_rect.right()),
            int(height - 1),
        )

        if not self.is_collapsed:
            # No internal labels drawn here anymore - handled by GroupLabelOverlay
            pass
        else:
            # Draw tick marks for collapsed band
            if self.event_dates:
                # Get scale factor from parent if available
                scale_factor = 20.0  # Default
                if hasattr(self.scene(), "views") and self.scene().views():
                    view = self.scene().views()[0]
                    if hasattr(view, "scale_factor"):
                        scale_factor = view.scale_factor

                # Draw vertical tick for each event
                tick_color = QColor(self._color).lighter(150)
                painter.setPen(QPen(tick_color, 1))

                for event_date in self.event_dates:
                    # Calculate X position
                    x_pos = event_date * scale_factor

                    # Only draw if in visible range
                    if scene_rect.left() <= x_pos <= scene_rect.right():
                        painter.drawLine(int(x_pos), 0, int(x_pos), int(height))

    def mousePressEvent(self, event):
        """Handle mouse press."""
        if event.button() == Qt.LeftButton:
            self._pressed = True
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release to toggle collapse state."""
        if event.button() == Qt.LeftButton and self._pressed:
            self._pressed = False
            # Toggle collapse state
            if self.is_collapsed:
                self.expand_requested.emit(self.tag_name)
            else:
                self.collapse_requested.emit(self.tag_name)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        """Handle context menu request."""
        self.context_menu_requested.emit(self.tag_name, event.screenPos())
        event.accept()

    def hoverEnterEvent(self, event):
        """Handle hover enter."""
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """Handle hover leave."""
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def set_collapsed(self, collapsed: bool):
        """
        Set the collapsed state of the band.

        Args:
            collapsed: True to collapse, False to expand
        """
        if self.is_collapsed != collapsed:
            self.is_collapsed = collapsed
            self.prepareGeometryChange()
            self.update()

    def set_color(self, color: str):
        """
        Update the band color.

        Args:
            color: Hex color string (e.g., "#FF0000")
        """
        self._color = QColor(color)
        self.update()

    def update_metadata(self, count: int, earliest_date: float, latest_date: float):
        """
        Update the band metadata.

        Args:
            count: Number of events in this group
            earliest_date: Earliest event date in the group
            latest_date: Latest event date in the group
        """
        self.count = count
        self.earliest_date = earliest_date if earliest_date is not None else 0.0
        self.latest_date = latest_date if latest_date is not None else 0.0
        self._update_tooltip()
        self.update()

    def set_event_dates(self, event_dates: list):
        """
        Set the event dates for tick mark rendering.

        Args:
            event_dates: List of lore_dates for events in this group
        """
        self.event_dates = event_dates
        self.update()

    def get_height(self) -> int:
        """
        Get the current height of the band.

        Returns:
            Height in pixels
        """
        return (
            self.BAND_HEIGHT_COLLAPSED
            if self.is_collapsed
            else self.BAND_HEIGHT_EXPANDED
        )
