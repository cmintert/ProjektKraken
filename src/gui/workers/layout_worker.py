"""Timeline Layout Worker Module.

Provides asynchronous lane packing calculation for timeline events using QRunnable.
"""

import logging
import time
from collections.abc import Sequence

from PySide6.QtCore import QObject, QRunnable, Signal

from src.core.timeline_layout import TimelineLayoutInput, pack_timeline_intervals

logger = logging.getLogger(__name__)

_SLOW_LAYOUT_THRESHOLD_SECONDS = 0.1


class LayoutWorkerSignals(QObject):
    """Signals for the LayoutWorker.

    Qt signals must be defined in a QObject subclass.
    """

    finished = Signal(int, dict, list, float)
    error = Signal(int, str)


class LayoutWorker(QRunnable):
    """A worker for calculating timeline lane layout in a background thread.

    Uses Qt's thread pool to perform lane packing calculations off the main thread,
    preventing UI freezes during zoom or large timeline operations.
    """

    def __init__(
        self,
        intervals: Sequence[TimelineLayoutInput],
        request_token: int,
    ) -> None:
        """Initialize the layout worker.

        Args:
            intervals: Detached GUI-measured intervals to pack.
            request_token: Identity returned with either completion signal.
        """
        super().__init__()
        self.intervals = tuple(intervals)
        self.request_token = request_token
        self.signals = LayoutWorkerSignals()
        self.setAutoDelete(True)

    def run(self) -> None:
        """Execute the lane packing calculation.

        This runs in a background thread. Results are emitted via signals.
        """
        try:
            start_time = time.perf_counter()

            lane_assignments, lane_heights = pack_timeline_intervals(self.intervals)

            elapsed = time.perf_counter() - start_time

            # Emit results back to main thread
            self.signals.finished.emit(
                self.request_token, lane_assignments, lane_heights, elapsed
            )

            if elapsed > _SLOW_LAYOUT_THRESHOLD_SECONDS:
                logger.warning(
                    f"Lane packing took {elapsed:.3f}s for {len(self.intervals)} events"
                )

        except Exception as e:
            logger.error(f"Layout worker error: {e}", exc_info=True)
            self.signals.error.emit(self.request_token, str(e))
