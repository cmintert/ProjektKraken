"""Layout-only workspace orchestration with explicit local persistence."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from copy import deepcopy
from typing import Any

import shiboken6
from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox, QWidget

from src.core.workspaces import BUILTIN_IDS, workspace_default
from src.gui.workspace.workspace_shell import WorkspaceShell
from src.services.workspace_store import WorkspaceStore


class WorkspaceCoordinator(QObject):
    """Switch arrangements without navigating objects or mutating world content."""

    def __init__(
        self,
        shell: WorkspaceShell,
        store: WorkspaceStore,
        selected_type: Callable[[], str | None],
        exit_focus: Callable[[], None],
        parent: QWidget,
    ) -> None:
        """Bind only layout, selection inspection and temporary presentation endpoints."""
        super().__init__(parent)
        self.shell = shell
        self.store = store
        self._selected_type = selected_type
        self._exit_focus = exit_focus
        self._dialog_parent = parent
        self._last_inspector = "entity"
        self._applying = False
        self._ready = False
        self.collection: dict[str, Any] = {}
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self.flush)
        rail = shell.activity_bar
        rail.configure_workspaces()
        rail.workspace_requested.connect(self.activate)
        rail.management_requested.connect(self.manage)
        rail.expanded_changed.connect(self._expanded_changed)
        shell.layout_changed.connect(self._layout_changed)
        shell.panel_activated.connect(self._remember_inspector)

    @property
    def active_id(self) -> str:
        """Return the current stable workspace ID."""
        return str(self.collection.get("active", "overview"))

    def restore(self) -> None:
        """Restore after startup composition, before ordinary view refreshes."""
        self.collection = self.store.load()
        self._apply(self.active_id)
        self.shell.activity_bar.set_expanded(self.collection["expanded"])
        self._ready = True
        self.flush()

    def _inspector(self) -> str:
        selected = self._selected_type()
        return selected if selected in ("entity", "event") else self._last_inspector

    def _remember_inspector(self, identifier: str) -> None:
        if identifier in ("entity", "event"):
            self._last_inspector = identifier

    def activate(self, identifier: str) -> None:
        """Capture the outgoing layout and activate a distinct known destination."""
        if not self._ready or identifier == self.active_id:
            return
        if identifier not in self.collection["entries"]:
            return
        self.flush()
        self._exit_focus()
        self._apply(identifier)
        self.flush()

    def _apply(self, identifier: str) -> None:
        entry = self.collection["entries"][identifier]
        layout = entry["layout"]
        if layout is None:
            layout = workspace_default(identifier, self._inspector())
        origin = QApplication.focusWidget()
        self._applying = True
        try:
            normalized = self.shell.apply_layout(layout)
            self.collection["active"] = identifier
            entry["layout"] = normalized
        finally:
            self._applying = False
        self._refresh_menu()
        if origin is not None and shiboken6.isValid(origin) and origin.isVisible():
            origin.setFocus()

    def _refresh_menu(self) -> None:
        self.shell.activity_bar.set_entries(
            [
                (identifier, entry["name"])
                for identifier, entry in self.collection["entries"].items()
            ],
            self.active_id,
        )

    def _layout_changed(self) -> None:
        if self._ready and not self._applying:
            self._timer.start()

    def _expanded_changed(self, expanded: bool) -> None:
        if self.collection:
            self.collection["expanded"] = expanded
            self._refresh_menu()
            self._layout_changed()

    def flush(self) -> None:
        """Persist the settled active layout; safe before switching and shutdown."""
        self._timer.stop()
        if not self._ready or self._applying:
            return
        if self.shell.isVisible():
            self.collection["entries"][self.active_id]["layout"] = (
                self.shell.capture_layout()
            )
        self.store.save(self.collection)

    def save_as(self, name: str) -> str:
        """Create a custom workspace with an independent creation baseline."""
        name = self._validate_name(name)
        self.flush()
        identifier = "custom:" + str(uuid.uuid4())
        layout = self.shell.capture_layout()
        self.collection["entries"][identifier] = {
            "name": name,
            "layout": layout,
            "baseline": deepcopy(layout),
        }
        self.collection["active"] = identifier
        self._refresh_menu()
        self.flush()
        return identifier

    def _validate_name(self, name: str) -> str:
        name = name.strip()
        if not name:
            raise ValueError("Enter a workspace name.")
        if any(
            entry["name"].casefold() == name.casefold()
            for entry in self.collection["entries"].values()
        ):
            raise ValueError("A workspace with that name already exists.")
        return name

    def rename(self, name: str) -> None:
        """Rename only the active custom workspace."""
        if self.active_id in BUILTIN_IDS:
            return
        if name.strip() == self.collection["entries"][self.active_id]["name"]:
            return
        self.collection["entries"][self.active_id]["name"] = self._validate_name(name)
        self._refresh_menu()
        self.flush()

    def delete(self) -> None:
        """Delete the active custom entry, retaining all live panel contents."""
        identifier = self.active_id
        if identifier in BUILTIN_IDS:
            return
        self.activate("overview")
        del self.collection["entries"][identifier]
        self._refresh_menu()
        self.flush()

    def reset(self) -> None:
        """Reset only this workspace to its factory or custom creation layout."""
        self._exit_focus()
        entry = self.collection["entries"][self.active_id]
        entry["layout"] = (
            workspace_default(self.active_id, self._inspector())
            if self.active_id in BUILTIN_IDS
            else deepcopy(entry["baseline"])
        )
        self._apply(self.active_id)
        self.flush()

    def manage(self, operation: str) -> None:
        """Collect explicit naming/confirmation before a local management operation."""
        if operation in ("save", "rename"):
            initial = (
                self.collection["entries"][self.active_id]["name"]
                if operation == "rename"
                else ""
            )
            name, accepted = QInputDialog.getText(
                self._dialog_parent, "Workspace name", "Name:", text=initial
            )
            if accepted:
                try:
                    self.save_as(name) if operation == "save" else self.rename(name)
                except ValueError as exc:
                    QMessageBox.information(
                        self._dialog_parent, "Workspace name", str(exc)
                    )
        elif operation in ("delete", "reset"):
            name = self.collection["entries"][self.active_id]["name"]
            verb = (
                "Delete workspace"
                if operation == "delete"
                else "Reset workspace layout"
            )
            answer = QMessageBox.question(
                self._dialog_parent,
                verb,
                f"{verb} ‘{name}’?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.delete() if operation == "delete" else self.reset()
        self.shell.activity_bar.restore_menu_focus()
