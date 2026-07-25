"""Qt thread-pool adapter for pure raster spatial queries."""

from __future__ import annotations

from typing import Any

import numpy as np
from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from src.services.raster_query_service import compute_resampled_query


class RasterQuerySignals(QObject):
    """Signals emitted by a background raster query."""

    finished = Signal(object)
    failed = Signal(str)


class RasterQueryTask(QRunnable):
    """Run a spatial query without blocking the Qt main thread."""

    def __init__(
        self,
        arrays: list[np.ndarray],
        modes: list[str],
        conditions: list[dict[str, Any]],
    ) -> None:
        super().__init__()
        self.arrays = [array.copy() for array in arrays]
        self.modes = list(modes)
        self.conditions = [dict(condition) for condition in conditions]
        self.signals = RasterQuerySignals()

    @Slot()
    def run(self) -> None:
        """Compute and emit the mask or a user-facing error."""
        try:
            result = compute_resampled_query(
                self.arrays, self.modes, self.conditions
            )
            self.signals.finished.emit(result)
        except Exception as exc:
            self.signals.failed.emit(str(exc))
