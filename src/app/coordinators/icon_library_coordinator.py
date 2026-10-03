"""Coordinate icon library intents, worker snapshots and open editor references."""

from __future__ import annotations

import weakref
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Slot
from shiboken6 import isValid

from src.commands.base_command import BaseCommand, CommandResult
from src.commands.icon_library_commands import IconLibraryCommand


class IconLibraryCoordinator(QObject):
    """Own library state with narrow command, world and refresh dependencies."""

    def __init__(
        self,
        submit: Callable[[BaseCommand], None],
        world_context: Callable[[], tuple[str, str]],
        refresh: Callable[[dict[str, Any]], None],
        parent: QObject | None = None,
    ) -> None:
        """Initialize dependencies without retaining an application facade."""
        super().__init__(parent)
        self._submit = submit
        self._world_context = world_context
        self._refresh = refresh
        self._snapshot: dict[str, Any] = {"metadata": {}, "icons": []}
        self._world: tuple[str, str] = ("", "")
        self._pickers: list[weakref.ReferenceType[Any]] = []
        self._drafts: list[weakref.ReferenceType[Any]] = []
        self._pending: dict[str, weakref.ReferenceType[Any] | None] = {}

    def _context(self) -> tuple[str, str]:
        world_id, root = self._world_context()
        context = (world_id, str(Path(root).resolve()))
        if context != self._world:
            self._world = context
            self._snapshot = {"metadata": {}, "icons": []}
            self._pickers.clear()
            self._drafts.clear()
            self._pending.clear()
        return context

    @Slot(object)
    def attach_picker(self, picker: Any) -> None:
        """Connect UI intent and request fresh worker-owned metadata."""
        context = self._context()
        reference = weakref.ref(picker)
        self._pickers.append(reference)
        picker.library_requested.connect(
            lambda intent, ref=reference: self._request(intent, ref, context)
        )
        picker.set_library_snapshot(self._snapshot)
        picker.set_request_pending(True)
        self._request({"operation": "load"}, reference)

    def show_manager(self, parent: Any) -> None:
        """Open library management independently of any marker or graph selection."""
        from src.gui.dialogs.icon_picker_dialog import IconPickerDialog

        _, root = self._context()
        dialog = IconPickerDialog(parent, world_root=root, manage_only=True)
        self.attach_picker(dialog)
        dialog.exec()
        dialog.deleteLater()

    @Slot(object)
    def attach_draft(self, editor: Any) -> None:
        """Protect unsaved Visual Lexicon references while an editor is open."""
        self._context()
        self._drafts.append(weakref.ref(editor))

    def protected_references(self) -> dict[str, list[str]]:
        """Snapshot open editor references on the Qt main thread."""
        result: dict[str, list[str]] = {}
        for reference in self._drafts + self._pickers:
            widget = reference()
            if widget is None or not isValid(widget) or not widget.isVisible():
                continue
            for icon_id, uses in widget.icon_references().items():
                result.setdefault(icon_id, []).extend(uses)
        return result

    @Slot(object)
    def prepare_command(self, command: BaseCommand) -> None:
        """Refresh draft protection immediately before execute, undo or redo."""
        if isinstance(command, IconLibraryCommand):
            world_id, root = self._context()
            if command.before is not None and command.world_id == world_id:
                command.world_root = root
            command.protected = self.protected_references()
            self._pending.setdefault(command.command_id, None)
            self._set_pickers_pending(True)

    def _set_pickers_pending(self, pending: bool) -> None:
        for reference in self._pickers:
            picker = reference()
            if picker is not None and isValid(picker):
                picker.set_request_pending(pending)

    def _request(
        self,
        intent: dict[str, Any],
        owner: weakref.ReferenceType[Any] | None,
        expected_world: tuple[str, str] | None = None,
    ) -> None:
        world_id, root = self._context()
        if expected_world is not None and expected_world != (world_id, root):
            picker = owner() if owner is not None else None
            if picker is not None and isValid(picker):
                picker.finish_library_request(
                    False, "The active world changed. Reopen the icon picker.", {}
                )
            return
        command = IconLibraryCommand(
            root,
            world_id,
            str(intent["operation"]),
            icon_id=str(intent.get("icon_id", "")),
            source_paths=intent.get("source_paths"),
            changes=intent.get("changes"),
        )
        self._pending[command.command_id] = owner
        self.prepare_command(command)
        self._submit(command)

    @Slot(object)
    def on_command_finished(self, result: CommandResult) -> None:
        """Apply current-world snapshots without touching destroyed dialogs."""
        if not result.command_name.endswith("IconLibraryCommand"):
            return
        context = self._context()
        command_id = str(result.data.get("command_id", ""))
        owner = self._pending.pop(command_id, None)
        if result.data.get("world_id") not in {None, context[0]}:
            return
        if result.success:
            world = (
                str(result.data.get("world_id", "")),
                str(Path(str(result.data.get("world_root", ""))).resolve()),
            )
            if world != context:
                return
            snapshot = result.data.get("icon_library")
            if not isinstance(snapshot, dict):
                return
            self._snapshot = snapshot
            for reference in self._pickers:
                picker = reference()
                if picker is not None and isValid(picker):
                    picker.set_library_snapshot(snapshot)
            self._refresh(dict(result.data))
        if owner is not None:
            picker = owner()
            if picker is not None and isValid(picker):
                picker.set_request_pending(False)
                if picker.isVisible():
                    picker.finish_library_request(
                        result.success, result.message, result.data
                    )
        self._set_pickers_pending(bool(self._pending))

    @Slot(bool)
    def on_initialized(self, success: bool) -> None:
        """Load metadata when a world is ready for reads."""
        if success:
            self._request({"operation": "load"}, None)
