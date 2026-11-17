"""Coalesced projection requests with world and map generation protection."""

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot

from src.gui.widgets.map.connected_features import ConnectedFeatures
from src.services.map_projection_calculation import MapProjectionCalculation
from src.services.map_projection_reader import DatabaseProvider, MapProjectionReader


class MapProjectionCoordinator(QObject):
    """Dispatch through a feature adapter; keep all database access off the UI."""

    requested = Signal(dict)
    calculate_requested = Signal(dict)

    def __init__(
        self,
        overlay: ConnectedFeatures,
        thread: QThread,
        database: DatabaseProvider,
        world: Callable[[], str],
        target: Callable[[], str | None],
        date: Callable[[], float],
        parent: QObject | None = None,
    ) -> None:
        """Compose narrow live-context providers and a worker-owned reader."""
        super().__init__(parent)
        self.overlay, self.world, self.target, self.date = overlay, world, target, date
        self.reader = MapProjectionReader(database)
        self.reader.moveToThread(thread)
        thread.finished.connect(self.reader.deleteLater)
        self.requested.connect(self.reader.run, Qt.ConnectionType.QueuedConnection)
        self.reader.completed.connect(self.captured, Qt.ConnectionType.QueuedConnection)
        self.calculation_thread = QThread(self)
        self.calculator = MapProjectionCalculation()
        self.calculator.moveToThread(self.calculation_thread)
        self.calculation_thread.finished.connect(self.calculator.deleteLater)
        self.calculate_requested.connect(
            self.calculator.run, Qt.ConnectionType.QueuedConnection
        )
        self.calculator.completed.connect(
            self.completed, Qt.ConnectionType.QueuedConnection
        )
        self.calculation_thread.start()
        self.revision = 0
        self.token = 0
        self.busy = False
        self.dirty = False
        self.stopped = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.send)
        overlay.changed.connect(self.refresh)
        if parent is not None:
            parent.destroyed.connect(self.shutdown)

    @Slot()
    def shutdown(self) -> None:
        """Join feature calculation before its owner and scene are destroyed."""
        self.timer.stop()
        self.stopped = True
        self.dirty = False
        self.token += 1
        self.calculation_thread.quit()
        self.calculation_thread.wait()

    @Slot(dict)
    def captured(self, result: dict[str, Any]) -> None:
        """Send current captures to CPU work without occupying the DB thread."""
        if (
            "snapshot" in result
            and result["token"] == self.token
            and self.overlay.enabled
        ):
            self.calculate_requested.emit(result)
        else:
            self.completed(result)

    @Slot()
    def invalidate(self, *_args: Any) -> None:
        """Refresh authored inputs after saves, hierarchy/world changes or undo."""
        self.revision += 1
        self.refresh()

    @Slot()
    def refresh(self, *_args: Any) -> None:
        """Clear frames whose map, authored inputs, or presentation changed."""
        if self.stopped:
            return
        self.token += 1
        self.overlay.clear()
        self.refresh_playhead()

    @Slot()
    def refresh_playhead(self, *_args: Any) -> None:
        """Keep the current frame visible and sample the latest date at each send."""
        if self.stopped:
            return
        self.dirty = True
        self._schedule_send()

    def _schedule_send(self) -> None:
        """Start a bounded wait without postponing an already scheduled send."""
        if not self.busy and self.overlay.enabled and not self.timer.isActive():
            self.timer.start()

    def send(self) -> None:
        """Keep at most one worker request in flight and one latest continuation."""
        if self.stopped or self.busy or not self.overlay.enabled or not self.target():
            return
        self.dirty = False
        self.busy = True
        image = self.overlay.view.pixmap_item
        bounds = image.boundingRect() if image is not None else None
        scale = abs(self.overlay.view.transform().m11())
        self.requested.emit(
            {
                "token": self.token,
                "world": self.world(),
                "target": self.target(),
                "date": self.date(),
                "revision": self.revision,
                "zoom": abs(self.overlay.view.transform().m11()),
                "fit_ratio": self.overlay.view.zoom_factor,
                "include_detail": self.overlay.include_detail,
                "pixel_size": (bounds.width() * scale, bounds.height() * scale)
                if bounds
                else None,
            }
        )

    @Slot(dict)
    def completed(self, result: dict[str, Any]) -> None:
        """Display frames from the current context and continue to the latest date."""
        self.busy = False
        if self.stopped:
            return
        if result["token"] == self.token and self.overlay.enabled:
            self.overlay.display(result)
        if self.dirty:
            self._schedule_send()
