"""Timeline Lane Packer Module.

Provides the lane packing algorithm for organizing events on the timeline without
overlaps using a greedy "First Fit" approach.
"""

from PySide6.QtGui import QFont, QFontMetrics

from src.core.events import Event
from src.core.temporal_display import TemporalDisplay, event_temporal_display
from src.gui.widgets.timeline.event_item import EventItem
from src.gui.widgets.timeline.temporal_geometry import (
    TemporalGeometry,
    project_temporal_geometry,
)


class TimelineLanePacker:
    """Handles the lane packing algorithm for timeline events.

    Uses a greedy "First Fit" algorithm to pack events into lanes, minimizing vertical
    space while preventing visual overlaps. Supports variable-height events by tracking
    per-lane heights.
    """

    # Constants for spacing
    GAP_PIXELS = 15  # Gap between events in pixels
    LANE_PADDING = 10  # Vertical padding between lanes

    def __init__(self, scale_factor: float = 20.0) -> None:
        """Initializes the TimelineLanePacker.

        Args:
            scale_factor: The current timeline scale factor (pixels per day).

        """
        self.scale_factor = scale_factor
        self.font: QFont | None = None
        self.fm: QFontMetrics | None = None

    def _ensure_font_metrics(self) -> None:
        """Ensures font metrics are initialized (requires QApplication)."""
        if self.fm is None:
            font = QFont()
            font.setBold(True)
            self.font = font
            self.fm = QFontMetrics(font)

    def pack_events(self, events: list[Event]) -> tuple[dict[str, int], list[int]]:
        """Packs events into lanes using the First Fit algorithm.

        Args:
            events: List of Event objects to pack (should be sorted by
                lore_date).

        Returns:
            Tuple of:
                - Dict mapping event ID to lane index
                - List of lane heights (max height of events in each lane)

        """
        self._ensure_font_metrics()

        lanes_end_times: list[float] = []
        lanes_heights: list[int] = []
        event_lane_assignments: dict[str, int] = {}

        projected: list[tuple[float, Event, TemporalDisplay, TemporalGeometry]] = []
        for event in events:
            display = event_temporal_display(event, EventItem._calendar_converter)
            geometry = project_temporal_geometry(display, self.scale_factor)
            projected.append(
                (
                    event.lore_date + geometry.left / self.scale_factor,
                    event,
                    display,
                    geometry,
                )
            )
        projected.sort(key=lambda entry: entry[0])
        for start_time, event, display, geometry in projected:
            event_height = EventItem.get_event_height(event)

            visual_duration = self._calculate_visual_duration(
                event, display=display, geometry=geometry
            )
            gap_duration = self.GAP_PIXELS / self.scale_factor

            end_time = start_time + visual_duration + gap_duration

            # First Fit (Gravity) - find first available lane
            assigned_lane = self._find_available_lane(
                lanes_end_times, lanes_heights, start_time, end_time, event_height
            )

            event_lane_assignments[event.id] = assigned_lane

        return event_lane_assignments, lanes_heights

    def _calculate_visual_duration(
        self,
        event: Event,
        *,
        display: TemporalDisplay | None = None,
        geometry: TemporalGeometry | None = None,
    ) -> float:
        """Calculates the visual duration of an event in time units.

        Takes into account the event's actual duration and text label width
        to determine how much horizontal space it needs.

        Args:
            event: The Event object.

        Returns:
            float: Visual duration in lore date units.

        """
        if self.fm is None:
            self._ensure_font_metrics()
        # Double check after ensure
        if self.fm is None:
            # Should practically never happen if QApplication exists
            return 0.0

        if display is None:
            display = event_temporal_display(event, EventItem._calendar_converter)
        if geometry is None:
            geometry = project_temporal_geometry(display, self.scale_factor)
        label_width = max(
            self.fm.horizontalAdvance(event.name),
            self.fm.horizontalAdvance(display.caption),
        )
        right = max(geometry.right, geometry.label_left + label_width + 10)
        return (right - geometry.left) / self.scale_factor

    def _find_available_lane(
        self,
        lanes_end_times: list[float],
        lanes_heights: list[int],
        start_time: float,
        end_time: float,
        event_height: int,
    ) -> int:
        """Finds the first available lane for an event.

        Args:
            lanes_end_times: List of end times for each existing lane.
            lanes_heights: List of max heights for each existing lane.
            start_time: When the event starts.
            end_time: When the event ends (including visual space).
            event_height: Height of this event in pixels.

        Returns:
            int: The lane index (0-based).

        """
        # Try to find an existing lane that's available
        for i, lane_end in enumerate(lanes_end_times):
            if lane_end <= start_time:
                # This lane is available - update its end time and max height
                lanes_end_times[i] = end_time
                lanes_heights[i] = max(lanes_heights[i], event_height)
                return i

        # No available lane found, create a new one
        lanes_end_times.append(end_time)
        lanes_heights.append(event_height)
        return len(lanes_end_times) - 1

    def update_scale_factor(self, scale_factor: float) -> None:
        """Updates the scale factor for packing calculations.

        Args:
            scale_factor: New scale factor (pixels per day).

        """
        self.scale_factor = scale_factor
