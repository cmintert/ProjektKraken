"""
Timeline View Module.

Provides the TimelineView class for rendering and interacting with the timeline.
"""

import logging
from typing import Any

from PySide6.QtCore import QPointF, QRectF, QSettings, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QResizeEvent,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import QGraphicsView, QWidget

from src.core.theme_manager import ThemeManager
from src.gui.widgets.timeline.event_item import EventItem
from src.gui.widgets.timeline.group_band_manager import GroupBandManager
from src.gui.widgets.timeline.group_label_overlay import GroupLabelOverlay
from src.gui.widgets.timeline.timeline_scene import (
    CurrentTimeLineItem,
    PlayheadItem,
    TimelineScene,
)
from src.gui.widgets.timeline_lane_packer import TimelineLanePacker
from src.gui.widgets.timeline_ruler import TimelineRuler

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

    # Use the tallest event type height for lane spacing
    LANE_HEIGHT = EventItem.DURATION_EVENT_HEIGHT
    RULER_HEIGHT = 50  # Increased for semantic ruler with context tier

    # Zoom limits
    MIN_ZOOM = 0.01  # Maximum zoom out (1% of normal)
    MAX_ZOOM = 100.0  # Maximum zoom in (100x normal)

    # Ruler & Playhead Constants
    PLAYHEAD_COLOR = QColor(255, 100, 100)
    PLAYHEAD_HANDLE_WIDTH = 20
    PLAYHEAD_HANDLE_RECT_HEIGHT = 12
    PLAYHEAD_HANDLE_TRI_HEIGHT = 8

    MAJOR_TICK_HEIGHT = 12
    MINOR_TICK_HEIGHT = 8

    # Special "All Events" group
    ALL_EVENTS_GROUP_NAME = "All events"
    ALL_EVENTS_COLOR = "#808080"  # Neutral gray

    def __init__(self, parent: QWidget = None) -> None:
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

        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setRenderHint(QPainter.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        # Force full viewport updates to prevent ruler distortion during panning
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

        # Viewport alignment
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

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

        # Restore persisted playhead time
        settings = QSettings()
        # Default to 0.0 only if not set
        persisted_time = settings.value("timeline/playhead_time", 0.0, type=float)

        # Apply restoration
        if persisted_time != 0.0:
            self.set_playhead_time(persisted_time)

        # Group band manager (will be initialized when data provider is set)
        self._band_manager = None
        self._data_provider = None

        # Group label overlay for fixed lane labels
        self._label_overlay = GroupLabelOverlay(self)
        self._label_overlay.setGeometry(
            0, self.RULER_HEIGHT, GroupLabelOverlay.LABEL_WIDTH, 0
        )
        self._label_overlay.raise_()  # Ensure overlay is on top

        # Track duplicate event items created for "All events" group
        self._duplicate_event_items = []

        # Initialize grouping state (will be set by set_grouping_config)
        self._grouping_tag_order = []
        self._grouping_mode = "DUPLICATE"

        # Set corner widget for themed scrollbar corner
        self._update_corner_widget(ThemeManager().get_theme())

    def minimumSizeHint(self) -> QSize:
        """
        Override minimum size hint to allow vertical shrinking.

        By default, QGraphicsView uses the scene rect to determine
        its minimum size, which prevents the dock from being resized
        smaller than the content. We override this to allow free resizing.

        Returns:
            QSize: A small minimum size (200x100) to allow shrinking.
        """
        from PySide6.QtCore import QSize

        if self._playhead:
            self._playhead.set_zoom(self._current_zoom * self.scale_factor)

        return QSize(200, 100)

    def _on_playhead_moved(self, x_pos: float) -> None:
        """
        Called when playhead is dragged manually.
        Updates the internal time and emits signal.
        """
        # Round to 4 decimal places to prevent float precision drift
        new_time = round(x_pos / self.scale_factor, 4)
        self._playhead._time = new_time  # Directly update internal state
        self.playhead_time_changed.emit(new_time)

    def _on_event_drag_complete(self, event_id: str, new_lore_date: float) -> None:
        """
        Called when an event item is dragged to a new position.
        Emits the event_date_changed signal for persistence.

        Args:
            event_id: The ID of the event that was moved.
            new_lore_date: The new lore_date value.
        """

        self.event_date_changed.emit(event_id, new_lore_date)

    def _update_corner_widget(self, theme: dict) -> None:
        """
        Updates the corner widget background to match the theme.

        Args:
            theme: The theme dictionary.
        """
        scrollbar_bg = theme.get("scrollbar_bg", theme.get("app_bg", "#2B2B2B"))
        corner = QWidget()
        corner.setStyleSheet(f"background-color: {scrollbar_bg};")
        self.setCornerWidget(corner)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """
        Handles resize events to ensure initial fit works correctly.
        """
        super().resizeEvent(event)
        if self._initial_fit_pending and self.width() > 0 and self.height() > 0:
            self.fit_all()
            self._initial_fit_pending = False
            self._has_done_initial_fit = True

        # Ensure playhead zoom is updated if view size affects it
        if self._playhead and hasattr(self, "_current_zoom"):
            self._playhead.set_zoom(self._current_zoom * self.scale_factor)

        # Update label overlay geometry to match viewport
        if hasattr(self, "_label_overlay"):
            viewport_height = self.viewport().height()
            self._label_overlay.setGeometry(
                0,
                self.RULER_HEIGHT,
                GroupLabelOverlay.LABEL_WIDTH,
                viewport_height - self.RULER_HEIGHT,
            )

            # Update label positions
            self._update_label_overlay()

    # Height allocated for sticky parent context tier
    CONTEXT_TIER_HEIGHT = 14

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
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
        painter.setPen(Qt.PenStyle.NoPen)
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
        major_font, minor_font = self._setup_ruler_fonts(painter)

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
                tick_height = self.MAJOR_TICK_HEIGHT
                painter.setFont(major_font)
                text_color = QColor(theme["text_main"])
            else:
                tick_height = self.MINOR_TICK_HEIGHT
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
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
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
        if context_label := self._ruler.get_parent_context(start_date):
            painter.setFont(minor_font)
            painter.setPen(QColor(theme["primary"]))
            painter.drawText(
                QRectF(8, 2, w - 16, context_h - 4),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                context_label,
            )

        # 8. Draw Playhead Handle (on top of everything else)
        self._draw_playhead_handle(painter, rect)

        # 9. Clean up
        painter.restore()

    def _draw_playhead_handle(self, painter: QPainter, rect: QRectF) -> None:
        """
        Draws a handle for the playhead in the ruler area.
        """
        playhead_time = self._playhead.get_time(self.scale_factor)

        # Convert to screen coordinates
        playhead_scene_x = playhead_time * self.scale_factor
        playhead_screen_pos = self.mapFromScene(playhead_scene_x, 0)
        screen_x = playhead_screen_pos.x()

        # Check if visible
        if screen_x < 0 or screen_x > rect.width():
            return

        # Draw Handle
        # A pentagon shape pointing down
        # Width: 14px, Height: 12px

        handle_color = QColor(self.PLAYHEAD_COLOR)  # Match playhead red

        # Check for hover/drag state to highlight
        if hasattr(self, "_dragging_playhead") and self._dragging_playhead:
            handle_color = handle_color.lighter(130)
        elif self._playhead.isUnderMouse():
            handle_color = handle_color.lighter(120)

        painter.setBrush(handle_color)
        painter.setPen(Qt.PenStyle.NoPen)

        # Define shape: Pentagon
        # Top-Left, Top-Right, Bottom-Tip
        # Actually let's do a simple pentagon: rectangle top + triangle bottom
        w = self.PLAYHEAD_HANDLE_WIDTH
        h_rect = self.PLAYHEAD_HANDLE_RECT_HEIGHT
        h_tri = self.PLAYHEAD_HANDLE_TRI_HEIGHT

        x = screen_x

        path = QPainterPath()
        # Start top-left of the rect part
        path.moveTo(x - w / 2, 0)
        # Top-right
        path.lineTo(x + w / 2, 0)
        # Bottom-right of rect
        path.lineTo(x + w / 2, h_rect)
        # Tip
        path.lineTo(x, h_rect + h_tri)
        # Bottom-left of rect
        path.lineTo(x - w / 2, h_rect)
        # Close
        path.closeSubpath()

        painter.drawPath(path)

    def set_ruler_calendar(self, converter: Any) -> None:
        """
        Configures the ruler with calendar-aware date divisions.

        Configures the ruler with calendar-aware date divisions.

        Args:
            converter (CalendarConverter): Converter instance or None.
        """
        self._ruler.set_calendar_converter(converter)
        self.viewport().update()

    def set_events(self, events: list) -> None:
        """
        Updates the scene with event items using smart lane packing.
        Reuses existing EventItem instances where possible for performance.

        Smart lane packing algorithm:
        - Greedy interval packing (First Fit)
        - Sort events by start time.
        - Packs into first available lane.
        """
        # Cleanup duplicates first to avoid pollution when scanning scene
        self._clear_duplicates()

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

        # NOTE: Don't call repack_events() here - items don't exist yet.
        # Items are created below, then repack_events() is called at line 470.

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
                    QPen(QColor(80, 80, 80), 1, Qt.PenStyle.DashLine),
                )
                line.setZValue(-1)
                line.event_id = event.id  # Mark for tracking

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
            self._update_scene_rect_from_events(sorted_events)

            # Center Playhead and Current Time Line if they are at 0 (initial state)
            min_date = sorted_events[0].lore_date
            max_date = sorted_events[-1].lore_date
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

    def repack_events(self) -> None:
        """
        Repacks events into lanes based on the current effective zoom level.
        This recalculates lane assignments to prevent overlaps as the timeline
        zooms in and out (changing the effective visual duration of text labels).
        Uses variable lane heights based on event content.
        """
        if not self.events:
            return

        # Cleanup duplicates before scanning scene for layout
        self._clear_duplicates()

        # Calculate effective scale (Scene scale * View zoom)
        # Note: scale_factor is pixels/day in Scene coordinates.
        # current_zoom is the View transformation scale.
        effective_scale = self.scale_factor * self._current_zoom

        # Update packer with effective scale
        self._lane_packer.update_scale_factor(effective_scale)

        # Dispatch to swimlane layout if grouping is active
        grouping_active = getattr(self, "_grouping_tag_order", None)

        if grouping_active and self._band_manager:
            # Validate that bands actually exist - if not, clear stale state
            bands_exist = any(
                self._band_manager.get_band(tag) for tag in grouping_active
            )
            if bands_exist:
                self._repack_grouped_events()
                return
            else:
                logger.warning(
                    "Stale grouping state detected - bands don't exist. "
                    "Falling back to standard layout."
                )
                self._grouping_tag_order = []

        event_lane_assignments, lane_heights = self._lane_packer.pack_events(
            self.events
        )

        # Calculate cumulative Y offsets for each lane
        from itertools import accumulate

        # Each offset is previous offset + previous height + padding
        # Start at 80.
        lane_y_offsets = list(
            accumulate((h + 10 for h in lane_heights[:-1]), initial=80)
        )

        # Update Y positions of existing items
        existing_items = {}
        drop_lines = {}
        for item in self.scene.items():
            if isinstance(item, EventItem):
                existing_items[item.event.id] = item
            elif hasattr(item, "event_id"):
                drop_lines[item.event_id] = item

        max_y = 80
        for event in self.events:
            if event.id in existing_items:
                lane_index = event_lane_assignments[event.id]
                y = (
                    lane_y_offsets[lane_index]
                    if lane_index < len(lane_y_offsets)
                    else 80
                )
                item = existing_items[event.id]

                # Set Y position and ensure visible
                item.setY(y)
                item.setVisible(True)
                item._initial_y = y  # Update constraint

                # Track max Y for scene rect
                event_height = EventItem.get_event_height(event)
                max_y = max(max_y, y + event_height)

                # Update drop line
                if event.id in drop_lines:
                    line = drop_lines[event.id]
                    line.setLine(item.x(), -self.RULER_HEIGHT, item.x(), y)
                    line.setVisible(True)

        # Recalculate Scene Rect Height
        # Recalculate Scene Rect Height
        current_rect = self.scene.sceneRect()
        max_y = max_y + 40  # Add margin

        if max_y != current_rect.height():
            self.scene.setSceneRect(
                current_rect.x(), current_rect.y(), current_rect.width(), max_y
            )

    def _partition_events(self, events: list, tag_order: list, mode: str) -> dict:
        """Partition events into groups based on tags."""
        groups = {tag: [] for tag in tag_order}
        ungrouped = []

        for event in events:
            # Handle both list of strings or list of Tag objects
            event_tags = getattr(event, "tags", [])
            tag_names = []
            for tag in event_tags:
                if isinstance(tag, str):
                    tag_names.append(tag)
                elif hasattr(tag, "name"):
                    tag_names.append(tag.name)

            matched = False
            for tag in tag_order:
                if tag in tag_names:
                    groups[tag].append(event)
                    matched = True
                    if mode == "FIRST_MATCH":
                        break

            if not matched:
                ungrouped.append(event)

        return groups, ungrouped

    def _clear_duplicates(self) -> tuple[dict, list]:
        """Removes all duplicate event items from the scene."""
        if (
            not hasattr(self, "_duplicate_event_items")
            or not self._duplicate_event_items
        ):
            return

        for item in self._duplicate_event_items:
            if item.scene() == self.scene:
                self.scene.removeItem(item)
        self._duplicate_event_items.clear()

    def _repack_grouped_events(self) -> None:
        """Repack events using swimlane layout (Band -> Events -> Band)."""

        # Sort events by date first for proper packing
        self.events.sort(key=lambda e: e.lore_date)

        # Build map of existing items (now clean of duplicates)
        event_items = {}
        drop_lines = {}
        for item in self.scene.items():
            if isinstance(item, EventItem):
                event_items[item.event.id] = item
            elif hasattr(item, "setLine") and hasattr(item, "event_id"):
                drop_lines[item.event_id] = item

        # (Cleanup already done by caller: repack_events)

        # 1. Partition events
        groups, ungrouped = self._partition_events(
            self.events, self._grouping_tag_order, self._grouping_mode
        )

        current_y = 60  # Start below ruler
        placed_event_ids = set()

        # 2. Iterate Groups
        for tag in self._grouping_tag_order:
            events_in_group = groups[tag]
            band = self._band_manager.get_band(tag) if self._band_manager else None

            if not band:
                continue

            # Position Band
            band.setY(current_y)
            band.setVisible(True)
            band_height = band.get_height()
            current_y += band_height + 25

            # If band is collapsed, hide events and skip space
            if band.is_collapsed:
                for event in events_in_group:
                    if event.id in event_items:
                        event_items[event.id].setVisible(False)
                        if event.id in drop_lines:
                            drop_lines[event.id].setVisible(False)
                continue

            # Band is expanded - pack and show events
            if events_in_group:
                # Pack events for this group
                layout_map, lane_heights = self._lane_packer.pack_events(
                    events_in_group
                )

                # Position events
                for event in events_in_group:
                    if event.id not in event_items:
                        continue

                    # Choose item: Original or Duplicate
                    if event.id in placed_event_ids:
                        # Duplicate for subsequent groups
                        item = EventItem(event, self.scale_factor)
                        item.on_drag_complete = self._on_event_drag_complete
                        self.scene.addItem(item)
                        self._duplicate_event_items.append(item)
                    else:
                        item = event_items[event.id]
                        placed_event_ids.add(event.id)

                    lane_idx = layout_map[event.id]

                    # Calculate Y offset within group
                    y_offset = 0
                    for i in range(lane_idx):
                        y_offset += lane_heights[i] + self._lane_packer.LANE_PADDING

                    item.setY(current_y + y_offset)
                    item.setVisible(True)
                    item._initial_y = current_y + y_offset

                    # Update drop lines - only for the item we are using now
                    if event.id in drop_lines and item == event_items[event.id]:
                        line = drop_lines[event.id]
                        line.setVisible(True)
                        line.setLine(item.x(), -self.RULER_HEIGHT, item.x(), item.y())

                # Advance current_y by group height
                total_group_height = 0
                if lane_heights:
                    total_group_height = (
                        sum(lane_heights)
                        + (len(lane_heights) - 1) * self._lane_packer.LANE_PADDING
                    )

                current_y += total_group_height + 20  # Padding between groups
            else:
                # No events in this group
                current_y += 10  # Minimal padding

        # 3. Add "All Events" Group
        # This group shows ALL events:
        # - Ungrouped events use their ORIGINAL EventItem (not positioned yet)
        # - Grouped events use DUPLICATE EventItem instances
        current_y += 20

        # Create/get "All events" band
        all_events_band = None
        if self._band_manager:
            all_events_band = self._band_manager.get_band(self.ALL_EVENTS_GROUP_NAME)

        if not all_events_band:
            logger.warning(f"Band for '{self.ALL_EVENTS_GROUP_NAME}' not found")
        else:
            # Position "All events" band
            all_events_band.setY(current_y)
            all_events_band.setVisible(True)
            band_height = all_events_band.get_height()
            current_y += band_height + 25

        # The "All events" group will use placed_event_ids to determine duplication
        grouped_event_ids = placed_event_ids

        # Check if "All events" band is collapsed - skip event positioning
        if all_events_band and all_events_band.is_collapsed:
            # Hide ungrouped events (their original items)
            for event in self.events:
                if event.id not in grouped_event_ids and event.id in event_items:
                    event_items[event.id].setVisible(False)
                    if event.id in drop_lines:
                        drop_lines[event.id].setVisible(False)
        else:
            # Band is expanded - show all events

            # Pack ALL events for the "All events" section
            layout_map, lane_heights = self._lane_packer.pack_events(self.events)

            for event in self.events:
                lane_idx = layout_map[event.id]
                y_offset = sum(lane_heights[:lane_idx]) + (
                    lane_idx * self._lane_packer.LANE_PADDING
                )

                target_y = current_y + y_offset

                if event.id in grouped_event_ids:
                    # Event was already in a tag group - create a DUPLICATE
                    duplicate_item = EventItem(event, self.scale_factor)
                    duplicate_item.on_drag_complete = self._on_event_drag_complete

                    # Add to scene
                    self.scene.addItem(duplicate_item)
                    self._duplicate_event_items.append(duplicate_item)

                    self._position_event_item(duplicate_item, target_y)
                elif event.id in event_items:
                    # Event was ungrouped - use its ORIGINAL item
                    item = event_items[event.id]
                    self._position_event_item(item, target_y, drop_lines)

            if lane_heights:
                current_y += sum(lane_heights) + (
                    len(lane_heights) * self._lane_packer.LANE_PADDING
                )

        # Update scene rect
        current_rect = self.scene.sceneRect()
        # Ensure we cover everything
        self.scene.setSceneRect(
            current_rect.x(), 0, current_rect.width(), current_y + 100
        )

        # Update label overlay to reflect new band positions
        self._update_label_overlay()

    def fit_all(self) -> None:
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

            self._apply_zoom(scale_x)

            # Center X, Align Top Y
            center_x = (start_x + end_x) / 2
            vh = self.viewport().height()
            scene_top = self.scene.sceneRect().top()

            self.centerOn(center_x, scene_top + vh / 2)

            # Explicitly ensure we are at the top (redundancy for safety)
            self.verticalScrollBar().setValue(self.verticalScrollBar().minimum())

    def wheelEvent(self, event: QWheelEvent) -> None:
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
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

            try:
                # Apply zoom
                self.scale(factor, 1.0)
                self._current_zoom = new_zoom

                # Update playhead zoom
                self._playhead.set_zoom(new_zoom * self.scale_factor)

                # Repack on new zoom
                self.repack_events()
            finally:
                # Restore original anchor
                self.setTransformationAnchor(old_anchor)

    def update_event_preview(self, event_data: dict) -> None:
        """
        Updates the visual representation of an event in real-time.

        Args:
            event_data: dictionary containing transient event state.
        """
        event_id = event_data.get("id")
        if not event_id:
            return

        # Find the item
        # Find the item
        found_item = next(
            (
                item
                for item in self.scene.items()
                if isinstance(item, EventItem) and item.event.id == event_id
            ),
            None,
        )

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

    def mousePressEvent(self, event: QMouseEvent) -> None:
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

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """
        Handles mouse release. Emits playhead_time_changed if playhead was dragged.
        """
        super().mouseReleaseEvent(event)

        if hasattr(self, "_dragging_playhead") and self._dragging_playhead:
            # Emit final authoritative signal with rounded playhead time
            # This ensures markers snap to exact position after scrubbing
            new_time = round(self._playhead.get_time(self.scale_factor), 4)
            self.playhead_time_changed.emit(new_time)
            self._dragging_playhead = False

            # Persist the new time on release
            settings = QSettings()
            settings.setValue("timeline/playhead_time", new_time)

    def focus_event(self, event_id: str) -> None:
        """Centers the view on the specified event."""
        for item in self.scene.items():
            if isinstance(item, EventItem) and item.event.id == event_id:
                self.centerOn(item)
                item.setSelected(True)
                return

    def _apply_zoom(self, zoom_level: float) -> None:
        """
        Applies a zoom level and updates related state.

        Args:
            zoom_level: The zoom level to apply.
        """
        self.setTransform(QTransform().scale(zoom_level, 1.0))
        self._current_zoom = zoom_level
        self._playhead.set_zoom(zoom_level * self.scale_factor)
        self.repack_events()

    def _setup_ruler_fonts(self, painter: QPainter) -> tuple[QFont, QFont]:
        """Sets up major and minor fonts for the ruler."""
        major_font = QFont(painter.font())
        major_font.setPointSize(9)
        major_font.setBold(True)

        minor_font = QFont(painter.font())
        minor_font.setPointSize(8)
        minor_font.setBold(False)
        return major_font, minor_font

    def _position_event_item(
        self, item: EventItem, y: float, drop_lines: dict | None = None
    ) -> None:
        """
        Positions an event item and updates its associated drop line.
        """
        item.setY(y)
        item.setVisible(True)
        item._initial_y = y

        if drop_lines and item.event.id in drop_lines:
            line = drop_lines[item.event.id]
            line.setLine(item.x(), -self.RULER_HEIGHT, item.x(), item.y())
            line.setVisible(True)

    def start_playback(self) -> None:
        """
        Starts automatic playhead advancement.
        """
        if not self._playback_timer.isActive():
            self._playback_timer.start(self._playback_interval)

    def stop_playback(self) -> None:
        """
        Stops automatic playhead advancement.
        """
        self._playback_timer.stop()
        self.save_state()

    def save_state(self) -> None:
        """Saves current state (playhead time) to settings."""
        settings = QSettings()
        time = self._playhead.get_time(self.scale_factor)
        settings.setValue("timeline/playhead_time", time)

    def is_playing(self) -> bool:
        """
        Returns whether playback is currently active.

        Returns:
            bool: True if playing, False otherwise.
        """
        return self._playback_timer.isActive()

    def set_playhead_time(self, time: float) -> None:
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

    def step_forward(self) -> None:
        """
        Steps the playhead forward by the playback step amount.
        """
        current_time = self.get_playhead_time()
        new_time = current_time + self._playback_step
        self.set_playhead_time(new_time)

    def step_backward(self) -> None:
        """
        Steps the playhead backward by the playback step amount.
        """
        current_time = self.get_playhead_time()
        new_time = current_time - self._playback_step
        self.set_playhead_time(new_time)

    def _advance_playhead(self) -> None:
        """
        Internal method called by timer to advance playhead during playback.
        """
        self.step_forward()

    def set_current_time(self, time: float) -> None:
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

    # -------------------------------------------------------------------------
    # Timeline Grouping Methods (Milestone 3)
    # -------------------------------------------------------------------------

    def set_data_provider(self, provider: Any) -> None:
        """
        Set the data provider for timeline grouping features.

        The provider should implement methods:
        - get_group_metadata(tag_order, date_range) -> list of metadata dicts
        - get_events_for_group(tag_name, date_range) -> list of Event objects

        Args:
            provider: Object implementing the data provider interface
        """
        self._data_provider = provider

        # Initialize band manager if not already done
        if self._band_manager is None and provider is not None:
            self._band_manager = GroupBandManager(
                self.scene,
                get_group_metadata_callback=provider.get_group_metadata,
                get_events_for_group_callback=provider.get_events_for_group,
                parent=self,
            )

            # Connect band manager signals
            self._band_manager.band_expanded.connect(self._on_band_expanded)
            self._band_manager.band_collapsed.connect(self._on_band_collapsed)
            self._band_manager.tag_color_change_requested.connect(
                self._on_tag_color_change_requested
            )
            self._band_manager.tag_rename_requested.connect(
                self._on_tag_rename_requested
            )
            self._band_manager.remove_from_grouping_requested.connect(
                self._on_remove_from_grouping_requested
            )

            logger.info("Group band manager initialized with data provider")

    def set_grouping_config(self, tag_order: list, mode: str = "DUPLICATE") -> None:
        """
        Set the timeline grouping configuration.

        Args:
            tag_order: List of tag names to group by
            mode: Grouping mode ("DUPLICATE" or "FIRST_MATCH")
        """
        if self._band_manager is None:
            logger.warning("Cannot set grouping: band manager not initialized")
            return

        # Get visible date range for filtering
        date_range = self._get_visible_date_range()

        # Store config for layout logic
        self._grouping_tag_order = tag_order
        self._grouping_mode = mode

        # Automatically append "All events" group to tag order
        tag_order_with_all = tag_order.copy()
        if self.ALL_EVENTS_GROUP_NAME not in tag_order_with_all:
            tag_order_with_all.append(self.ALL_EVENTS_GROUP_NAME)

        # Update band manager with extended tag order
        self._band_manager.set_grouping_config(tag_order_with_all, date_range)

        # Trigger layout update to include bands
        self.repack_events()

        # Scroll to top to ensure bands are visible
        self.verticalScrollBar().setValue(self.verticalScrollBar().minimum())

        logger.info(f"Grouping set: {len(tag_order)} tags, mode={mode}")

    def clear_grouping(self) -> None:
        """Clear all timeline grouping bands."""
        if self._band_manager is not None:
            self._band_manager.clear_bands()
        # Reset grouping state
        self._grouping_tag_order = []
        # Clear label overlay
        self._label_overlay.clear_labels()
        # Trigger repack to restore standard layout
        self.repack_events()
        logger.info("Grouping cleared")

    def update_band_metadata(self) -> None:
        """Update metadata for all bands (counts, dates)."""
        if self._band_manager is not None:
            date_range = self._get_visible_date_range()
            self._band_manager.update_band_metadata(date_range)

    def _get_visible_date_range(self) -> tuple | None:
        """
        Get the currently visible date range in the viewport.

        Returns:
            tuple: (start_date, end_date) or None
        """
        try:
            viewport_rect = self.viewport().rect()
            left_scene = self.mapToScene(viewport_rect.topLeft())
            right_scene = self.mapToScene(viewport_rect.topRight())

            start_date = left_scene.x() / self.scale_factor
            end_date = right_scene.x() / self.scale_factor

            return (start_date, end_date)
        except Exception as e:
            logger.warning(f"Could not calculate visible date range: {e}")
            return None

    def _on_band_expanded(self, tag_name: str) -> None:
        """
        Handle band expansion.

        Args:
            tag_name: The tag name that was expanded
        """

        # Repack events to update positions and show events in this group
        self.repack_events()

    def _on_band_collapsed(self, tag_name: str) -> None:
        """
        Handle band collapse.

        Args:
            tag_name: The tag name that was collapsed
        """

        # Repack events to update positions and hide events in this group
        self.repack_events()

    def _update_label_overlay(self) -> None:
        """
        Update the label overlay positions to match current band positions.

        This should be called after bands are repositioned (e.g., after
        repack_events, band expand/collapse).
        """
        if not self._band_manager or not self._grouping_tag_order:
            self._label_overlay.clear_labels()
            return

        # Collect label data from bands
        # Include both user-selected tags and "All events"
        labels = []
        all_tags = list(self._grouping_tag_order) + [self.ALL_EVENTS_GROUP_NAME]

        for tag in all_tags:
            band = self._band_manager.get_band(tag)
            if band and band.isVisible():
                # Convert scene Y to view Y
                band_scene_y = band.y()
                band_view_pos = self.mapFromScene(0, band_scene_y)

                # Adjust for overlay widget's starting position
                # (overlay starts at RULER_HEIGHT in viewport)
                y_in_overlay = band_view_pos.y() - self.RULER_HEIGHT

                labels.append(
                    {
                        "tag_name": tag,
                        "y_pos": y_in_overlay,
                        "color": band._color.name(),
                        "is_collapsed": band.is_collapsed,
                    }
                )

        self._label_overlay.set_labels(labels)

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        """Handle scroll events to update label positions."""
        super().scrollContentsBy(dx, dy)

        # Update label positions when scrolling vertically
        if dy != 0:
            self._update_label_overlay()

    def _on_tag_color_change_requested(self, tag_name: str) -> None:
        """
        Handle tag color change request.

        Args:
            tag_name: The tag name to change color for
        """

        # TODO: Show color picker dialog and update tag color
        # This should be handled by the main window/controller
        # For now, just log
        # For now, just log

    def _on_tag_rename_requested(self, tag_name: str) -> None:
        """
        Handle tag rename request.

        Args:
            tag_name: The tag name to rename
        """

        # TODO: Show rename dialog
        # This should be handled by the main window/controller
        # This should be handled by the main window/controller

    def _on_remove_from_grouping_requested(self, tag_name: str) -> None:
        """
        Handle request to remove a tag from grouping.

        Args:
            tag_name: The tag name to remove
        """

        # TODO: Update grouping configuration to exclude this tag
        # This should be handled by the main window/controller
        # This should be handled by the main window/controller

    def _update_scene_rect_from_events(self, sorted_events: list) -> None:
        """Updates the scene rectangle based on event bounds."""
        # X bounds
        min_date = sorted_events[0].lore_date
        max_date = sorted_events[-1].lore_date
        if min_date == max_date:
            min_date -= 10
            max_date += 10

        margin_x = (max_date - min_date) * 0.1 or 100
        start_x = (min_date - margin_x) * self.scale_factor
        end_x = (max_date + margin_x) * self.scale_factor

        # Y bounds - inspect items to find max Y
        max_y_found = 60
        for item in self.scene.items():
            if isinstance(item, EventItem):
                max_y_found = max(max_y_found, item.y())

        max_y = max_y_found + self.LANE_HEIGHT + 40
        min_y = 0

        # Set Scene Rect explicitly to avoid infinite lines expanding it
        self.scene.setSceneRect(start_x, min_y, end_x - start_x, max_y - min_y)
