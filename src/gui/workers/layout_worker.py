"""Timeline Layout Worker Module.

Provides asynchronous lane packing calculation for timeline events using QRunnable.
"""

import logging
import time
from typing import List

from PySide6.QtCore import QObject, QRunnable, Signal

from src.core.events import Event
from src.gui.widgets.timeline_lane_packer import TimelineLanePacker

logger = logging.getLogger(__name__)

_SLOW_LAYOUT_THRESHOLD_SECONDS = 0.1


class LayoutWorkerSignals(QObject):
    """Signals for the LayoutWorker.

    Qt signals must be defined in a QObject subclass.
    """

    finished = Signal(
        dict, list, float
    )  # (lane_assignments, lane_heights, elapsed_time)
    error = Signal(str)  # error message


class LayoutWorker(QRunnable):
    """A worker for calculating timeline lane layout in a background thread.

    Uses Qt's thread pool to perform lane packing calculations off the main thread,
    preventing UI freezes during zoom or large timeline operations.
    """

    def __init__(
        self,
        events: List[Event],
        scale_factor: float,
        grouping_config: dict | None = None,
    ) -> None:
        """Initialize the layout worker.

        Args:
            events: List of Event objects to pack.
            scale_factor: Current timeline scale factor (pixels per day).
            grouping_config: Optional grouping configuration for swimlane layout.
        """
        super().__init__()
        self.events = events.copy()  # Copy to avoid concurrent modification
        self.scale_factor = scale_factor
        self.grouping_config = grouping_config or {}
        self.signals = LayoutWorkerSignals()
        self.setAutoDelete(True)

    def run(self) -> None:
        """Execute the lane packing calculation.

        This runs in a background thread. Results are emitted via signals.
        """
        try:
            start_time = time.perf_counter()

            # Create a lane packer with current scale
            packer = TimelineLanePacker(self.scale_factor)

            # Perform packing (this is the expensive O(N²) operation)
            lane_assignments, lane_heights = packer.pack_events(self.events)

            elapsed = time.perf_counter() - start_time

            # Emit results back to main thread
            self.signals.finished.emit(lane_assignments, lane_heights, elapsed)

            if elapsed > _SLOW_LAYOUT_THRESHOLD_SECONDS:
                logger.warning(
                    f"Lane packing took {elapsed:.3f}s for {len(self.events)} events"
                )

        except Exception as e:
            logger.error(f"Layout worker error: {e}", exc_info=True)
            self.signals.error.emit(str(e))
