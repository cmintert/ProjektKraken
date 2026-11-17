"""Coalesced projection requests with world/map/date generation protection."""

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot

from src.gui.widgets.map.connected_features import ConnectedFeatures
from src.services.map_projection_reader import DatabaseProvider, MapProjectionReader


class MapProjectionCoordinator(QObject):
    """Dispatch through a feature adapter; keep all database access off the UI."""

    requested = Signal(dict)

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
        self.reader.completed.connect(
            self.completed, Qt.ConnectionType.QueuedConnection
        )
        self.revision = 0
        self.token = 0
        self.busy = False
        self.dirty = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.send)
        overlay.changed.connect(self.refresh)

    @Slot()
    def invalidate(self, *_args: Any) -> None:
        """Refresh authored inputs after saves, hierarchy/world changes or undo."""
        self.revision += 1
        self.refresh()

    @Slot()
    def refresh(self, *_args: Any) -> None:
        """Invalidate stale replies immediately and coalesce repeated UI changes."""
        self.token += 1
        self.dirty = True
        self.overlay.clear()
        self.timer.start()

    def send(self) -> None:
        """Keep at most one worker request in flight and one latest continuation."""
        if self.busy or not self.overlay.enabled or not self.target():
            return
        self.dirty = False
        self.busy = True
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
            }
        )

    @Slot(dict)
    def completed(self, result: dict[str, Any]) -> None:
        """Display only the latest generation; drain the latest coalesced request."""
        self.busy = False
        if result["token"] == self.token and self.overlay.enabled:
            self.overlay.display(result)
        if self.dirty:
            self.timer.start()
