"""Drain database work without blocking the GUI or terminating a live thread."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

from PySide6.QtCore import (
    QByteArray,
    QObject,
    QSettings,
    Qt,
    QThread,
    QTimer,
    Signal,
    Slot,
)

from src.app.constants import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY

if TYPE_CHECKING:
    from src.services.worker import DatabaseWorker

logger = logging.getLogger(__name__)


class ShutdownParticipant(Protocol):
    """A feature that can invalidate its background work on approved close."""

    def shutdown(self) -> None:
        """Stop submitting work and reject late results."""
        ...


class CommandGate(Protocol):
    """The command admission switch used once drafts have been resolved."""

    mutations_suspended: bool


class ReloadTimers(Protocol):
    """The two database reload timers stopped before cleanup."""

    def stop_graph_reload_timer(self) -> None:
        """Stop deferred graph reloads."""
        ...

    def stop_semantic_debounce_timer(self) -> None:
        """Stop deferred semantic reloads."""
        ...


class BackupTimer(Protocol):
    """The periodic backup timer stopped before cleanup."""

    def stop_auto_backup(self) -> None:
        """Stop scheduled backups."""
        ...


def stop_authoring(
    commands: CommandGate | None,
    worker_manager: ShutdownParticipant,
    *features: ShutdownParticipant | None,
) -> None:
    """Quiesce authoring even when close precedes deferred initialization."""
    worker_manager.shutdown()
    if commands is not None:
        commands.mutations_suspended = True
    for feature in features:
        if feature is not None:
            feature.shutdown()


def save_shutdown_state(
    geometry: QByteArray,
    save_workspace: Callable[[], None],
    save_timeline: Callable[[], None],
) -> None:
    """Persist outer geometry separately from workspace and timeline snapshots."""
    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    settings.setValue("geometry", geometry)
    save_workspace()
    save_timeline()


def stop_background_work(
    longform: ShutdownParticipant,
    data: ReloadTimers,
    backup: BackupTimer | None,
    search: ShutdownParticipant,
    analysis: ShutdownParticipant,
) -> None:
    """Quiesce the existing background producers before database cleanup."""
    longform.shutdown()
    data.stop_graph_reload_timer()
    data.stop_semantic_debounce_timer()
    if backup is not None:
        backup.stop_auto_backup()
    search.shutdown()
    analysis.shutdown()


class ShutdownCoordinator(QObject):
    """Close the database on its owner thread, then confirm the thread has exited."""

    cleanup_requested = Signal()
    finished = Signal(dict)
    waiting = Signal()

    def __init__(
        self, worker: DatabaseWorker, thread: QThread, parent: QObject
    ) -> None:
        """Bind only the worker lifecycle; draft decisions remain with the caller."""
        super().__init__(parent)
        self._thread = thread
        self.pending = False
        self.complete = False
        self._result: dict | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._on_waiting)
        self.cleanup_requested.connect(
            worker.cleanup, Qt.ConnectionType.QueuedConnection
        )
        worker.cleanup_finished.connect(
            self._on_cleanup, Qt.ConnectionType.QueuedConnection
        )
        thread.finished.connect(self._on_stopped, Qt.ConnectionType.QueuedConnection)

    def start(self) -> None:
        """Queue cleanup behind submitted work, allowing the GUI to keep running."""
        if self.pending or self.complete:
            return
        self.pending = True
        if not self._thread.isRunning():
            # A thread that was never started owns no database connection.
            # A previously finished worker still requires cleanup confirmation.
            if not self._thread.isFinished():
                self._result = {"success": True, "error": ""}
            self._on_stopped()
            return
        self._timer.start()
        self.cleanup_requested.emit()

    @Slot()
    def _on_waiting(self) -> None:
        logger.warning("Still waiting for database shutdown; keeping worker alive")
        self.waiting.emit()

    @Slot(dict)
    def _on_cleanup(self, result: dict) -> None:
        if not self.pending or self._result is not None:
            return
        self._result = dict(result)
        self._thread.quit()

    @Slot()
    def _on_stopped(self) -> None:
        if not self.pending:
            return
        # QThread.finished precedes thread-local destructors. Poll rather than
        # blocking the GUI while they finish, before native objects may be freed.
        if not self._thread.wait(0):
            QTimer.singleShot(10, self._on_stopped)
            return
        self._timer.stop()
        self.pending = False
        self.complete = True
        result = self._result or {
            "success": False,
            "error": "Database worker stopped without confirming cleanup.",
        }
        if not result.get("success"):
            logger.error("Database shutdown failed: %s", result.get("error"))
        self.finished.emit(result)
