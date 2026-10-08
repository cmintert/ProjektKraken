"""Timeline Event Item Module.

Provides the EventItem class for rendering individual events on the timeline.
"""

import logging
from collections.abc import Callable
from typing import Any, Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QCursor,
    QPainter,
    QPainterPath,
    QPen,
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
from src.core.temporal_presentation import event_temporal_presentation
from src.core.theme_manager import ThemeManager
from src.gui.utils.style_helper import StyleHelper
from src.gui.widgets.timeline.item_layout import (
    LABEL_GUTTER,
    TemporalRow,
    TimelineItemLayout,
    timeline_item_layout,
)
from src.gui.widgets.timeline.temporal_geometry import (
    TemporalGeometry,
    project_temporal_geometry,
)
from src.gui.widgets.timeline.temporal_painter import (
    paint_measure,
    paint_occurrence,
    paint_presence,
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
        presentation = event_temporal_presentation(event, cls._calendar_converter)
        if presentation.layered:
            return timeline_item_layout(presentation, event.name, 1).height
        return (
            cls.DURATION_EVENT_HEIGHT
            if presentation.presence.kind == "duration"
            else cls.POINT_EVENT_HEIGHT
        )

    @classmethod
    def set_calendar_converter(cls, converter: CalendarConverter | None) -> None:
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
        self._secondary_text_color = QColor(theme["supporting_caption"])
        self._theme = theme
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

        self.setOpacity(1.0)
        self.update()

    def _get_effective_color(self) -> QColor:
        """Return identity color; future state is named without fading text."""
        return QColor(self.base_color)

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
            "Solid bar: certainly ongoing. ?: timing unresolved.\n"
            "Detached Duration ruler measures length, not a start/end date. "
            "A broken ruler is shorter than the scale can show."
        )

    def _geometry(self, display: TemporalDisplay) -> TemporalGeometry:
        return project_temporal_geometry(display, self.scale_factor * self._zoom_level)

    def _display_rect(self, display: TemporalDisplay) -> QRectF:
        """Return the same screen geometry used by painting and hit testing."""
        if event_temporal_presentation(self.event, self._calendar_converter).layered:
            return self._layout().rows[-1].rect
        geometry = self._geometry(display)
        return QRectF(geometry.left, -8, geometry.right - geometry.left, 16)

    def _layout(self) -> TimelineItemLayout:
        """Return the same measured layout used by painting and lane packing."""
        presentation = event_temporal_presentation(self.event, self._calendar_converter)
        return timeline_item_layout(
            presentation, self.event.name, self.scale_factor * self._zoom_level
        )

    def boundingRect(self) -> QRectF:
        """Include all channel marks and measured text without selection resizing."""
        return self._layout().bounds

    def shape(self) -> QPainterPath:
        """Only channel glyphs accept event dragging; labels are not drag handles."""
        path = QPainterPath()
        for row in self._layout().rows:
            path.addRect(row.rect.adjusted(-4, -2, 4, 2))
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
        """Render independent occurrence, length and possible presence channels."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        layout = self._layout()
        color = self._get_effective_color()
        boundary_role = (
            "focus_ring"
            if self.hasFocus()
            else "text_main"
            if self.isSelected()
            else "supporting_text"
        )
        boundary = QColor(self._theme[boundary_role])
        for row in layout.rows:
            painter.save()
            painter.translate(0, row.y)
            if row.measure:
                paint_measure(painter, row.geometry, self._theme)
            elif row.geometry.mode == "duration":
                paint_presence(
                    painter,
                    row.geometry,
                    color,
                    boundary,
                    6 if row.label else 12,
                    self.isSelected(),
                )
            else:
                paint_occurrence(
                    painter, row.geometry, color, boundary, self.isSelected()
                )
            painter.restore()
            self._paint_row_label(painter, layout, row)
        self._paint_labels(painter, layout)
        if self.hasFocus():
            painter.setPen(QPen(QColor(self._theme["focus_ring"]), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(layout.bounds)
        painter.restore()

    def _paint_row_label(
        self, painter: QPainter, layout: TimelineItemLayout, row: TemporalRow
    ) -> None:
        """Label channels without coupling the detached measure to a date."""
        font = painter.font()
        font.setBold(False)
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(self._secondary_text_color)
        if row.label:
            painter.drawText(
                QPointF(layout.label_x - LABEL_GUTTER, row.y + 4), row.label + ":"
            )
        if row.value:
            painter.drawText(QPointF(row.geometry.right + 12, row.y + 4), row.value)

    def _paint_labels(self, painter: QPainter, layout: TimelineItemLayout) -> None:
        """Keep authored captions fully readable in every temporal state."""
        display = event_temporal_display(self.event, self._calendar_converter)
        font = painter.font()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(self._text_color)
        title = self.display_name
        painter.drawText(QPointF(layout.label_x, layout.name_y), title)
        font.setBold(False)
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(self._secondary_text_color)
        painter.drawText(QPointF(layout.label_x, layout.caption_y), display.caption)

    @property
    def display_name(self) -> str:
        """Name a definitely future occurrence without dimming its date."""
        return self.event.name + (" · Not yet" if self.is_future else "")
