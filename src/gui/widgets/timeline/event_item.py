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
    QLinearGradient,
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
from src.core.theme_manager import ThemeManager
from src.gui.constants import (
    TEMPORAL_FUTURE_LIGHTNESS_BOOST,
    TEMPORAL_FUTURE_OPACITY,
    TEMPORAL_FUTURE_SATURATION_FACTOR,
)
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.timeline.temporal_geometry import (
    TemporalGeometry,
    project_temporal_geometry,
)

logger = logging.getLogger(__name__)


class EventItem(QGraphicsItem):
    """Unified evidence-aware event marker with text label.

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
            "end_expression"
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
            "Solid diamond: precise point. Hollow diamond: layout anchor, "
            "not an exact date. Dotted caps: possible occurrence dates. "
            "Soft halo: no hard date limits. Hatching: possible duration. "
            "Solid bar: certainly ongoing. ?: timing unresolved."
        )

    def _geometry(self, display: TemporalDisplay) -> TemporalGeometry:
        return project_temporal_geometry(display, self.scale_factor * self._zoom_level)

    def _display_rect(self, display: TemporalDisplay) -> QRectF:
        """Return the same screen geometry used by painting and hit testing."""
        geometry = self._geometry(display)
        return QRectF(geometry.left, -8, geometry.right - geometry.left, 16)

    def boundingRect(self) -> QRectF:
        """Defines the redrawable area of the item.

        Includes the diamond icon and the text label. Refreshed when selection changes
        (border width).
        """
        display = event_temporal_display(self.event, self._calendar_converter)
        geometry = self._geometry(display)
        symbol = self._display_rect(display)
        label_y = -10 if geometry.mode == "exact" else 8
        label = QRectF(
            geometry.label_left,
            label_y,
            max(self.MAX_WIDTH, len(display.caption) * 7),
            30 if geometry.mode == "exact" else 32,
        )
        return symbol.united(label).adjusted(-2, -2, 2, 2)

    def shape(self) -> QPainterPath:
        """Defines the clickable area of the item. Only includes the diamond icon (or
        duration bar), not the text labels.

        Returns:
            QPainterPath: The clickable region path.

        """
        path = QPainterPath()

        display = event_temporal_display(self.event, self._calendar_converter)
        path.addRect(self._display_rect(display).adjusted(-2, -2, 2, 2))
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
        """Draw one visual grammar for legacy and semantic event dates."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        display = event_temporal_display(self.event, self._calendar_converter)
        geometry = self._geometry(display)
        painter.save()
        color = self._get_effective_color()
        pen = QPen(self._text_color if self.isSelected() else color)
        pen.setCosmetic(True)
        pen.setWidth(2 if self.isSelected() else 1)
        painter.setPen(pen)
        if geometry.mode == "duration":
            self._paint_duration(painter, geometry, color)
        elif geometry.mode == "unresolved":
            painter.setBrush(
                QBrush(color, Qt.BrushStyle.BDiagPattern)
                if display.kind == "duration"
                else QBrush(Qt.BrushStyle.NoBrush)
            )
            if display.kind == "duration":
                painter.drawRect(self._display_rect(display))
            else:
                painter.drawEllipse(self._display_rect(display))
            painter.drawText(
                self._display_rect(display), Qt.AlignmentFlag.AlignCenter, "?"
            )
        else:
            self._paint_occurrence(painter, geometry, color)
        self._paint_labels(painter, display, geometry)
        painter.restore()

    def _paint_occurrence(
        self, painter: QPainter, geometry: TemporalGeometry, color: QColor
    ) -> None:
        """Draw a point with a precision window, bounded window, or soft halo."""
        if geometry.mode in {"window", "one_sided", "soft"}:
            line_brush = QBrush(color)
            if geometry.mode in {"soft", "one_sided"}:
                gradient = QLinearGradient(geometry.left, 0, geometry.right, 0)
                transparent = QColor(color)
                transparent.setAlpha(0)
                faint = QColor(color)
                faint.setAlpha(65)
                if geometry.mode == "one_sided" and geometry.cap_left:
                    gradient.setColorAt(0, faint)
                    gradient.setColorAt(1, transparent)
                elif geometry.mode == "one_sided":
                    gradient.setColorAt(0, transparent)
                    gradient.setColorAt(1, faint)
                else:
                    gradient.setColorAt(0, transparent)
                    gradient.setColorAt(0.5, faint)
                    gradient.setColorAt(1, transparent)
                painter.fillRect(
                    QRectF(geometry.left, -6, geometry.right - geometry.left, 12),
                    QBrush(gradient),
                )
                line_brush = QBrush(gradient)
            else:
                faint = QColor(color)
                faint.setAlpha(35)
                painter.fillRect(
                    QRectF(geometry.left, -6, geometry.right - geometry.left, 12),
                    faint,
                )
            dotted = QPen(line_brush, 2 if self.isSelected() else 1)
            dotted.setCosmetic(True)
            dotted.setStyle(Qt.PenStyle.DotLine)
            painter.setPen(dotted)
            if geometry.left < geometry.marker_x - 5:
                painter.drawLine(
                    QPointF(geometry.left, 0),
                    QPointF(geometry.marker_x - 5, 0),
                )
            if geometry.marker_x + 5 < geometry.right:
                painter.drawLine(
                    QPointF(geometry.marker_x + 5, 0),
                    QPointF(geometry.right, 0),
                )
            painter.setPen(QPen(color, 2 if self.isSelected() else 1))
            if geometry.cap_left:
                painter.drawLine(QPointF(geometry.left, -6), QPointF(geometry.left, 6))
            if geometry.cap_right:
                painter.drawLine(
                    QPointF(geometry.right, -6), QPointF(geometry.right, 6)
                )

        half = self.ICON_SIZE / 2 if geometry.mode == "exact" else 5
        x = geometry.marker_x
        diamond = QPolygonF(
            [
                QPointF(x, -half),
                QPointF(x + half, 0),
                QPointF(x, half),
                QPointF(x - half, 0),
            ]
        )
        painter.setPen(
            QPen(
                self._text_color if self.isSelected() else color,
                2 if self.isSelected() else 1,
            )
        )
        painter.setBrush(
            QBrush(color) if geometry.mode == "exact" else QBrush(Qt.BrushStyle.NoBrush)
        )
        painter.drawPolygon(diamond)

    def _paint_duration(
        self, painter: QPainter, geometry: TemporalGeometry, color: QColor
    ) -> None:
        """Keep possible presence distinct from certainly occupied duration."""
        rect = QRectF(geometry.left, -6, geometry.right - geometry.left, 12)
        possible = QColor(color)
        possible.setAlpha(110)
        painter.setBrush(QBrush(possible, Qt.BrushStyle.BDiagPattern))
        painter.drawRect(rect)
        if geometry.certain_left is not None and geometry.certain_right is not None:
            certain = QRectF(
                geometry.certain_left,
                -6,
                geometry.certain_right - geometry.certain_left,
                12,
            )
            painter.fillRect(certain, color)

    def _paint_labels(
        self, painter: QPainter, display: TemporalDisplay, geometry: TemporalGeometry
    ) -> None:
        """Use the same authored caption for both saved date formats."""
        exact = geometry.mode == "exact"
        x = geometry.label_left
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(self._text_color)
        painter.drawText(QPointF(x, -2 if exact else 20), self.event.name)
        font.setBold(False)
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(self._secondary_text_color)
        painter.drawText(QPointF(x, 10 if exact else 32), display.caption)
