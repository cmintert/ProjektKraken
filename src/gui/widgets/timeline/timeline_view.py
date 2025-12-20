"""
Timeline View Module.

Provides the TimelineView class for rendering and interacting with the timeline.
"""

import logging
from PySide6.QtWidgets import QGraphicsView, QWidget
from PySide6.QtCore import Qt, Signal, QTimer, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QTransform, QFont

from src.core.theme_manager import ThemeManager
from src.gui.widgets.timeline_ruler import TimelineRuler
from src.gui.widgets.timeline_lane_packer import TimelineLanePacker
from src.gui.widgets.timeline.timeline_scene import (
    TimelineScene,
    PlayheadItem,
    CurrentTimeLineItem,
)
from src.gui.widgets.timeline.event_item import EventItem

logger = logging.getLogger(__name__)


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
    event_date_changed = Signal(str, float)  # (event_id, new_lore_date)

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

        # Initialize lane packer for event organization
        self._lane_packer = TimelineLanePacker()

        # Connect to theme manager to trigger redraw of foreground (ruler)
        # Use shiboken6 to check if the C++ object is still valid
        from shiboken6 import isValid

        ThemeManager().theme_changed.connect(
            lambda t: self.viewport().update() if isValid(self) else None
        )
        ThemeManager().theme_changed.connect(
            lambda t: self._update_corner_widget(t) if isValid(self) else None
        )

        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setRenderHint(QPainter.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        # Force full viewport updates to prevent ruler distortion during panning
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

        # Viewport alignment
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.events = []
        self.scale_factor = 20.0
        self._initial_fit_pending = False
        self._has_done_initial_fit = False  # Only fit_all on first load

        # Track current zoom level
        self._current_zoom = 1.0

        # Playhead/scrubber setup
        self._playhead = PlayheadItem()
        self.scene.addItem(self._playhead)
        self._playhead.set_time(0.0, self.scale_factor)

        # Connect playhead drag
        self._playhead.on_moved = self._on_playhead_moved

        # Current time line setup (distinct from playhead)
        self._current_time_line = CurrentTimeLineItem()
        self.scene.addItem(self._current_time_line)
        self._current_time_line.set_time(0.0, self.scale_factor)
        # Hide initially - only show when explicitly set by user
        self._current_time_line.hide()

        # Playback state
        self._playback_timer = QTimer()
        self._playback_timer.timeout.connect(self._advance_playhead)
        self._playback_step = 1.0  # Default step: 1 day per tick
        self._playback_interval = 100  # Default: 100ms between ticks

        # Set corner widget for themed scrollbar corner
        self._update_corner_widget(ThemeManager().get_theme())

    def minimumSizeHint(self):
        """
        Override minimum size hint to allow vertical shrinking.

        By default, QGraphicsView uses the scene rect to determine
        its minimum size, which prevents the dock from being resized
        smaller than the content. We override this to allow free resizing.

        Returns:
            QSize: A small minimum size (200x100) to allow shrinking.
        """
        from PySide6.QtCore import QSize

        return QSize(200, 100)

    def _on_playhead_moved(self, x_pos):
        """
        Called when playhead is dragged manually.
        Updates the internal time and emits signal.
        """
        new_time = x_pos / self.scale_factor
        self._playhead._time = new_time  # Directly update internal state
        self.playhead_time_changed.emit(new_time)

    def _on_event_drag_complete(self, event_id: str, new_lore_date: float):
        """
        Called when an event item is dragged to a new position.
        Emits the event_date_changed signal for persistence.

        Args:
            event_id: The ID of the event that was moved.
            new_lore_date: The new lore_date value.
        """
        logger.debug(f"Event {event_id} dragged to lore_date {new_lore_date}")
        self.event_date_changed.emit(event_id, new_lore_date)

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
            self._has_done_initial_fit = True

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

        # Get theme with error handling for test environments
        try:
            theme = ThemeManager().get_theme()
        except (KeyError, AttributeError) as e:
            logger.warning(f"Theme not available, using defaults: {e}")
            # Fallback theme for when ThemeManager isn't initialized
            theme = {
                "surface": "#2B2B2B",
                "border": "#555555",
            }

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

        Configures the ruler with calendar-aware date divisions.

        Args:
            converter (CalendarConverter): Converter instance or None.
        """
        self._ruler.set_calendar_converter(converter)
        self.viewport().update()

    def set_events(self, events):
        """
        Updates the scene with event items using smart lane packing.
        Reuses existing EventItem instances where possible for performance.

        Smart lane packing algorithm:
        - Greedy interval packing (First Fit)
        - Sort events by start time.
        - Packs into first available lane.
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

        # Use repack logic (via helper) which handles effective scaling
        # But for initial load, we might just want base scale if current_zoom is 1.0
        # repack_events() uses self._current_zoom.
        self.repack_events()

        # Now place items in scene
        # REPACK will have set positions, but items new or old need to be managed
        # Actually repack_events() only updates EXISTING items or lane assignments
        # We need to create items first?
        # NO. Logic inversion.
        # set_events() must CREATE items first, then pack them.

        # Correct logic:
        # 1. Create/Update all EventItems at y=0 (temp)
        # 2. Call repack_events() to position them vertically.

        # Let's rewrite this block slightly.

        # Create/Update items first
        for event in sorted_events:
            if event.id in existing_items:
                item = existing_items[event.id]
                item.update_event(event)

                reused_ids.add(event.id)
            else:
                item = EventItem(event, self.scale_factor)
                # item.setY(0) # Will be set by repack
                item.on_drag_complete = self._on_event_drag_complete
                self.scene.addItem(item)
                existing_items[event.id] = item  # Add to map for repack

            # Reuse or create drop line
            drop_line_top = -self.RULER_HEIGHT
            if event.id in drop_lines:
                line = drop_lines[event.id]
                line.setLine(item.x(), drop_line_top, item.x(), 60)  # Temp Y
            else:
                line = self.scene.addLine(
                    item.x(),
                    drop_line_top,
                    item.x(),
                    80,  # Temp Y
                    QPen(QColor(80, 80, 80), 1, Qt.DashLine),
                )
                line.setZValue(-1)
                line.event_id = event.id  # Mark for tracking

        # Remove items for events that no longer exist
        for event_id, item in existing_items.items():
            if event_id not in reused_ids and event_id not in [
                e.id for e in sorted_events if e.id not in reused_ids
            ]:
                # Careful: reused_ids tracks updates.
                # The else block adds new items which are not in
                # reused_ids yet but are in sorted_events/existing_items.
                # Simplest: "if event_id not in [e.id for e in sorted_events]"
                pass

        # Clean up removed items
        current_ids = {e.id for e in sorted_events}
        for event_id, item in list(existing_items.items()):
            if event_id not in current_ids:
                self.scene.removeItem(item)

        # Clean up drop lines
        for event_id, line in list(drop_lines.items()):
            if event_id not in current_ids:
                self.scene.removeItem(line)

        # Now Repack
        self.repack_events()

        # Update Drop Lines after repack
        # We need to iterate drop lines again to match new item Y
        # But we don't have a map from item -> drop line easily without query
        # Actually drop_lines is map id -> line.
        for event_id, line in drop_lines.items():
            if event_id in existing_items:  # Still exists
                item = existing_items[event_id]
                # Drop line goes to item's Y
                line.setLine(item.x(), -self.RULER_HEIGHT, item.x(), item.y())

        if sorted_events:
            # Calculate bounds from events for the scene rect.
            # We want the scene rect defined by events + margin,
            # ignoring infinite lines

            # X bounds
            min_date = sorted_events[0].lore_date
            max_date = sorted_events[-1].lore_date
            if min_date == max_date:
                min_date -= 10
                max_date += 10

            margin_x = (max_date - min_date) * 0.1 or 100
            start_x = (min_date - margin_x) * self.scale_factor
            end_x = (max_date + margin_x) * self.scale_factor

            # Y bounds
            # Events start at 60. Max y is approx (num_lanes * 40) + 60
            # Calculate max lane from assignments
            # Calculate max lane from items or use a safe default
            # We can't access event_lane_assignments here easily anymore.
            # But the scene rect will be updated by repack_events calls anyway.
            # However, for the initial scene rect, we should try to
            # estimate or just rely on repack.
            # Actually, repack_events sets the scene rect!
            # Custom widgets might not need blocking
            # if we don't connect to them directly
            # or if they don't emit on programmatic set.

            # Let's just set a safe default height here, and let repack fix it.
            # Or better, just don't set Y bounds strictly here if repack does it.
            # But we are setting the scene rect for the whole scene.

            # Let's inspect items to find max Y
            max_y_found = 60
            for item in self.scene.items():
                if isinstance(item, EventItem):
                    max_y_found = max(max_y_found, item.y())

            max_y = max_y_found + self.LANE_HEIGHT + 40

            min_y = 0  # Ruler area

            # Set Scene Rect explicitly to avoid infinite lines expanding it
            self.scene.setSceneRect(start_x, min_y, end_x - start_x, max_y - min_y)

            # Center Playhead and Current Time Line if they are at 0 (initial state)
            center_date = (min_date + max_date) / 2

            # Check if they are at default 0 position or we want to force center on load
            # Let's force center them on the events for better UX if they are far off
            if self._playhead._time == 0:
                self.set_playhead_time(center_date)

            # Don't auto-center current time line
            # Only show when explicitly set by user

            # Only fit_all on initial load, not on refreshes/updates
            if not self._has_done_initial_fit:
                if self.isVisible() and self.width() > 0 and self.height() > 0:
                    self.fit_all()
                    self._initial_fit_pending = False
                    self._has_done_initial_fit = True
                else:
                    self._initial_fit_pending = True

    def repack_events(self):
        """
        Repacks events into lanes based on the current effective zoom level.
        This recalculates lane assignments to prevent overlaps as the timeline
        zooms in and out (changing the effective visual duration of text labels).
        """
        if not self.events:
            return

        # Calculate effective scale (Scene scale * View zoom)
        # Note: scale_factor is pixels/day in Scene coordinates.
        # current_zoom is the View transformation scale.
        effective_scale = self.scale_factor * self._current_zoom

        # Update packer with effective scale
        self._lane_packer.update_scale_factor(effective_scale)
        event_lane_assignments = self._lane_packer.pack_events(self.events)

        # Update Y positions of existing items
        # We need to map event IDs to items again, or iterate scene items
        existing_items = {}
        drop_lines = {}
        for item in self.scene.items():
            if isinstance(item, EventItem):
                existing_items[item.event.id] = item
            elif hasattr(item, "event_id"):
                drop_lines[item.event_id] = item

        max_lane = 0
        for event in self.events:
            if event.id in existing_items:
                lane_index = event_lane_assignments[event.id]
                y = (lane_index * self.LANE_HEIGHT) + 80
                item = existing_items[event.id]

                # Animate or set Y? Just set for now.
                item.setY(y)
                item._initial_y = y  # Update constraint
                if lane_index > max_lane:
                    max_lane = lane_index

                # Update drop line
                if event.id in drop_lines:
                    line = drop_lines[event.id]
                    line.setLine(item.x(), -self.RULER_HEIGHT, item.x(), y)

        # Recalculate Scene Rect Height
        current_rect = self.scene.sceneRect()
        max_y = 80 + (max_lane + 1) * self.LANE_HEIGHT + 40
        if max_y != current_rect.height():
            self.scene.setSceneRect(
                current_rect.x(), current_rect.y(), current_rect.width(), max_y
            )

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

        # 2. Fit Horizontal Only
        viewport_width = self.viewport().width()
        if viewport_width > 0 and width > 0:
            scale_x = viewport_width / width

            # Enforce limits
            scale_x = max(self.MIN_ZOOM, min(scale_x, self.MAX_ZOOM))

            # Apply Transform: Scale X, Reset Y to 1.0
            self.setTransform(QTransform().scale(scale_x, 1.0))
            self._current_zoom = scale_x

            # Repack on new zoom
            self.repack_events()

            # Center X, Align Top Y
            center_x = (start_x + end_x) / 2

            # centerOn(x, y) puts (x,y) in the center of the viewport
            # To ensure Y=0 is at the top, we center on (center_x, viewport_height/2)
            # This relies on Scene Y=0 being the top of the content
            vh = self.viewport().height()
            self.centerOn(center_x, vh / 2)

            # Explicitly ensure we are at the top (redundancy for safety)
            self.verticalScrollBar().setValue(0)

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
            # Set anchor to mouse position to zoom towards/away from it
            old_anchor = self.transformationAnchor()
            self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

            try:
                # Apply zoom
                self.scale(factor, 1.0)
                self._current_zoom = new_zoom

                # Repack on new zoom
                self.repack_events()
            finally:
                # Restore original anchor
                self.setTransformationAnchor(old_anchor)

    def update_event_preview(self, event_data: dict):
        """
        Updates the visual representation of an event in real-time.

        Args:
            event_data: dictionary containing transient event state.
        """
        event_id = event_data.get("id")
        if not event_id:
            return

        # Find the item
        found_item = None
        for item in self.scene.items():
            if isinstance(item, EventItem) and item.event.id == event_id:
                found_item = item
                break

        if not found_item:
            return

        # Update Event Object Shallowly
        # Note: We are modifying the live object in the scene.
        # Discarding needs to revert this.
        # Ideally, we should update visual properties without mutating the object,
        # or accept that the object is mutable and "Discard" reloads from DB.
        # Since "Discard" reloads, mutating here is fine for preview.

        if "name" in event_data:
            found_item.event.name = event_data["name"]
        if "lore_date" in event_data:
            found_item.event.lore_date = event_data["lore_date"]
        if "lore_duration" in event_data:
            found_item.event.lore_duration = event_data["lore_duration"]

        found_item.setToolTip(f"{found_item.event.name} ({found_item.event.lore_date})")

        # Repack to handle position/size changes
        self.repack_events()

        # Update view
        self.viewport().update()

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
        self._current_time_line.show()  # Make visible when explicitly set
        self.current_time_changed.emit(time)

    def get_current_time(self) -> float:
        """
        Gets the current time position.

        Returns:
            float: The current time in lore_date units.
        """
        return self._current_time_line.get_time(self.scale_factor)
