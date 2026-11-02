"""Bounded latest-target scheduling on one persistent preview thread."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot

from src.commands.base_command import BaseCommand
from src.commands.timeline_move_command import TimelineMoveCommand
from src.gui.widgets.timeline.movement import TimelineMovementPresenter
from src.services.event_timing.preview_worker import MovementPreviewWorker


class TimelineMovementCoordinator(QObject):
    """Throttle requests without starving continuous motion or building a backlog."""

    initialize_requested = Signal(str)
    calculation_requested = Signal(str)

    def __init__(
        self,
        presenter: TimelineMovementPresenter,
        submit: Callable[[BaseCommand], None],
        parent: QObject,
        world: Callable[[], str] = lambda: "",
    ) -> None:
        """Bind narrow presentation signals to a feature-owned persistent worker."""
        super().__init__(parent)
        self.presenter, self.submit, self.world = presenter, submit, world
        self.drag_world = ""
        self.pending: dict[str, Any] | None = None
        self.busy = False
        self.session = -1
        self._closed = False
        self.preview_thread = QThread(self)
        self.worker = MovementPreviewWorker()
        self.worker.moveToThread(self.preview_thread)
        self.preview_thread.finished.connect(self.worker.deleteLater)
        self.initialize_requested.connect(
            self.worker.initialize, Qt.ConnectionType.QueuedConnection
        )
        self.calculation_requested.connect(
            self.worker.calculate, Qt.ConnectionType.QueuedConnection
        )
        self.worker.completed.connect(self._present, Qt.ConnectionType.QueuedConnection)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._calculate)
        presenter.preview_requested.connect(self.request)
        presenter.move_requested.connect(self.commit)
        presenter.cancelled.connect(self.cancel)
        presenter.started.connect(self._started)
        parent.destroyed.connect(self.shutdown)

    def _started(self) -> None:
        if self._closed or self.presenter.intent is None:
            return
        if not self.preview_thread.isRunning():
            self.preview_thread.start()
        self.drag_world = self.world()
        self.session = self.presenter.session
        self.initialize_requested.emit(
            json.dumps(
                {
                    **self.presenter.snapshot,
                    **self.presenter.intent,
                    "world_id": self.drag_world,
                    "session": self.session,
                }
            )
        )

    def request(self, payload: dict[str, Any]) -> None:
        """Keep one pending target; incoming motion never restarts the timer."""
        if self._closed:
            return
        self.pending = {**payload, "world_id": self.drag_world}
        if not self.busy and not self.timer.isActive():
            self.timer.start()

    def _calculate(self) -> None:
        if self.pending is None or self.busy:
            return
        payload, self.pending = self.pending, None
        self.busy = True
        self.calculation_requested.emit(json.dumps(payload))

    @Slot(str)
    def _present(self, payload: str) -> None:
        self.busy = False
        result = json.loads(payload)
        if self.drag_world != self.world():
            self.presenter.cancel()
        elif not result.get("cancelled"):
            self.presenter.present(result)
        if self.pending is not None and not self.timer.isActive():
            self.timer.start()

    def commit(self, intent: dict[str, Any]) -> None:
        """Preview results never authorize writes; use full-world command review."""
        if self.drag_world == self.world():
            self.submit(TimelineMoveCommand({**intent, "world_id": self.drag_world}))

    def cancel(self) -> None:
        """Cancel the session, not each useful in-flight calculation."""
        self.timer.stop()
        self.pending = None
        self.worker.cancel_session(self.session)

    def shutdown(self) -> None:
        """Cooperatively join the persistent thread before QObject destruction."""
        if self._closed:
            return
        self._closed = True
        self.cancel()
        self.preview_thread.quit()
        self.preview_thread.wait()
