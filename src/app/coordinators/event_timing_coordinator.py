"""Cancellable timing preparation and reviewed application through existing commands."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import QMessageBox, QProgressDialog, QWidget

from src.commands.base_command import BaseCommand, CommandResult
from src.commands.event_timing_commands import ApplyEventTimingPlanCommand
from src.commands.event_timing_intents import request_for_command, timing_intent
from src.gui.dialogs.event_timing_review_dialog import EventTimingReviewDialog
from src.services.event_timing.planning import TimingChangePlan
from src.services.event_timing.worker import (
    DatabaseProvider,
    EventTimingCalculation,
    EventTimingDatabaseAdapter,
)


class EventTimingCoordinator(QObject):
    """Own feature jobs and dialogs without owning the application or its database."""

    requested = Signal(str)
    failed = Signal(object)
    resolution_prepared = Signal(str)

    def __init__(
        self,
        parent: QWidget,
        db_thread: QThread,
        database: DatabaseProvider,
        world: Callable[[], str],
        execute: Callable[[BaseCommand], None],
    ) -> None:
        """Compose narrow thread, context, presentation and command dependencies."""
        super().__init__(parent)
        self._parent = parent
        self._world = world
        self._execute = execute
        self._adapter = EventTimingDatabaseAdapter(database)
        self._adapter.moveToThread(db_thread)
        db_thread.finished.connect(self._adapter.deleteLater)
        self.requested.connect(self._adapter.run, Qt.ConnectionType.QueuedConnection)
        self._adapter.completed.connect(
            self._database_result, Qt.ConnectionType.QueuedConnection
        )
        self._job = ""
        self._command: BaseCommand | None = None
        self._calculation: EventTimingCalculation | None = None
        self._threads: list[EventTimingCalculation] = []
        self._progress: QProgressDialog | None = None
        self._review_dialog: EventTimingReviewDialog | None = None
        self._world_id = ""

    def intercept(self, command: BaseCommand) -> bool:
        """Defer only timing intents; already prepared wrappers pass through."""
        if isinstance(command, ApplyEventTimingPlanCommand) or not timing_intent(
            command
        ):
            return False
        if self._command is not None:
            self._fail_command(
                command, "Another timing change is still being calculated or reviewed."
            )
            return True
        self._job = str(uuid4())
        self._world_id = self._world()
        self._command = command
        self._progress = QProgressDialog(
            "Calculating Event timing…", "Cancel", 0, 0, self._parent
        )
        self._progress.setWindowTitle("Check Event timing")
        self._progress.setWindowModality(Qt.WindowModality.NonModal)
        self._progress.setMinimumDuration(1000)
        self._progress.canceled.connect(self.cancel)
        self._send("capture")
        return True

    def _send(self, operation: str, **data: Any) -> None:
        self.requested.emit(
            json.dumps(
                {
                    "operation": operation,
                    "job": self._job,
                    "world_id": self._world_id,
                    **data,
                }
            )
        )

    @Slot(str)
    def _database_result(self, payload: str) -> None:
        result = json.loads(payload)
        if result["job"] != self._job or self._world() != self._world_id:
            return
        if not result["success"]:
            self._finish(result["error"])
            return
        if result["operation"] == "capture":
            self._start_calculation(result["snapshot"])
        else:
            command = self._command
            if command is None:
                return
            wrapped = ApplyEventTimingPlanCommand(
                command, result["plan_id"], result["fingerprint"]
            )
            wrapped.command_id = command.command_id
            self._reset()
            self._execute(wrapped)

    def _start_calculation(self, snapshot: dict[str, Any]) -> None:
        if self._command is None:
            return
        try:
            request = request_for_command(self._command, snapshot)
            calculation = EventTimingCalculation(self._job, snapshot, request, self)
        except (ValueError, KeyError, StopIteration, TypeError) as exc:
            self._finish(str(exc))
            return
        self._calculation = calculation
        self._threads.append(calculation)
        calculation.completed.connect(
            self._calculated, Qt.ConnectionType.QueuedConnection
        )
        calculation.finished.connect(lambda: self._retire(calculation))
        calculation.start()

    def _retire(self, calculation: EventTimingCalculation) -> None:
        if calculation in self._threads:
            self._threads.remove(calculation)
        calculation.deleteLater()

    @Slot(str)
    def _calculated(self, payload: str) -> None:
        result = json.loads(payload)
        if result["job"] != self._job or self._world() != self._world_id:
            return
        if not result["success"]:
            self._finish(
                result.get("error", "Timing edit cancelled."),
                show=not result.get("cancelled", False),
            )
            return
        plan = TimingChangePlan.from_dict(result["plan"])
        if plan.resolved_world is not None:
            self.resolution_prepared.emit(json.dumps(plan.resolved_world))
        self._close_progress()
        if plan.errors:
            self._finish("\n".join(plan.errors))
            return
        if plan.needs_review and not self._review(plan):
            self._finish("Timing changes were not applied.", show=False)
            return
        if result["job"] != self._job or self._world() != self._world_id:
            return
        self._send("register", plan=plan.to_dict())

    def _review(self, plan: TimingChangePlan) -> bool:
        dialog = EventTimingReviewDialog(plan.consequences, self._parent)
        self._review_dialog = dialog
        try:
            return dialog.exec() == EventTimingReviewDialog.DialogCode.Accepted
        finally:
            self._review_dialog = None
            dialog.deleteLater()

    def _fail_command(
        self, command: BaseCommand, message: str, *, cancelled: bool = False
    ) -> None:
        self.failed.emit(
            CommandResult(
                success=False,
                message=message,
                command_name=type(command).__name__,
                data={"command_id": command.command_id, "cancelled": cancelled},
            )
        )

    def _finish(self, message: str, *, show: bool = True) -> None:
        command = self._command
        self._reset()
        if command is not None:
            self._fail_command(command, message, cancelled=not show)
        if show:
            QMessageBox.warning(self._parent, "Timing changes not applied", message)

    def _reset(self) -> None:
        self._job = ""
        self._command = None
        self._calculation = None
        if self._review_dialog is not None:
            self._review_dialog.reject()
        self._close_progress()

    def _close_progress(self) -> None:
        """Stop delayed progress display before opening any result or review."""
        if self._progress is not None:
            progress = self._progress
            self._progress = None
            progress.canceled.disconnect(self.cancel)
            progress.reset()
            progress.deleteLater()

    @Slot()
    def cancel(self) -> None:
        """Cancel the current job without discarding its author's draft."""
        if self._job:
            self._adapter.cancel_job(self._job)
        if self._calculation is not None:
            self._calculation.cancelled.set()
        self._finish("Timing edit cancelled.", show=False)

    @Slot()
    def shutdown(self) -> None:
        """Invalidate work and join cooperatively before QObject destruction."""
        for thread in self._threads:
            thread.cancelled.set()
        for thread in self._threads:
            thread.wait()
        self._reset()
