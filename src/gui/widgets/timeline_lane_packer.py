"""Timeline Lane Packer Module.

Measures timeline bounds and delegates detached, stable lane packing.
"""

from PySide6.QtGui import QFont, QFontMetrics

from src.core.events import Event
from src.core.temporal_display import TemporalDisplay
from src.core.temporal_presentation import event_temporal_presentation
from src.core.timeline_layout import (
    TimelineLayoutInput,
    TimelineLayoutSnapshot,
    pack_stable_timeline_intervals,
)
from src.gui.widgets.timeline.event_item import EventItem
from src.gui.widgets.timeline.item_layout import timeline_item_layout
from src.gui.widgets.timeline.temporal_geometry import (
    TemporalGeometry,
)


class TimelineLanePacker:
    """Handles the lane packing algorithm for timeline events.

    Saved dates order overlapping events above later ones. Rows are minimized
    under chronological precedence; heights follow current row members.
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

    def pack_events(
        self,
        events: list[Event],
        previous: TimelineLayoutSnapshot = TimelineLayoutSnapshot(),
    ) -> tuple[dict[str, int], list[int]]:
        """Pack measured events, retaining valid accepted lane placements.

        Args:
            events: List of Event objects to pack (should be sorted by
                lore_date).
            previous: Frozen accepted occurrence layout, or empty for compaction.

        Returns:
            Tuple of:
                - Dict mapping event ID to lane index
                - List of lane heights (max height of events in each lane)

        """
        return pack_stable_timeline_intervals(self.measure_events(events), previous)

    def measure_events(self, events: list[Event]) -> tuple[TimelineLayoutInput, ...]:
        """Capture detached numeric bounds on the GUI thread before dispatch."""
        self._ensure_font_metrics()
        measured = []
        for event in events:
            if event.lore_date is None:
                continue
            layout = timeline_item_layout(
                event_temporal_presentation(event, EventItem._calendar_converter),
                event.name,
                self.scale_factor,
            )
            start = event.require_date() + layout.bounds.left() / self.scale_factor
            visual_duration = layout.bounds.width() / self.scale_factor
            gap_duration = self.GAP_PIXELS / self.scale_factor
            measured.append(
                TimelineLayoutInput(
                    event.id,
                    start,
                    start + visual_duration + gap_duration,
                    max(layout.height, EventItem.get_event_height(event)),
                    event.lore_date,
                )
            )
        return tuple(measured)

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
        layout = timeline_item_layout(
            event_temporal_presentation(event, EventItem._calendar_converter),
            event.name,
            self.scale_factor,
        )
        return layout.bounds.width() / self.scale_factor

    def update_scale_factor(self, scale_factor: float) -> None:
        """Updates the scale factor for packing calculations.

        Args:
            scale_factor: New scale factor (pixels per day).

        """
        self.scale_factor = scale_factor
