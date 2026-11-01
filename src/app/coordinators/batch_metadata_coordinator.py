"""Coordinate checked metadata intent, worker preview and command acknowledgement."""

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import QWidget

from src.commands.batch_metadata_command import BatchMetadataCommand
from src.core.batch_metadata import MetadataOperation, Target, normalize_targets
from src.core.command import CommandResult, parse_lore_mutation_effects
from src.gui.dialogs.batch_metadata_dialog import BatchMetadataDialog
from src.services.batch_metadata_worker import BatchMetadataWorker, DatabaseProvider


class BatchMetadataCoordinator(QObject):
    """Own the feature lifecycle with narrow callbacks and detached snapshots."""

    preview_requested = Signal(dict)

    def __init__(
        self,
        parent: QWidget,
        thread: QThread,
        database: DatabaseProvider,
        world: Callable[[], str],
        checked: Callable[[], list],
        drafts: Callable[[list[Target]], str],
        tags: Callable[[], list[str]],
        execute: Callable[[BatchMetadataCommand], None],
        refresh: Callable[[list], None],
        index: Callable[[str, str], None],
    ) -> None:
        """Bind preview delivery without taking ownership of database services."""
        super().__init__(parent)
        self._parent = parent
        self._world = world
        self._checked = checked
        self._drafts = drafts
        self._tags = tags
        self._execute = execute
        self._refresh = refresh
        self._index = index
        self._adapter = BatchMetadataWorker(database)
        self._adapter.moveToThread(thread)
        thread.finished.connect(self._adapter.deleteLater)
        self.preview_requested.connect(
            self._adapter.preview, Qt.ConnectionType.QueuedConnection
        )
        self._adapter.completed.connect(
            self._preview_ready, Qt.ConnectionType.QueuedConnection
        )
        self.dialog: BatchMetadataDialog | None = None
        self._targets: list[Target] = []
        self._world_id = ""
        self._job = ""
        self._command_id = ""
        self._preview: dict[str, Any] | None = None
        self._operation: dict[str, Any] = {}

    @Slot()
    def show(self) -> None:
        """Capture checked identities independently from inspected identity."""
        if self.dialog is not None:
            self.dialog.raise_()
            return
        try:
            self._targets = normalize_targets(self._checked())
        except ValueError:
            return
        self._world_id = self._world()
        self.dialog = BatchMetadataDialog(
            len(self._targets), self._tags(), self._parent
        )
        self.dialog.preview_requested.connect(self._request_preview)
        self.dialog.intent_changed.connect(self._invalidate)
        self.dialog.apply_requested.connect(self._apply)
        self.dialog.finished.connect(self._closed)
        self.dialog.open()
        if message := self._drafts(self._targets):
            self.dialog.show_error(message)

    def _invalidate(self) -> None:
        self._job = ""
        self._preview = None

    def _closed(self, _result: int) -> None:
        dialog, self.dialog = self.dialog, None
        self._invalidate()
        if dialog is not None:
            dialog.deleteLater()

    def _guard(self) -> bool:
        if self.dialog is None:
            return False
        message = self._drafts(self._targets)
        if self._world_id != self._world():
            message = "The world changed. Close Batch Edit and open it again."
        if message:
            self._invalidate()
            self.dialog.show_error(message)
            return False
        return True

    @Slot(dict)
    def _request_preview(self, operation: dict) -> None:
        if not self._guard() or self.dialog is None:
            return
        self._invalidate()
        try:
            self._operation = MetadataOperation.from_dict(operation).to_dict()
        except (ValueError, TypeError) as exc:
            self.dialog.show_error(str(exc))
            return
        self._job = str(uuid4())
        self.dialog.set_busy(True, "Reading saved metadata…")
        self.preview_requested.emit(
            {
                "job": self._job,
                "world": self._world_id,
                "targets": list(self._targets),
                "operation": self._operation,
            }
        )

    @Slot(dict)
    def _preview_ready(self, result: dict) -> None:
        if result["job"] != self._job or not self._guard():
            return
        assert self.dialog is not None
        if not result["success"]:
            self.dialog.show_error(result["error"])
            return
        self._preview = result["preview"]
        self.dialog.show_preview(result["preview"])

    @Slot()
    def _apply(self) -> None:
        if self._command_id or not self._guard() or not self._preview:
            return
        if not self._preview["changed"]:
            return
        command = BatchMetadataCommand(
            self._targets, self._operation, self._preview["rows"]
        )
        self._command_id = command.command_id
        assert self.dialog is not None
        self.dialog.set_busy(True, "Applying batch edit…", applying=True)
        self._execute(command)

    @Slot(object)
    def on_command_finished(self, result: CommandResult) -> None:
        """Refresh all changed objects and correlate the dialog acknowledgement."""
        if not result.command_name.endswith("BatchMetadataCommand"):
            return
        effects = parse_lore_mutation_effects(result.data.get("lore_effects"))
        if result.success and effects:
            self._refresh(effects)
            if result.command_name.startswith(("Undo_", "Redo_")):
                for effect in effects:
                    self._index(effect["object_type"], effect["object_id"])
        if result.data.get("command_id") != self._command_id:
            return
        self._command_id = ""
        if self.dialog is None:
            return
        if result.success:
            self.dialog.accept()
        else:
            self._invalidate()
            self.dialog.show_error(result.message)

    @Slot()
    def cancel(self) -> None:
        """Invalidate previews when the worker initializes or closes a world."""
        self._invalidate()
        if self.dialog is not None:
            self.dialog.set_busy(False)
            self.dialog.reject()
        self._command_id = ""
