"""Timeline Event Item Module.

Provides the EventItem class for rendering individual events on the timeline.
"""

import logging
from collections.abc import Callable
from typing import Any, Optional, cast

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from src.core.calendar import CalendarConverter
from src.core.events import Event
from src.core.temporal_display import TemporalDisplay, event_temporal_display
from src.core.temporal_expression import TemporalExpression, expression_from_attributes
from src.core.theme_manager import ThemeManager
from src.gui.constants import (
    TEMPORAL_FUTURE_LIGHTNESS_BOOST,
    TEMPORAL_FUTURE_OPACITY,
    TEMPORAL_FUTURE_SATURATION_FACTOR,
)
from src.gui.utils.style_helper import StyleHelper

logger = logging.getLogger(__name__)


class EventItem(QGraphicsItem):
    """Diamond-shaped event marker with text label.

    Theme-aware coloring.
    """

    MAX_WIDTH = 400  # Increased to fit longer calendar-formatted dates
    ICON_SIZE = 16  # Diamond size in pixels (increased from 14)
    PADDING = 5

    # Height constants for lane packing (includes label space)
    DURATION_EVENT_HEIGHT = 60  # Bar + label + date below
    POINT_EVENT_HEIGHT = 40  # Diamond + text to right

    # Class-level calendar converter (shared across all event items)
    _calendar_converter: CalendarConverter | None = None

    @classmethod
    def get_event_height(cls, event: Event) -> int:
        """Returns the visual height for an event based on its type.

        Args:
            event (Event): The Event object.

        Returns:
            int: Height in pixels.

        """
        if event.lore_duration > 0 or event.attributes.get("_temporal_v2", {}).get(
            "expression"
        ):
            return cls.DURATION_EVENT_HEIGHT
        return cls.POINT_EVENT_HEIGHT

    @classmethod
    def set_calendar_converter(cls, converter: CalendarConverter) -> None:
        """Sets the calendar converter for date formatting."""
        cls._calendar_converter = converter

    def __init__(self, event: Event, scale_factor: float = 10.0) -> None:
        """Initializes an EventBlock.

        Args:
            event (Event): The event to represent.
            scale_factor (float, optional): Scale factor for positioning.
                Defaults to 10.0.

        """
        super().__init__()
        self.event = event
        self.scale_factor = scale_factor

        self.base_color = QColor()
        self._text_color = QColor()
        self._secondary_text_color = QColor()
        self._border_color = QColor()
        self.refresh_theme(ThemeManager().get_theme())

        # Position is handled by parent/layout, but X is strictly date-based
        self.setPos(event.lore_date * scale_factor, 0)

        # Flags: Movable and fixed size on screen
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
            | QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations
            | QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )

        # Enable caching for improved rendering performance
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)

        # Set pointing hand cursor to indicate clickability
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Store initial Y position for constraining vertical movement
        self._initial_y = 0.0

        # Callback for when drag completes: fn(event_id, new_lore_date)
        self.on_drag_complete: Callable[[str, float], None] | None = None

        # Track if we're currently dragging
        self._is_dragging = False

        # Zoom level for scaling duration bars (updated by TimelineView)
        self._zoom_level = 1.0

        # Temporal State
        self.is_future = False
        self.is_past = False
        self._update_temporal_tooltip()

    def refresh_theme(self, theme: dict[str, str]) -> None:
        """Refresh cached rendering colors after a theme change.

        ``EventItem`` uses a device-coordinate cache, so a scene repaint alone
        cannot update colors that were resolved when the item was created.

        Args:
            theme: The active theme data emitted by :class:`ThemeManager`.

        """
        self.base_color = QColor(StyleHelper.get_event_color())
        self._text_color = QColor(theme["text_main"])
        self._secondary_text_color = QColor(theme["text_dim"])
        self._border_color = QColor(theme["border"])
        self.update()

    def set_temporal_state(self, is_future: bool, is_past: bool = False) -> None:
        """Updates the event's visual state based on its temporal relation.

        Args:
            is_future: If True, event is in the future (dull/faded).
            is_past: If True, event is in the past (reserved for "visited" styling).

        """
        if self.is_future == is_future and self.is_past == is_past:
            return

        self.is_future = is_future
        self.is_past = is_past

        # Update visual properties based on state
        if is_future:
            # Dulling effect: Reduced opacity
            self.setOpacity(TEMPORAL_FUTURE_OPACITY)
            # Saturation change happens in _get_effective_color()
        else:
            # Normal state: Vivid
            self.setOpacity(1.0)

        self.update()

    def _get_effective_color(self) -> QColor:
        """Returns the color modified by current state (e.g., desaturated if future).

        Returns:
            QColor: The effective color for rendering.

        """
        color = QColor(self.base_color)

        if self.is_future:
            # Desaturate significantly for future state
            h, s, lightness, a = cast(
                tuple[float, float, float, float], color.getHslF()
            )
            # Reduce saturation by 20% (keep 80%) for a subtle fade
            s = max(0.0, s * TEMPORAL_FUTURE_SATURATION_FACTOR)
            lightness = min(1.0, lightness + TEMPORAL_FUTURE_LIGHTNESS_BOOST)
            color = QColor.fromHslF(h, s, lightness, a)

        return color

    def set_zoom(self, zoom: float) -> None:
        """Updates the zoom level for duration bar scaling.

        This method is called by TimelineView when the zoom level changes.
        Duration bars will be drawn with width = duration * scale_factor * zoom.

        Args:
            zoom: The current zoom level of the timeline view.

        """
        if zoom != self._zoom_level:
            self.prepareGeometryChange()
            self._zoom_level = zoom
            self.update()

    def update_event(self, event: Event) -> None:
        """Updates the event data for this item and refreshes the display.

        Args:
            event (Event): The updated event object.

        """
        self.prepareGeometryChange()
        self.event = event
        self.refresh_theme(ThemeManager().get_theme())
        self.setPos(event.lore_date * self.scale_factor, self.y())
        self._update_temporal_tooltip()

    def _update_temporal_tooltip(self) -> None:
        display = event_temporal_display(self.event, self._calendar_converter)
        self.setToolTip(
            f"{self.event.name}\n{display.caption}\n"
            "Dotted outline: possible dates, not duration. Hatched area: possible presence. "
            "Solid interior: certainly present. ?: no finite evidence bounds."
            if display
            else self.event.name
        )

    def _evidence_rect(self, start: float, end: float) -> QRectF:
        scale = self.scale_factor * self._zoom_level
        return QRectF(
            (start - self.event.lore_date) * scale,
            -6,
            max(1, (end - start) * scale),
            12,
        )

    def _display_rect(self, display: TemporalDisplay) -> QRectF:
        if display.possible_start is None or display.possible_end is None:
            return QRectF(-7, -7, 14, 14)
        return self._evidence_rect(display.possible_start, display.possible_end)

    def _uncertainty_rect(self) -> QRectF:
        """Return positional uncertainty separately from actual duration."""
        expression = expression_from_attributes(self.event.attributes)
        if expression is None or self._calendar_converter is None:
            return QRectF()
        bounds = expression.resolve_bounds(self._calendar_converter)
        if not bounds.has_hard_bounds:
            return QRectF(-10, -9, 20, 18)
        assert bounds.hard_start is not None and bounds.hard_end is not None
        scale = self.scale_factor * self._zoom_level
        return QRectF(
            (bounds.hard_start - self.event.lore_date) * scale,
            -22,
            max(1.0, (bounds.hard_end - bounds.hard_start) * scale),
            6,
        )

    def _end_uncertainty_rect(self) -> QRectF:
        """Draw the duration endpoint's uncertainty separately from its start."""
        data = self.event.attributes.get("_temporal_v2", {}).get("end_expression")
        if not data or self._calendar_converter is None:
            return QRectF()
        bounds = TemporalExpression.from_dict(data).resolve_bounds(
            self._calendar_converter
        )
        if not bounds.has_hard_bounds:
            return QRectF(
                self.event.lore_duration * self.scale_factor * self._zoom_level - 10,
                -9,
                20,
                18,
            )
        assert bounds.hard_start is not None and bounds.hard_end is not None
        scale = self.scale_factor * self._zoom_level
        return QRectF(
            (bounds.hard_start - self.event.lore_date) * scale,
            -22,
            max(1.0, (bounds.hard_end - bounds.hard_start) * scale),
            6,
        )

    def boundingRect(self) -> QRectF:
        """Defines the redrawable area of the item.

        Includes the diamond icon and the text label. Refreshed when selection changes
        (border width).
        """
        display = event_temporal_display(self.event, self._calendar_converter)
        if display is not None:
            rect = self._display_rect(display)
            return rect.united(
                QRectF(
                    rect.left(), 7, max(self.MAX_WIDTH, len(display.caption) * 7), 32
                )
            ).adjusted(-2, -2, 2, 2)
        if self.event.lore_duration > 0:
            # Width scales with zoom to match the timeline grid
            width = self.event.lore_duration * self.scale_factor * self._zoom_level
            # Ensure minimum width for visibility and clicking
            width = max(width, 10)
            # Extra height below for label + date
            return (
                QRectF(0, -10, max(width, self.MAX_WIDTH), 50)
                .united(self._uncertainty_rect())
                .united(self._end_uncertainty_rect())
            )

        # Bounding box includes Diamond + Text (extra height for date line)
        return (
            QRectF(
                -self.ICON_SIZE, -self.ICON_SIZE, self.MAX_WIDTH, self.ICON_SIZE * 2 + 8
            )
            .united(self._uncertainty_rect())
            .united(self._end_uncertainty_rect())
        )

    def shape(self) -> QPainterPath:
        """Defines the clickable area of the item. Only includes the diamond icon (or
        duration bar), not the text labels.

        Returns:
            QPainterPath: The clickable region path.

        """
        path = QPainterPath()

        display = event_temporal_display(self.event, self._calendar_converter)
        if display is not None:
            path.addRect(self._display_rect(display).adjusted(-2, -2, 2, 2))
            return path

        if self.event.lore_duration > 0:
            # For duration events, the bar is clickable
            # Width scales with zoom to match the timeline grid
            width = self.event.lore_duration * self.scale_factor * self._zoom_level
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

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Handles mouse press to track drag state.

        Args:
            event: The mouse event.

        """
        super().mousePressEvent(event)
        # Mark that user initiated a drag - used by itemChange to know
        # when to apply constraints vs allowing programmatic moves
        self._is_dragging = True
        # Capture current Y as the constraint value at drag start
        self._initial_y = self.y()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        """Handles item changes to constrain dragging to horizontal only and update the
        lore_date during drag.

        Args:
            change: The type of change.
            value: The new value.

        Returns:
            The constrained value.

        """
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
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

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Handles mouse release to emit drag completion callback.

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

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        """Custom painting for the Event Marker.

        Draws a diamond shape and a text label.
        """
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        display = event_temporal_display(self.event, self._calendar_converter)
        if display is not None:
            self._paint_temporal_display(painter, display)
            return
        for uncertainty in (self._uncertainty_rect(), self._end_uncertainty_rect()):
            if not uncertainty.isEmpty():
                painter.save()
                pen = QPen(self._secondary_text_color)
                pen.setStyle(Qt.PenStyle.DotLine)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(uncertainty)
                painter.restore()

        if self.event.lore_duration > 0:
            self._paint_duration_bar(painter)
        else:
            self._paint_point_event(painter)

    def _paint_temporal_display(
        self, painter: QPainter, display: TemporalDisplay
    ) -> None:
        """Paint possible extent and certain interior, never a midpoint duration bar."""
        painter.save()
        rect = self._display_rect(display)
        pen = QPen(self._get_effective_color())
        pen.setCosmetic(True)
        pen.setWidth(2 if self.isSelected() else 1)
        pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        bounded = (
            display.possible_start is not None and display.possible_end is not None
        )
        if bounded:
            if self.event.lore_duration > 0:
                painter.setBrush(
                    QBrush(self._get_effective_color(), Qt.BrushStyle.BDiagPattern)
                )
            painter.drawRect(rect)
            if display.certain_start is not None and display.certain_end is not None:
                painter.fillRect(
                    self._evidence_rect(display.certain_start, display.certain_end),
                    self._get_effective_color(),
                )
        else:
            painter.drawEllipse(rect)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "?")
        painter.setPen(self._text_color)
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QPointF(rect.left(), 20), self.event.name)
        font.setBold(False)
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(self._secondary_text_color)
        painter.drawText(QPointF(rect.left(), 32), display.caption)
        painter.restore()

    def _paint_duration_bar(self, painter: QPainter) -> None:
        """Draws the event as a horizontal bar spanning its duration."""
        # Width scales with zoom to match the timeline grid
        width = self.event.lore_duration * self.scale_factor * self._zoom_level
        width = max(width, 10)  # Minimum width visual

        rect = QRectF(0, -6, width, 12)

        brush = QBrush(self._get_effective_color())
        if self.isSelected():
            brush.setColor(self.base_color.lighter(130))

        painter.setBrush(brush)

        pen = QPen(self._text_color if self.isSelected() else self._border_color)
        pen.setCosmetic(True)
        pen.setWidth(2 if self.isSelected() else 1)
        painter.setPen(pen)

        # Draw rounded rect for the bar
        painter.drawRoundedRect(rect, 4, 4)

        # Draw Text Label BELOW the bar
        painter.setPen(QPen(self._text_color))

        font = painter.font()
        font.setBold(True)
        painter.setFont(font)

        # Event name below the bar
        label_y = rect.bottom() + 14
        painter.drawText(QPointF(0, label_y), self.event.name)

        # Date below the name
        font.setBold(False)
        font.setPointSize(8)
        painter.setFont(font)

        if EventItem._calendar_converter:
            try:
                expression = expression_from_attributes(self.event.attributes)
                date_str = (
                    expression.display_text(EventItem._calendar_converter)
                    if expression
                    else EventItem._calendar_converter.format_date(self.event.lore_date)
                )
            except Exception as e:
                logger.warning(
                    f"Calendar conversion failed for date {self.event.lore_date}: {e}"
                )
                date_str = f"{self.event.lore_date:,.1f}"
        else:
            date_str = f"{self.event.lore_date:,.1f}"

        painter.setPen(QPen(self._secondary_text_color))
        painter.drawText(QPointF(0, label_y + 12), date_str)

    def _paint_point_event(self, painter: QPainter) -> None:
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

        brush = QBrush(self._get_effective_color())
        if self.isSelected():
            brush.setColor(self.base_color.lighter(130))

        painter.setBrush(brush)

        # Border
        pen = QPen(self._text_color if self.isSelected() else self._border_color)
        pen.setCosmetic(True)  # Keep border crisp
        pen.setWidth(2 if self.isSelected() else 1)
        painter.setPen(pen)

        painter.drawPolygon(diamond)

        # 2. Draw Text Label (to the right)
        text_x = self.ICON_SIZE / 2 + self.PADDING

        # Title
        painter.setPen(QPen(self._text_color))
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
                expression = expression_from_attributes(self.event.attributes)
                date_str = (
                    expression.display_text(EventItem._calendar_converter)
                    if expression
                    else EventItem._calendar_converter.format_date(self.event.lore_date)
                )
            except Exception as e:
                logger.warning(
                    f"Calendar conversion failed for date {self.event.lore_date}: {e}"
                )
                date_str = f"{self.event.lore_date:,.1f}"
        else:
            date_str = f"{self.event.lore_date:,.1f}"
        painter.setPen(QPen(self._secondary_text_color))
        painter.drawText(QPointF(text_x, 10), date_str)
