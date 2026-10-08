"""Group Band Item Module.

Provides the GroupBandItem widget for displaying tag-based grouping bands on the
timeline. Bands are thin, colored, collapsible elements that stack above the timeline
lanes.
"""

import logging
from typing import Dict, Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsSceneContextMenuEvent,
    QGraphicsSceneHoverEvent,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from src.core.temporal_display import TemporalDisplay
from src.core.theme_manager import ThemeManager
from src.gui.widgets.timeline.temporal_geometry import project_temporal_geometry
from src.gui.widgets.timeline.temporal_painter import paint_occurrence

logger = logging.getLogger(__name__)


class GroupBandItem(QGraphicsObject):
    """A thin colored band representing a tag group on the timeline.

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
        parent: Optional[QGraphicsItem] = None,
    ) -> None:
        """Initializes the GroupBandItem.

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
        self.event_dates: list[float] = []
        self.presentations: tuple[TemporalDisplay, ...] = ()
        self.event_captions: tuple[str, ...] = ()

        # Visual settings
        self.setAcceptHoverEvents(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setZValue(50)  # Above timeline content, below playhead

        # Interaction state
        self._hovered = False
        self._pressed = False

        # Theme
        self.theme = ThemeManager().get_theme()
        ThemeManager().theme_changed.connect(self._on_theme_changed)

        # Tooltip
        self._update_tooltip()

    def _on_theme_changed(self, theme: Dict) -> None:
        """Update theme and refresh."""
        self.theme = theme
        self.update()

    def _update_tooltip(self) -> None:
        """Describe group membership and authored timing without raw layout dates."""
        heading = (
            f"{self.tag_name}\nEvents: {self.count}"
            if self.count
            else f"{self.tag_name}\nNo events"
        )
        details = self.event_captions or tuple(p.caption for p in self.presentations)
        self.setToolTip(heading + ("\n" + "\n".join(details) if details else ""))

    def boundingRect(self) -> QRectF:
        """Returns the bounding rectangle for the band.

        The band spans horizontally across the entire visible timeline (effectively
        infinite) and has a height based on collapsed state.
        """
        height = (
            self.BAND_HEIGHT_COLLAPSED
            if self.is_collapsed
            else self.BAND_HEIGHT_EXPANDED
        )
        # Return a very wide rect to span the timeline
        return QRectF(-1e12, 0, 2e12, height)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        """Draw neutral structural bands and device-space occurrence marks."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        transform = painter.worldTransform()
        width = widget.width() if widget is not None else 1000
        origin = transform.map(QPointF(0, 0))
        painter.resetTransform()
        height = self.get_height()
        role = "action_quiet_hover_bg" if self._hovered else "surface"
        painter.fillRect(QRectF(0, origin.y(), width, height), QColor(self.theme[role]))
        painter.setPen(QPen(QColor(self.theme["border"]), 1))
        painter.drawLine(
            QPointF(0, origin.y() + height - 1), QPointF(width, origin.y() + height - 1)
        )
        if self.is_collapsed:
            self._paint_occurrences(painter, transform, origin.y() + height / 2)
        painter.restore()

    def _paint_occurrences(
        self, painter: QPainter, transform: object, y: float
    ) -> None:
        """Use screen-space strokes; a layout anchor never becomes a precise tick."""
        from PySide6.QtGui import QTransform

        assert isinstance(transform, QTransform)
        views = self.scene().views() if self.scene() is not None else []
        scale = getattr(views[0], "scale_factor", 20.0) if views else 20.0
        pixels_per_day = scale * transform.m11()
        for display in self.presentations:
            geometry = project_temporal_geometry(display, pixels_per_day)
            position = transform.map(QPointF(display.anchor * scale, 0))
            painter.save()
            painter.translate(position.x(), y)
            paint_occurrence(
                painter, geometry, self._color, QColor(self.theme["supporting_text"])
            )
            painter.restore()

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Handle mouse release to toggle collapse state."""
        if event.button() == Qt.MouseButton.LeftButton and self._pressed:
            self._pressed = False
            # Toggle collapse state
            if self.is_collapsed:
                self.expand_requested.emit(self.tag_name)
            else:
                self.collapse_requested.emit(self.tag_name)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent) -> None:
        """Handle context menu request."""
        self.context_menu_requested.emit(self.tag_name, event.screenPos())
        event.accept()

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        """Handle hover enter."""
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        """Handle hover leave."""
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def set_collapsed(self, collapsed: bool) -> None:
        """Set the collapsed state of the band.

        Args:
            collapsed: True to collapse, False to expand

        """
        if self.is_collapsed != collapsed:
            self.is_collapsed = collapsed
            self.prepareGeometryChange()
            self.update()

    def set_color(self, color: str) -> None:
        """Update the band color.

        Args:
            color: Hex color string (e.g., "#FF0000")

        """
        self._color = QColor(color)
        self.update()

    def update_metadata(
        self, count: int, earliest_date: float, latest_date: float
    ) -> None:
        """Update the band metadata.

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

    def set_event_dates(self, event_dates: list) -> None:
        """Set the event dates for tick mark rendering.

        Args:
            event_dates: List of lore_dates for events in this group

        """
        self.event_dates = event_dates
        self.set_event_presentations(
            [TemporalDisplay(date, date, anchor=date) for date in event_dates]
        )

    def set_event_presentations(
        self, presentations: list[TemporalDisplay], captions: list[str] | None = None
    ) -> None:
        """Accept immutable occurrence projections, retaining their uncertainty."""
        snapshot = tuple(presentations)
        details = tuple(captions or ())
        if snapshot != self.presentations or details != self.event_captions:
            self.presentations = snapshot
            self.event_captions = details
            self._update_tooltip()
            self.update()

    def get_height(self) -> int:
        """Get the current height of the band.

        Returns:
            Height in pixels

        """
        return (
            self.BAND_HEIGHT_COLLAPSED
            if self.is_collapsed
            else self.BAND_HEIGHT_EXPANDED
        )
