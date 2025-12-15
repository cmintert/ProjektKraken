"""
Timeline Widget Module.
Provides the graphical timeline visualization using QGraphicsView/Scene.
Supports zooming, panning, and event visualization.
"""

from PySide6.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QGraphicsItem,
    QGraphicsLineItem,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QTimer
from PySide6.QtGui import QBrush, QPen, QColor, QPainter, QPolygonF, QFont
from src.core.theme_manager import ThemeManager
from src.gui.widgets.timeline_ruler import TimelineRuler
import heapq


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

        # Enable caching for improved rendering performance
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)

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
        super().__init__(-1e12, -1e12, 1e12, 1e12, parent)

        # Style
        pen = QPen(QColor(255, 100, 100), 2)  # Red playhead
        pen.setCosmetic(True)
        self.setPen(pen)

        # Make draggable
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

        # Set high Z value to appear on top
        self.setZValue(100)

        # Track current time position
        self._time = 0.0

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
        super().__init__(-1e12, -1e12, 1e12, 1e12, parent)

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


class TimelineView(QGraphicsView):
    """
    Custom Graphics View for displaying the TimelineScene.
    Handles:
    - Rendering the infinite ruler and grid (Foreground).
    - Zoom/Pan interaction.
    - Coordinate mapping between dates and pixels.
    - Playhead/scrubber for timeline playback.
    """

    event_selected = Signal(str)
    playhead_time_changed = Signal(float)  # Emitted when playhead position changes
    current_time_changed = Signal(float)  # Emitted when current time is changed

    LANE_HEIGHT = 40
    RULER_HEIGHT = 50  # Increased for semantic ruler with context tier

    # Zoom limits
    MIN_ZOOM = 0.01  # Maximum zoom out (1% of normal)
    MAX_ZOOM = 100.0  # Maximum zoom in (100x normal)

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

        # Track current zoom level
        self._current_zoom = 1.0

        # Playhead/scrubber setup
        self._playhead = PlayheadItem()
        self.scene.addItem(self._playhead)
        self._playhead.set_time(0.0, self.scale_factor)

        # Current time line setup (distinct from playhead)
        self._current_time_line = CurrentTimeLineItem()
        self.scene.addItem(self._current_time_line)
        self._current_time_line.set_time(0.0, self.scale_factor)

        # Playback state
        self._playback_timer = QTimer()
        self._playback_timer.timeout.connect(self._advance_playhead)
        self._playback_step = 1.0  # Default step: 1 day per tick
        self._playback_interval = 100  # Default: 100ms between ticks

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
        Updates the scene with event items using smart lane packing.
        Reuses existing EventItem instances where possible for performance.

        Smart lane packing algorithm:
        - Greedy interval packing using min-heap
        - Sort events by start time (lore_date)
        - Maintain heap of lanes with their current end time
        - For each event, choose first lane whose end <= event.start
        - If no lane available, allocate new lane
        - O(n log k) complexity where n=events, k=lanes

        Args:
            events (list): List of Event domain objects.
        """
        # Sort by Date
        sorted_events = sorted(events, key=lambda e: e.lore_date)
        self.events = sorted_events

        # Build a map of existing items by event ID
        existing_items = {}
        drop_lines = {}
        for item in self.scene.items():
            if isinstance(item, EventItem):
                existing_items[item.event.id] = item
            elif hasattr(item, "event_id"):  # Drop lines marked with event_id
                drop_lines[item.event_id] = item

        # Track which items we've reused
        reused_ids = set()

        # Draw Infinite Axis Line if not present
        axis_exists = any(
            not isinstance(item, EventItem) and not hasattr(item, "event_id")
            for item in self.scene.items()
        )
        if not axis_exists:
            axis_pen = QPen(QColor(100, 100, 100))
            axis_pen.setCosmetic(True)
            self.scene.addLine(-1e12, 0, 1e12, 0, axis_pen)

        # Smart lane packing using greedy algorithm with min-heap
        # Heap stores (end_time, lane_index)
        lanes_heap = []
        event_lane_assignments = {}  # event -> lane_index

        for event in sorted_events:
            # Determine event's end time
            end_time = event.lore_date + (
                event.lore_duration if event.lore_duration > 0 else 0.1
            )

            # Try to find an available lane (one whose end_time <= event.lore_date)
            assigned_lane = None
            if lanes_heap and lanes_heap[0][0] <= event.lore_date:
                # Pop the earliest ending lane and reuse it
                _, assigned_lane = heapq.heappop(lanes_heap)
            else:
                # Allocate a new lane
                assigned_lane = len(lanes_heap)

            # Record assignment and push back to heap with new end time
            event_lane_assignments[event.id] = assigned_lane
            heapq.heappush(lanes_heap, (end_time, assigned_lane))

        # Now place items in scene
        for event in sorted_events:
            lane_index = event_lane_assignments[event.id]
            y = (lane_index * self.LANE_HEIGHT) + 60  # Start below ruler + Gap

            # Reuse or create item
            if event.id in existing_items:
                item = existing_items[event.id]
                item.update_event(event)
                item.setY(y)
                reused_ids.add(event.id)
            else:
                item = EventItem(event, self.scale_factor)
                item.setY(y)
                self.scene.addItem(item)

            # Reuse or create drop line
            if event.id in drop_lines:
                line = drop_lines[event.id]
                # Update line position
                line.setLine(item.x(), 0, item.x(), y)
            else:
                line = self.scene.addLine(
                    item.x(), 0, item.x(), y, QPen(QColor(80, 80, 80), 1, Qt.DashLine)
                )
                line.setZValue(-1)
                line.event_id = event.id  # Mark for tracking

        # Remove items for events that no longer exist
        for event_id, item in existing_items.items():
            if event_id not in reused_ids:
                self.scene.removeItem(item)

        # Remove orphaned drop lines
        current_event_ids = {e.id for e in sorted_events}
        for event_id, line in drop_lines.items():
            if event_id not in current_event_ids:
                self.scene.removeItem(line)

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
        Handles mouse wheel events for zooming with zoom-to-cursor behavior.
        Zooms in/out centered on the mouse position with min/max limits.

        Args:
            event: QWheelEvent containing wheel delta and position.
        """
        zoom_in = 1.25
        zoom_out = 1 / zoom_in
        factor = zoom_in if event.angleDelta().y() > 0 else zoom_out

        # Calculate new zoom level
        new_zoom = self._current_zoom * factor

        # Enforce zoom limits
        if new_zoom < self.MIN_ZOOM:
            factor = self.MIN_ZOOM / self._current_zoom
            new_zoom = self.MIN_ZOOM
        elif new_zoom > self.MAX_ZOOM:
            factor = self.MAX_ZOOM / self._current_zoom
            new_zoom = self.MAX_ZOOM

        # Only zoom if within limits
        if factor != 1.0:
            try:
                target = event.position().toPoint()
            except AttributeError:
                target = event.pos()

            # Get scene position before zoom
            old_pos = self.mapToScene(target)

            # Apply zoom
            self.scale(factor, factor)
            self._current_zoom = new_zoom

            # Get scene position after zoom
            new_pos = self.mapToScene(target)

            # Translate to keep the same scene point under cursor
            delta = new_pos - old_pos
            self.translate(delta.x(), delta.y())

    def mousePressEvent(self, event):
        """
        Handles mouse clicks. Emits 'event_selected' if an EventItem is clicked.
        Tracks playhead dragging.
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
        elif isinstance(item, PlayheadItem):
            # Track that we're dragging the playhead
            self._dragging_playhead = True

    def mouseReleaseEvent(self, event):
        """
        Handles mouse release. Emits playhead_time_changed if playhead was dragged.
        """
        super().mouseReleaseEvent(event)

        if hasattr(self, "_dragging_playhead") and self._dragging_playhead:
            # Emit signal with new playhead time
            new_time = self._playhead.get_time(self.scale_factor)
            self.playhead_time_changed.emit(new_time)
            self._dragging_playhead = False

    def focus_event(self, event_id: str):
        """Centers the view on the specified event."""
        for item in self.scene.items():
            if isinstance(item, EventItem) and item.event.id == event_id:
                self.centerOn(item)
                item.setSelected(True)
                return

    def start_playback(self):
        """
        Starts automatic playhead advancement.
        """
        if not self._playback_timer.isActive():
            self._playback_timer.start(self._playback_interval)

    def stop_playback(self):
        """
        Stops automatic playhead advancement.
        """
        self._playback_timer.stop()

    def is_playing(self) -> bool:
        """
        Returns whether playback is currently active.

        Returns:
            bool: True if playing, False otherwise.
        """
        return self._playback_timer.isActive()

    def set_playhead_time(self, time: float):
        """
        Sets the playhead to a specific time position.

        Args:
            time: The time in lore_date units.
        """
        self._playhead.set_time(time, self.scale_factor)
        self.playhead_time_changed.emit(time)

    def get_playhead_time(self) -> float:
        """
        Gets the current playhead time position.

        Returns:
            float: The current time in lore_date units.
        """
        return self._playhead.get_time(self.scale_factor)

    def step_forward(self):
        """
        Steps the playhead forward by the playback step amount.
        """
        current_time = self.get_playhead_time()
        new_time = current_time + self._playback_step
        self.set_playhead_time(new_time)

    def step_backward(self):
        """
        Steps the playhead backward by the playback step amount.
        """
        current_time = self.get_playhead_time()
        new_time = current_time - self._playback_step
        self.set_playhead_time(new_time)

    def _advance_playhead(self):
        """
        Internal method called by timer to advance playhead during playback.
        """
        self.step_forward()

    def set_current_time(self, time: float):
        """
        Sets the current time line to a specific time position.
        This represents the "now" of the world, distinct from the playhead.

        Args:
            time: The time in lore_date units.
        """
        self._current_time_line.set_time(time, self.scale_factor)
        self.current_time_changed.emit(time)

    def get_current_time(self) -> float:
        """
        Gets the current time position.

        Returns:
            float: The current time in lore_date units.
        """
        return self._current_time_line.get_time(self.scale_factor)


class TimelineWidget(QWidget):
    """
    Wrapper widget for TimelineView + Toolbar.
    """

    event_selected = Signal(str)
    playhead_time_changed = Signal(float)  # Expose playhead signal from view
    current_time_changed = Signal(float)  # Expose current time signal from view

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

        # Playback controls
        self.btn_step_back = QPushButton("◄")
        self.btn_step_back.setToolTip("Step Backward")
        self.btn_step_back.setMaximumWidth(40)
        self.btn_step_back.clicked.connect(self.step_backward)
        self.toolbar_layout.addWidget(self.btn_step_back)

        self.btn_play_pause = QPushButton("▶")
        self.btn_play_pause.setToolTip("Play/Pause")
        self.btn_play_pause.setCheckable(True)
        self.btn_play_pause.setMaximumWidth(40)
        self.btn_play_pause.clicked.connect(self.toggle_playback)
        self.toolbar_layout.addWidget(self.btn_play_pause)

        self.btn_step_forward = QPushButton("►")
        self.btn_step_forward.setToolTip("Step Forward")
        self.btn_step_forward.setMaximumWidth(40)
        self.btn_step_forward.clicked.connect(self.step_forward)
        self.toolbar_layout.addWidget(self.btn_step_forward)

        # Separator
        self.toolbar_layout.addSpacing(20)

        # Current time control
        self.btn_set_current_time = QPushButton("Set Current Time")
        self.btn_set_current_time.setToolTip(
            "Set the current time in the world to the playhead position"
        )
        self.btn_set_current_time.clicked.connect(self.set_current_time_to_playhead)
        self.toolbar_layout.addWidget(self.btn_set_current_time)

        self.toolbar_layout.addStretch()

        self.btn_fit = QPushButton("Fit View")
        self.btn_fit.clicked.connect(self.fit_view)
        self.toolbar_layout.addWidget(self.btn_fit)

        self.layout.addWidget(self.header_frame)

        # View
        self.view = TimelineView()
        self.view.event_selected.connect(self.event_selected.emit)
        self.view.playhead_time_changed.connect(self.playhead_time_changed.emit)
        self.view.current_time_changed.connect(self.current_time_changed.emit)
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

    def toggle_playback(self):
        """
        Toggles playback on/off and updates button state.
        """
        if self.view.is_playing():
            self.view.stop_playback()
            self.btn_play_pause.setText("▶")
            self.btn_play_pause.setChecked(False)
        else:
            self.view.start_playback()
            self.btn_play_pause.setText("■")
            self.btn_play_pause.setChecked(True)

    def step_forward(self):
        """Steps the playhead forward."""
        self.view.step_forward()

    def step_backward(self):
        """Steps the playhead backward."""
        self.view.step_backward()

    def set_playhead_time(self, time: float):
        """
        Sets the playhead to a specific time.

        Args:
            time: Time in lore_date units.
        """
        self.view.set_playhead_time(time)

    def get_playhead_time(self) -> float:
        """
        Gets the current playhead time.

        Returns:
            float: Current time in lore_date units.
        """
        return self.view.get_playhead_time()

    def set_current_time(self, time: float):
        """
        Sets the current time in the world.

        Args:
            time: Time in lore_date units.
        """
        self.view.set_current_time(time)

    def get_current_time(self) -> float:
        """
        Gets the current time in the world.

        Returns:
            float: Current time in lore_date units.
        """
        return self.view.get_current_time()

    def set_current_time_to_playhead(self):
        """
        Sets the current time to match the playhead position.
        This is the typical workflow: move playhead, then set as current time.
        """
        playhead_time = self.get_playhead_time()
        self.set_current_time(playhead_time)

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
