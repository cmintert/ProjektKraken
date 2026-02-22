"""Regression tests for reset_layout dock collapse fix.

Verifies that reset_layout() properly positions ALL docks, including
bottom-area docks (timeline, map, graph) that were previously
forgotten and would collapse to zero height.
"""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

from src.app.ui_manager import UIManager

# Patch path for get_default_layout_path — imported lazily inside reset_layout
_LAYOUT_PATH_PATCH = "src.core.paths.get_default_layout_path"


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def main_window(qapp):
    window = QMainWindow()
    window.resize(1280, 720)
    window.command_requested = MagicMock()
    window.worker = MagicMock()
    return window


@pytest.fixture
def ui_manager_with_docks(main_window):
    """UIManager with all docks pre-created via setup_docks."""
    um = UIManager(main_window)
    widgets = {
        "unified_list": QLabel("List"),
        "event_editor": QLabel("Event"),
        "entity_editor": QLabel("Entity"),
        "timeline": QLabel("Timeline"),
        "longform_editor": QLabel("Longform"),
        "map_widget": QLabel("Map"),
        "ai_search_panel": QLabel("AI Search"),
        "graph_widget": QLabel("Graph"),
        "history_panel": QLabel("History"),
    }
    um.setup_docks(widgets)
    return um


class TestResetLayoutPositionsAllDocks:
    """Verify reset_layout places every dock in the correct area."""

    @patch(_LAYOUT_PATH_PATCH, return_value="/nonexistent/path.json")
    def test_timeline_re_added_to_bottom(
        self, mock_path, ui_manager_with_docks, main_window
    ):
        """Timeline must be addDockWidget'd to bottom area."""
        ui_manager_with_docks.reset_layout()

        dock = ui_manager_with_docks.docks["timeline"]
        assert not dock.isHidden(), "Timeline dock should not be hidden"
        area = main_window.dockWidgetArea(dock)
        assert area == Qt.DockWidgetArea.BottomDockWidgetArea

    @patch(_LAYOUT_PATH_PATCH, return_value="/nonexistent/path.json")
    def test_map_re_added_to_bottom(
        self, mock_path, ui_manager_with_docks, main_window
    ):
        """Map dock must be addDockWidget'd to bottom area."""
        ui_manager_with_docks.reset_layout()

        dock = ui_manager_with_docks.docks["map"]
        assert not dock.isHidden(), "Map dock should not be hidden"
        area = main_window.dockWidgetArea(dock)
        assert area == Qt.DockWidgetArea.BottomDockWidgetArea

    @patch(_LAYOUT_PATH_PATCH, return_value="/nonexistent/path.json")
    def test_graph_re_added_to_bottom(
        self, mock_path, ui_manager_with_docks, main_window
    ):
        """Graph dock must be addDockWidget'd to bottom area."""
        ui_manager_with_docks.reset_layout()

        dock = ui_manager_with_docks.docks["graph"]
        assert not dock.isHidden(), "Graph dock should not be hidden"
        area = main_window.dockWidgetArea(dock)
        assert area == Qt.DockWidgetArea.BottomDockWidgetArea

    @patch(_LAYOUT_PATH_PATCH, return_value="/nonexistent/path.json")
    def test_longform_re_added_to_right(
        self, mock_path, ui_manager_with_docks, main_window
    ):
        """Longform dock must be re-added to right area."""
        ui_manager_with_docks.reset_layout()

        dock = ui_manager_with_docks.docks["longform"]
        assert not dock.isHidden(), "Longform dock should not be hidden"
        area = main_window.dockWidgetArea(dock)
        assert area == Qt.DockWidgetArea.RightDockWidgetArea

    @patch(_LAYOUT_PATH_PATCH, return_value="/nonexistent/path.json")
    def test_history_re_added_to_right(
        self, mock_path, ui_manager_with_docks, main_window
    ):
        """History dock must be re-added to right area."""
        ui_manager_with_docks.reset_layout()

        dock = ui_manager_with_docks.docks["history"]
        assert not dock.isHidden(), "History dock should not be hidden"
        area = main_window.dockWidgetArea(dock)
        assert area == Qt.DockWidgetArea.RightDockWidgetArea

    @patch(_LAYOUT_PATH_PATCH, return_value="/nonexistent/path.json")
    def test_ai_search_re_added_to_right(
        self, mock_path, ui_manager_with_docks, main_window
    ):
        """AI Search dock must be re-added to right area."""
        ui_manager_with_docks.reset_layout()

        dock = ui_manager_with_docks.docks["ai_search"]
        assert not dock.isHidden(), "AI Search dock should not be hidden"
        area = main_window.dockWidgetArea(dock)
        assert area == Qt.DockWidgetArea.RightDockWidgetArea

    @patch(_LAYOUT_PATH_PATCH, return_value="/nonexistent/path.json")
    def test_all_docks_not_hidden_after_reset(
        self, mock_path, ui_manager_with_docks
    ):
        """No dock should be explicitly hidden after reset_layout."""
        ui_manager_with_docks.reset_layout()

        for key, dock in ui_manager_with_docks.docks.items():
            assert not dock.isHidden(), (
                f"Dock '{key}' should not be hidden after reset"
            )


class TestEnsureBottomDockHeight:
    """Verify _ensure_bottom_dock_height calls resizeDocks."""

    @patch(_LAYOUT_PATH_PATCH, return_value="/nonexistent/path.json")
    def test_resize_docks_called(
        self, mock_path, ui_manager_with_docks, main_window
    ):
        """resizeDocks must be called to allocate bottom area height."""
        with patch.object(main_window, "resizeDocks") as mock_resize:
            ui_manager_with_docks.reset_layout()
            mock_resize.assert_called_once()

            # Verify it's called with vertical orientation
            args = mock_resize.call_args
            assert args[0][2] == Qt.Orientation.Vertical

    def test_ensure_bottom_dock_height_skips_hidden(
        self, ui_manager_with_docks, main_window
    ):
        """Should not call resizeDocks if all bottom docks are hidden."""
        for key in ("timeline", "map", "graph"):
            if key in ui_manager_with_docks.docks:
                ui_manager_with_docks.docks[key].hide()

        with patch.object(main_window, "resizeDocks") as mock_resize:
            ui_manager_with_docks._ensure_bottom_dock_height()
            mock_resize.assert_not_called()
