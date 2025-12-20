"""
Timeline Event Item Module.

Provides the EventItem class for rendering individual events on the timeline.
"""

import logging
from PySide6.QtWidgets import QGraphicsItem
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QBrush,
    QPen,
    QColor,
    QPainter,
    QPolygonF,
    QPainterPath,
    QCursor,
)

logger = logging.getLogger(__name__)


class EventItem(QGraphicsItem):
    """
    Diamond-shaped event marker with text label.
    Color-coded by event type.
    """

    COLORS = {
        "generic": QColor("#888888"),
        "cosmic": QColor("#8E44AD"),  # Purple
        "historical": QColor("#F39C12"),  # Orange
        "personal": QColor("#2ECC71"),  # Green
        "session": QColor("#3498DB"),  # Blue
        "combat": QColor("#E74C3C"),  # Red
    }

    MAX_WIDTH = 400  # Increased to fit longer calendar-formatted dates
    ICON_SIZE = 16  # Diamond size in pixels (increased from 14)
    PADDING = 5

    # Class-level calendar converter (shared across all event items)
    _calendar_converter = None

    @classmethod
    def set_calendar_converter(cls, converter):
        """Sets the calendar converter for date formatting."""
        cls._calendar_converter = converter

    def __init__(self, event, scale_factor=10.0):
        """
        Initializes an EventBlock.

        Args:
            event (Event): The event to represent.
            scale_factor (float, optional): Scale factor for positioning.
                Defaults to 10.0.
        """
        super().__init__()
        self.event = event
        self.scale_factor = scale_factor

        # Determine Color
        self.base_color = self.COLORS.get(event.type, self.COLORS["generic"])

        # Position is handled by parent/layout, but X is strictly date-based
        self.setPos(event.lore_date * scale_factor, 0)

        # Flags: Movable and fixed size on screen
        self.setFlags(
            QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemIsFocusable
            | QGraphicsItem.ItemIgnoresTransformations
            | QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemSendsGeometryChanges
        )

        # Enable caching for improved rendering performance
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)

        # Set pointing hand cursor to indicate clickability
        self.setCursor(QCursor(Qt.PointingHandCursor))

        # Store initial Y position for constraining vertical movement
        self._initial_y = 0.0

        # Callback for when drag completes: fn(event_id, new_lore_date)
        self.on_drag_complete = None

        # Track if we're currently dragging
        self._is_dragging = False

    def update_event(self, event):
        """
        Updates the event data for this item and refreshes the display.

        Args:
            event (Event): The updated event object.
        """
        self.prepareGeometryChange()
        self.event = event
        self.base_color = self.COLORS.get(event.type, self.COLORS["generic"])
        self.setPos(event.lore_date * self.scale_factor, self.y())
        self.update()

    def boundingRect(self) -> QRectF:
        """
        Defines the redrawable area of the item.
        Includes the diamond icon and the text label.
        Refreshed when selection changes (border width).
        """
        if self.event.lore_duration > 0:
            width = self.event.lore_duration * self.scale_factor
            # Ensure minimum width for visibility and clicking
            width = max(width, 10)
            return QRectF(0, -10, width, 30)

        # Bounding box includes Diamond + Text (extra height for date line)
        return QRectF(
            -self.ICON_SIZE, -self.ICON_SIZE, self.MAX_WIDTH, self.ICON_SIZE * 2 + 8
        )

    def shape(self) -> QPainterPath:
        """
        Defines the clickable area of the item.
        Only includes the diamond icon (or duration bar), not the text labels.

        Returns:
            QPainterPath: The clickable region path.
        """
        path = QPainterPath()

        if self.event.lore_duration > 0:
            # For duration events, the bar is clickable
            width = self.event.lore_duration * self.scale_factor
            width = max(width, 10)
            path.addRoundedRect(QRectF(0, -6, width, 12), 4, 4)
        else:
            # For point events, only the diamond is clickable
            half = self.ICON_SIZE / 2
            diamond = QPolygonF(
                [
                    QPointF(0, -half),
                    QPointF(half, 0),
                    QPointF(0, half),
                    QPointF(-half, 0),
                ]
            )
            path.addPolygon(diamond)

        return path

    def mousePressEvent(self, event):
        """
        Handles mouse press to track drag state.

        Args:
            event: The mouse event.
        """
        super().mousePressEvent(event)
        # Mark that user initiated a drag - used by itemChange to know
        # when to apply constraints vs allowing programmatic moves
        self._is_dragging = True
        # Capture current Y as the constraint value at drag start
        self._initial_y = self.y()

    def itemChange(self, change, value):
        """
        Handles item changes to constrain dragging to horizontal only
        and update the lore_date during drag.

        Args:
            change: The type of change.
            value: The new value.

        Returns:
            The constrained value.
        """
        if change == QGraphicsItem.ItemPositionChange:
            new_pos = value

            # Only constrain Y during user-initiated drags
            if self._is_dragging:
                new_pos.setY(self._initial_y)

                # Update the event's lore_date based on new X position
                new_lore_date = new_pos.x() / self.scale_factor
                self.event.lore_date = new_lore_date

                # Trigger repaint to update the displayed date
                self.update()

            return new_pos
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event):
        """
        Handles mouse release to emit drag completion callback.

        Args:
            event: The mouse event.
        """
        super().mouseReleaseEvent(event)

        if self._is_dragging:
            self._is_dragging = False

            # Emit callback with final position
            if self.on_drag_complete:
                new_lore_date = self.x() / self.scale_factor
                self.on_drag_complete(self.event.id, new_lore_date)

    def paint(self, painter, option, widget=None):
        """
        Custom painting for the Event Marker.
        Draws a diamond shape and a text label.
        """
        painter.setRenderHint(QPainter.Antialiasing)

        if self.event.lore_duration > 0:
            self._paint_duration_bar(painter)
        else:
            self._paint_point_event(painter)

    def _paint_duration_bar(self, painter):
        """Draws the event as a horizontal bar spanning its duration."""
        width = self.event.lore_duration * self.scale_factor
        width = max(width, 10)  # Minimum width visual

        rect = QRectF(0, -6, width, 12)

        brush = QBrush(self.base_color)
        if self.isSelected():
            brush.setColor(self.base_color.lighter(130))

        painter.setBrush(brush)

        pen = QPen(Qt.white if self.isSelected() else Qt.black)
        pen.setCosmetic(True)
        pen.setWidth(2 if self.isSelected() else 1)
        painter.setPen(pen)

        # Draw rounded rect for the bar
        painter.drawRoundedRect(rect, 4, 4)

        # Draw Text Label (inside if fits, otherwise right)
        painter.setPen(QPen(Qt.white))

        font = painter.font()
        font.setBold(True)
        painter.setFont(font)

        # Check if text fits inside
        fm = painter.fontMetrics()
        text_width = fm.horizontalAdvance(self.event.name)

        if text_width < width - 10:
            # Draw inside
            painter.drawText(rect, Qt.AlignCenter, self.event.name)
        else:
            # Draw to the right
            painter.drawText(QPointF(width + 5, 4), self.event.name)

    def _paint_point_event(self, painter):
        """Draws the standard diamond marker for point events."""
        # 1. Draw Diamond Icon
        half = self.ICON_SIZE / 2
        diamond = QPolygonF(
            [
                QPointF(0, -half),
                QPointF(half, 0),
                QPointF(0, half),
                QPointF(-half, 0),
            ]
        )

        brush = QBrush(self.base_color)
        if self.isSelected():
            brush.setColor(self.base_color.lighter(130))

        painter.setBrush(brush)

        # Border
        pen = QPen(Qt.white if self.isSelected() else Qt.black)
        pen.setCosmetic(True)  # Keep border crisp
        pen.setWidth(2 if self.isSelected() else 1)
        painter.setPen(pen)

        painter.drawPolygon(diamond)

        # 2. Draw Text Label (to the right)
        text_x = self.ICON_SIZE / 2 + self.PADDING

        # Title
        painter.setPen(QPen(Qt.white))
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QPointF(text_x, -2), self.event.name)

        # Date - use calendar converter if available
        font.setBold(False)
        font.setPointSize(8)
        painter.setFont(font)
        if EventItem._calendar_converter:
            try:
                date_str = EventItem._calendar_converter.format_date(
                    self.event.lore_date
                )
            except Exception:
                date_str = f"{self.event.lore_date:,.1f}"
        else:
            date_str = f"{self.event.lore_date:,.1f}"
        painter.setPen(QPen(QColor(180, 180, 180)))
        painter.drawText(QPointF(text_x, 10), date_str)
