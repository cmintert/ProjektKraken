"""
Timeline Widget Module.
Provides the graphical timeline visualization using QGraphicsView/Scene.
Supports zooming, panning, and event visualization.
"""

from PySide6.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QGraphicsItem,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QBrush, QPen, QColor, QPainter, QPolygonF, QFont
from src.core.theme_manager import ThemeManager
from src.gui.widgets.timeline_ruler import TimelineRuler


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
    ICON_SIZE = 14
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

        # Flags: Fixed size on screen
        self.setFlags(
            QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemIsFocusable
            | QGraphicsItem.ItemIgnoresTransformations
        )

    def boundingRect(self) -> QRectF:
        """
        Defines the clickable and redrawable area of the item.
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


class TimelineView(QGraphicsView):
    """
    Custom Graphics View for displaying the TimelineScene.
    Handles:
    - Rendering the infinite ruler and grid (Foreground).
    - Zoom/Pan interaction.
    - Coordinate mapping between dates and pixels.
    """

    event_selected = Signal(str)

    LANE_HEIGHT = 40
    RULER_HEIGHT = 50  # Increased for semantic ruler with context tier

    def __init__(self, parent=None):
        """
        Initializes the TimelineView.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.scene = TimelineScene(self)
        self.setScene(self.scene)

        # Initialize semantic ruler engine
        self._ruler = TimelineRuler()

        # Connect to theme manager to trigger redraw of foreground (ruler)
        ThemeManager().theme_changed.connect(lambda t: self.viewport().update())
        ThemeManager().theme_changed.connect(self._update_corner_widget)

        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setRenderHint(QPainter.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        # Force full viewport updates to prevent ruler distortion during panning
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

        # Viewport alignment
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.events = []
        self.scale_factor = 20.0
        self._initial_fit_pending = False

        # Set corner widget for themed scrollbar corner
        self._update_corner_widget(ThemeManager().get_theme())

    def _update_corner_widget(self, theme):
        """
        Updates the corner widget background to match the theme.

        Args:
            theme: The theme dictionary.
        """
        scrollbar_bg = theme.get("scrollbar_bg", theme.get("app_bg", "#2B2B2B"))
        corner = QWidget()
        corner.setStyleSheet(f"background-color: {scrollbar_bg};")
        self.setCornerWidget(corner)

    def resizeEvent(self, event):
        """
        Handles resize events to ensure initial fit works correctly.
        """
        super().resizeEvent(event)
        if self._initial_fit_pending and self.width() > 0 and self.height() > 0:
            self.fit_all()
            self._initial_fit_pending = False

    # Height allocated for sticky parent context tier
    CONTEXT_TIER_HEIGHT = 14

    def drawForeground(self, painter, rect):
        """
        Draws a semantic zoom ruler at the top of the viewport.

        Features:
        - Semantic Level of Detail (LOD) with smooth transitions
        - Opacity interpolation for emerging minor ticks
        - Label collision avoidance
        - Sticky parent context label
        """
        # 1. Switch to Screen Coordinates
        painter.save()
        painter.resetTransform()

        viewport_rect = self.viewport().rect()
        w = viewport_rect.width()
        h = self.RULER_HEIGHT
        context_h = self.CONTEXT_TIER_HEIGHT

        theme = ThemeManager().get_theme()

        # 2. Draw context tier background (top band)
        painter.setBrush(QColor(theme["surface"]).darker(110))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, w, context_h)

        # 3. Draw main ruler background
        painter.setBrush(QColor(theme["surface"]))
        painter.drawRect(0, context_h, w, h - context_h)

        # Bottom line separating ruler from content
        painter.setPen(QPen(QColor(theme["border"]), 1))
        painter.drawLine(0, h, w, h)

        # 4. Determine visible time range
        left_scene_x = self.mapToScene(0, 0).x()
        right_scene_x = self.mapToScene(w, 0).x()

        start_date = left_scene_x / self.scale_factor
        end_date = right_scene_x / self.scale_factor
        date_range = end_date - start_date

        if date_range <= 0:
            painter.restore()
            return

        # 5. Calculate ticks using semantic ruler engine
        ticks = self._ruler.calculate_ticks(
            start_date=start_date,
            end_date=end_date,
            viewport_width=w,
            scale_factor=self.scale_factor,
        )

        # 6. Apply collision avoidance
        ticks = self._ruler.avoid_collisions(ticks, label_width=45)

        # 7. Setup fonts
        major_font = QFont(painter.font())
        major_font.setPointSize(9)
        major_font.setBold(True)

        minor_font = QFont(painter.font())
        minor_font.setPointSize(8)
        minor_font.setBold(False)

        # 8. Draw ticks with opacity
        for tick in ticks:
            # Calculate screen position using mapFromScene for accuracy
            scene_x = tick.position * self.scale_factor
            screen_pos = self.mapFromScene(QPointF(scene_x, 0))
            screen_x = screen_pos.x()

            # Skip if outside viewport (with buffer)
            if screen_x < -50 or screen_x > w + 50:
                continue

            # Determine tick styling
            if tick.is_major:
                tick_height = 12
                painter.setFont(major_font)
                text_color = QColor(theme["text_main"])
            else:
                tick_height = 8
                painter.setFont(minor_font)
                text_color = QColor(theme["text_dim"])

            # Apply opacity for fade-in effect
            text_color.setAlphaF(tick.opacity)
            tick_color = QColor(theme["text_dim"])
            tick_color.setAlphaF(tick.opacity)

            # Draw tick line
            painter.setPen(QPen(tick_color, 1))
            painter.drawLine(int(screen_x), h - tick_height, int(screen_x), h)

            # Draw label if present
            if tick.label:
                painter.setPen(text_color)
                # Position labels in the main ruler area (below context tier)
                label_rect = QRectF(screen_x + 4, context_h + 2, 70, h - context_h - 14)
                painter.drawText(
                    label_rect,
                    Qt.AlignVCenter | Qt.AlignLeft,
                    tick.label,
                )

            # Draw vertical grid line (subtle)
            if tick.is_major:
                grid_color = QColor(255, 255, 255, int(15 * tick.opacity))
                painter.setPen(QPen(grid_color, 1))
                painter.drawLine(
                    int(screen_x), h, int(screen_x), viewport_rect.height()
                )

        # 9. Draw sticky parent context label
        context_label = self._ruler.get_parent_context(start_date)
        if context_label:
            painter.setFont(minor_font)
            painter.setPen(QColor(theme["primary"]))
            painter.drawText(
                QRectF(8, 2, w - 16, context_h - 4),
                Qt.AlignVCenter | Qt.AlignLeft,
                context_label,
            )

        painter.restore()

    def set_ruler_calendar(self, converter):
        """
        Configures the ruler with calendar-aware date divisions.

        Args:
            converter: CalendarConverter instance or None.
        """
        self._ruler.set_calendar_converter(converter)
        self.viewport().update()

    def set_events(self, events):
        """
        Clears the scene and repopulates it with event items.
        Applies a modulo-based layout algorithm to prevent overlapping.

        Args:
            events (list): List of Event domain objects.
        """
        self.scene.clear()

        # Sort by Date
        sorted_events = sorted(events, key=lambda e: e.lore_date)
        self.events = sorted_events

        # Draw Infinite Axis Line
        axis_pen = QPen(QColor(100, 100, 100))
        axis_pen.setCosmetic(True)
        self.scene.addLine(-1e12, 0, 1e12, 0, axis_pen)

        # Layout Logic: Modulo Stacking
        for i, event in enumerate(sorted_events):
            item = EventItem(event, self.scale_factor)

            # Cyclic Lane assignment
            lane_index = i % 8
            y = (lane_index * self.LANE_HEIGHT) + 60  # Start below ruler (40px) + Gap

            item.setY(y)

            # Draw Drop Line
            line = self.scene.addLine(
                item.x(), 0, item.x(), y, QPen(QColor(80, 80, 80), 1, Qt.DashLine)
            )
            line.setZValue(-1)

            self.scene.addItem(item)

        if sorted_events:
            self.scene.setSceneRect(self.scene.itemsBoundingRect())

            # Check if we can fit immediately
            if self.isVisible() and self.width() > 0 and self.height() > 0:
                self.fit_all()
                self._initial_fit_pending = False
            else:
                self._initial_fit_pending = True

    def fit_all(self):
        """
        Fits the view to encompass all event items, ignoring the infinite axis.
        Adds a 10% margin on the sides.
        """
        if not self.events:
            return

        # 1. Calculate X bounds based on events
        min_date = self.events[0].lore_date
        max_date = self.events[-1].lore_date

        # Handle single event case with a default range
        if min_date == max_date:
            min_date -= 10
            max_date += 10

        margin = (max_date - min_date) * 0.1
        if margin == 0:
            margin = 10

        start_x = (min_date - margin) * self.scale_factor
        end_x = (max_date + margin) * self.scale_factor
        width = end_x - start_x

        # 2. Calculate Y bounds based on lanes
        # Each item is at y = (lane_index * LANE_HEIGHT) + 60
        # Max 8 lanes (0-7), so max y is roughly (7 * 40) + 60 + height
        # But let's just use a fixed reasonable height or scan items if needed.
        # Fixed height covering all 8 lanes is safe + room for labels.
        # 8 lanes * 40 = 320. Start at 60. So bottom is ~380.
        height = 400

        # 3. Fit
        target_rect = QRectF(start_x, 0, width, height)
        self.fitInView(target_rect, Qt.KeepAspectRatio)

    def wheelEvent(self, event):
        """
        Handles mouse wheel events for zooming.
        Zooms in/out centered on the mouse position.
        """
        zoom_in = 1.25
        zoom_out = 1 / zoom_in
        factor = zoom_in if event.angleDelta().y() > 0 else zoom_out

        try:
            target = event.position().toPoint()
        except AttributeError:
            target = event.pos()

        old_pos = self.mapToScene(target)
        self.scale(factor, factor)
        new_pos = self.mapToScene(target)
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())

    def mousePressEvent(self, event):
        """
        Handles mouse clicks. Emits 'event_selected' if an EventItem is clicked.
        """
        super().mousePressEvent(event)

        try:
            pos = event.position().toPoint()
        except AttributeError:
            pos = event.pos()

        # Check for item at click position
        item = self.scene.itemAt(self.mapToScene(pos), self.transform())

        # Traverse up if needed
        if isinstance(item, EventItem):
            self.event_selected.emit(item.event.id)
            # If we clicked an item, we might want to stop the drag?
            # But QGraphicsView handles selection + drag logic usually.
            # For now, just emitting signal is safe.

    def focus_event(self, event_id: str):
        """Centers the view on the specified event."""
        for item in self.scene.items():
            if isinstance(item, EventItem) and item.event.id == event_id:
                self.centerOn(item)
                item.setSelected(True)
                return


class TimelineWidget(QWidget):
    """
    Wrapper widget for TimelineView + Toolbar.
    """

    event_selected = Signal(str)

    def __init__(self, parent=None):
        """
        Initializes the TimelineWidget.

        Args:
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar Container (Header)
        self.header_frame = QWidget()
        self.header_frame.setObjectName("TimelineHeader")
        self.toolbar_layout = QHBoxLayout(self.header_frame)
        self.toolbar_layout.setContentsMargins(4, 4, 4, 4)

        self.toolbar_layout.addStretch()

        self.btn_fit = QPushButton("Fit View")
        self.btn_fit.clicked.connect(self.fit_view)
        self.toolbar_layout.addWidget(self.btn_fit)

        self.layout.addWidget(self.header_frame)

        # View
        self.view = TimelineView()
        self.view.event_selected.connect(self.event_selected.emit)
        self.layout.addWidget(self.view)

    def set_events(self, events):
        """Passes the event list to the view."""
        self.view.set_events(events)

    def focus_event(self, event_id: str):
        """Centers the timeline on the given event."""
        self.view.focus_event(event_id)

    def fit_view(self):
        """Fits all events within the view."""
        self.view.fit_all()

    def set_calendar_converter(self, converter):
        """
        Sets the calendar converter for formatted date display.

        Args:
            converter: CalendarConverter instance or None.
        """
        EventItem.set_calendar_converter(converter)
        # Also configure the ruler for calendar-aware date divisions
        self.view.set_ruler_calendar(converter)
        # Trigger repaint to update existing items
        self.view.viewport().update()
