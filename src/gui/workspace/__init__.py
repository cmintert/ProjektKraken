"""Fixed-zone workspace shell for Projekt Kraken."""

from src.gui.workspace.layout_state import (
    DEFAULT_WORKSPACE_LAYOUT,
    WORKSPACE_LAYOUT_VERSION,
    normalize_layout,
)
from src.gui.workspace.pane_container import PaneContainer
from src.gui.workspace.panel_registry import PanelDefinition, PanelRegistry
from src.gui.workspace.workspace_shell import WorkspaceShell

__all__ = [
    "DEFAULT_WORKSPACE_LAYOUT",
    "WORKSPACE_LAYOUT_VERSION",
    "PaneContainer",
    "PanelDefinition",
    "PanelRegistry",
    "WorkspaceShell",
    "normalize_layout",
]
