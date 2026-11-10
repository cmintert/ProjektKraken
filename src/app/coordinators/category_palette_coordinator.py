"""World-session guards for asynchronously refreshed Explorer type colors."""

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot

from src.services.category_palette_task import CategoryPaletteTask, DatabaseProvider


class CategoryPaletteCoordinator(QObject):
    """Coalesce refreshes; publish snapshots only from the current world session."""

    requested = Signal(dict)

    def __init__(
        self,
        thread: QThread,
        database: DatabaseProvider,
        identity: Callable[[], str],
        publish: Callable[[dict[str, int]], None],
        parent: QObject | None = None,
    ) -> None:
        """Compose queued delivery without accessing SQLite from the GUI."""
        super().__init__(parent)
        self._identity = identity
        self._publish = publish
        self._generation = 0
        self._sequence = 0
        self._closed = False
        self._last: dict[str, int] | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._request)
        self._task = CategoryPaletteTask(database)
        self._task.moveToThread(thread)
        thread.finished.connect(self._task.deleteLater)
        self.requested.connect(self._task.run, Qt.ConnectionType.QueuedConnection)
        self._task.finished.connect(self._receive, Qt.ConnectionType.QueuedConnection)

    @Slot()
    def refresh(self) -> None:
        """Schedule once after a burst of confirmed loads or mutations."""
        if not self._closed:
            self._timer.start(0)

    @Slot(bool)
    def initialized(self, success: bool) -> None:
        """Clear previous-world colors, including same-path reopen sessions."""
        if self._closed:
            return
        self._generation += 1
        self._last = None
        self._publish({})
        self._timer.stop()
        if success:
            self.refresh()

    @Slot()
    def _request(self) -> None:
        if self._closed:
            return
        self._sequence += 1
        self.requested.emit(
            {
                "database": self._identity(),
                "generation": self._generation,
                "sequence": self._sequence,
            }
        )

    @Slot(dict)
    def _receive(self, result: dict[str, Any]) -> None:
        if (
            self._closed
            or result["database"] != self._identity()
            or result["generation"] != self._generation
            or result["sequence"] != self._sequence
            or "error" in result
        ):
            return
        assignments = result["assignments"]
        if assignments != self._last:
            self._last = dict(assignments)
            self._publish(dict(assignments))

    @Slot()
    def shutdown(self) -> None:
        """Reject late results without waiting on the shared worker."""
        self._closed = True
        self._timer.stop()
