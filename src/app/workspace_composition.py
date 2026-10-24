"""Compose activity workspaces against narrow existing window endpoints."""

from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QWidget

from src.app.coordinators.workspace_coordinator import WorkspaceCoordinator
from src.core.settings import WINDOW_SETTINGS_APP, WINDOW_SETTINGS_KEY
from src.gui.workspace.workspace_shell import WorkspaceShell
from src.services.workspace_store import WorkspaceStore


def compose_workspaces(
    shell: WorkspaceShell,
    parent: QWidget,
    focus_controller: object,
    navigation: object,
) -> WorkspaceCoordinator:
    """Avoid retaining the application facade in the workspace feature."""

    def selected_type() -> str | None:
        value = getattr(navigation, "selected_type", None)
        return value if isinstance(value, str) else None

    def exit_focus() -> None:
        if getattr(focus_controller, "active", None) is not None:
            exit_method = getattr(focus_controller, "exit")
            exit_method(restore_focus=False)

    return WorkspaceCoordinator(
        shell,
        WorkspaceStore(QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)),
        selected_type,
        exit_focus,
        parent,
    )
