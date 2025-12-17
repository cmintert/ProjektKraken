"""
Timeline Lane Packer Module.

Provides the lane packing algorithm for organizing events on the timeline
without overlaps using a greedy "First Fit" approach.
"""

from typing import List, Dict
from PySide6.QtGui import QFont, QFontMetrics
import logging

logger = logging.getLogger(__name__)


class TimelineLanePacker:
    """
    Handles the lane packing algorithm for timeline events.

    Uses a greedy "First Fit" algorithm to pack events into lanes,
    minimizing vertical space while preventing visual overlaps.
    """

    # Constants for spacing
    GAP_PIXELS = 15  # Gap between events in pixels
    MIN_BAR_WIDTH = 10.0  # Minimum width for duration bars

    def __init__(self, scale_factor: float = 20.0):
        """
        Initializes the TimelineLanePacker.

        Args:
            scale_factor: The current timeline scale factor (pixels per day).
        """
        self.scale_factor = scale_factor
        self.font = None
        self.fm = None

    def _ensure_font_metrics(self):
        """Ensures font metrics are initialized (requires QApplication)."""
        if self.fm is None:
            self.font = QFont()
            self.font.setBold(True)
            self.fm = QFontMetrics(self.font)

    def pack_events(self, events: List) -> Dict[str, int]:
        """
        Packs events into lanes using the First Fit algorithm.

        Args:
            events: List of Event objects to pack (should be sorted by
                lore_date).

        Returns:
            Dict mapping event ID to lane index.
        """
        # Ensure font metrics are initialized
        self._ensure_font_metrics()

        lanes_end_times = []  # Stores end time (in lore date units) per lane
        event_lane_assignments = {}

        logger.debug(
            f"Packing {len(events)} events. Scale: {self.scale_factor}"
        )

        for event in events:
            start_time = event.lore_date

            # Calculate visual duration (in time units)
            visual_duration = self._calculate_visual_duration(event)
            gap_duration = self.GAP_PIXELS / self.scale_factor

            end_time = start_time + visual_duration + gap_duration

            # First Fit (Gravity) - find first available lane
            assigned_lane = self._find_available_lane(
                lanes_end_times, start_time, end_time
            )

            event_lane_assignments[event.id] = assigned_lane

        return event_lane_assignments

    def _calculate_visual_duration(self, event) -> float:
        """
        Calculates the visual duration of an event in time units.

        Takes into account the event's actual duration and text label width
        to determine how much horizontal space it needs.

        Args:
            event: The Event object.

        Returns:
            float: Visual duration in lore date units.
        """
        text_width = self.fm.horizontalAdvance(event.name)

        if event.lore_duration > 0:
            # Duration Event - has a bar
            bar_width_px = max(
                event.lore_duration * self.scale_factor, self.MIN_BAR_WIDTH
            )

            # Check if text fits inside the bar
            if text_width < bar_width_px - 10:
                # Text fits inside bar
                total_width_px = bar_width_px
            else:
                # Text flows to right: Bar + Padding + Text
                total_width_px = bar_width_px + 5 + text_width
        else:
            # Point Event - diamond icon + text
            # Diamond (half width 7) + Padding (5) + Text + Safety margin
            total_width_px = 7 + 5 + text_width + 5

        # Convert pixels to time duration
        return total_width_px / self.scale_factor

    def _find_available_lane(
        self, lanes_end_times: List[float], start_time: float, end_time: float
    ) -> int:
        """
        Finds the first available lane for an event.

        Args:
            lanes_end_times: List of end times for each existing lane.
            start_time: When the event starts.
            end_time: When the event ends (including visual space).

        Returns:
            int: The lane index (0-based).
        """
        # Try to find an existing lane that's available
        for i, lane_end in enumerate(lanes_end_times):
            if lane_end <= start_time:
                # This lane is available
                lanes_end_times[i] = end_time
                return i

        # No available lane found, create a new one
        lanes_end_times.append(end_time)
        return len(lanes_end_times) - 1

    def update_scale_factor(self, scale_factor: float):
        """
        Updates the scale factor for packing calculations.

        Args:
            scale_factor: New scale factor (pixels per day).
        """
        self.scale_factor = scale_factor
