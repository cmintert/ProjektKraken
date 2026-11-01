"""Debounced, cancellable timeline preview calculations and reviewed commits."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Qt, QTimer

from src.commands.base_command import BaseCommand
from src.commands.timeline_move_command import TimelineMoveCommand
from src.gui.widgets.timeline.movement import TimelineMovementPresenter
from src.services.event_timing.planning import TimingChangeRequest
from src.services.event_timing.worker import EventTimingCalculation


class TimelineMovementCoordinator(QObject):
    """Own preview scheduling; never access a database or mutate scene objects."""

    def __init__(
        self,
        presenter: TimelineMovementPresenter,
        submit: Callable[[BaseCommand], None],
        parent: QObject,
        world: Callable[[], str] = lambda: "",
    ) -> None:
        """Bind narrow presentation signals to existing command submission."""
        super().__init__(parent)
        self.presenter = presenter
        self.submit = submit
        self.world = world
        self.drag_world = ""
        self.pending: dict[str, Any] | None = None
        self.threads: list[EventTimingCalculation] = []
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(60)
        self.timer.timeout.connect(self._calculate)
        presenter.preview_requested.connect(self.request)
        presenter.move_requested.connect(self.commit)
        presenter.cancelled.connect(self.cancel)
        presenter.started.connect(self._started)

    def _started(self) -> None:
        self.drag_world = self.world()

    def request(self, payload: dict[str, Any]) -> None:
        """Coalesce pointer motion; obsolete work is cooperatively cancelled."""
        self.cancel()
        self.pending = payload
        self.timer.start()

    def _calculate(self) -> None:
        if self.pending is None:
            return
        payload = self.pending
        worker = EventTimingCalculation(
            str(payload["sequence"]),
            payload["snapshot"],
            TimingChangeRequest(movement=payload["intent"], world_id="preview"),
            self,
        )
        self.threads.append(worker)
        worker.completed.connect(
            lambda result: self._present(result, payload),
            Qt.ConnectionType.QueuedConnection,
        )
        worker.finished.connect(lambda: self._retire(worker))
        worker.start()

    def _present(self, result: str, payload: dict[str, Any]) -> None:
        import json

        if self.drag_world != self.world():
            self.presenter.cancel()
            return
        data = json.loads(result)
        plan = data.get("plan", {})
        errors = plan.get("errors", [])
        caption = "\n".join(
            f"{item['name']}: {item['after_text']}"
            for item in plan.get("consequences", [])
            if item["kind"] == "event"
        )
        self.presenter.present(
            {
                "session": payload["session"],
                "sequence": payload["sequence"],
                "updated": plan.get("updated", {}) if not errors else {},
                "caption": caption,
                "error": "\n".join(errors) or data.get("error", ""),
            }
        )

    def _retire(self, worker: EventTimingCalculation) -> None:
        self.threads.remove(worker)
        worker.deleteLater()

    def commit(self, intent: dict[str, Any]) -> None:
        """Use the ordinary command coordinator and timing review interception."""
        if self.drag_world == self.world():
            self.submit(TimelineMoveCommand({**intent, "world_id": self.drag_world}))

    def cancel(self) -> None:
        """Invalidate queued preview work without waiting on the GUI thread."""
        self.timer.stop()
        self.pending = None
        for worker in self.threads:
            worker.cancelled.set()

    def shutdown(self) -> None:
        """Join workers before QObject destruction."""
        self.cancel()
        for worker in self.threads:
            worker.wait()
