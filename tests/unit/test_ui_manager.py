"""
Unit Tests for UIManager Dock Creation.

Tests the error handling and validation in dock creation.
"""

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QWidget
from unittest.mock import Mock, MagicMock

from src.app.ui_manager import UIManager


@pytest.fixture
def qapp():
    """Fixture to provide QApplication instance."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def main_window(qapp):
    """Fixture to provide a mock MainWindow."""
    window = QMainWindow()
    # Add required attributes that UIManager expects
    window.command_requested = Mock()
    window.worker = Mock()
    return window


@pytest.fixture
def ui_manager(main_window):
    """Fixture to provide UIManager instance."""
    return UIManager(main_window)


class TestDockCreation:
    """Tests for dock creation functionality."""

    def test_create_dock_with_valid_widget(self, ui_manager):
        """Test that dock creation succeeds with a valid widget."""
        widget = QLabel("Test Widget")
        dock = ui_manager._create_dock("Test Dock", "TestDockObject", widget)

        assert dock is not None
        assert dock.windowTitle() == "Test Dock"
        assert dock.objectName() == "TestDockObject"
        assert dock.widget() is widget

    def test_create_dock_with_none_widget(self, ui_manager):
        """Test that dock creation handles None widget gracefully."""
        dock = ui_manager._create_dock("Test Dock", "TestDockObject", None)

        assert dock is None

    def test_create_dock_with_invalid_widget_type(self, ui_manager):
        """Test that dock creation validates widget type."""
        invalid_widget = "Not a QWidget"
        dock = ui_manager._create_dock("Test Dock", "TestDockObject", invalid_widget)

        assert dock is None

    def test_create_dock_sets_minimum_sizes(self, ui_manager):
        """Test that dock creation sets appropriate minimum sizes."""
        widget = QLabel("Test Widget")
        dock = ui_manager._create_dock("Test Dock", "TestDockObject", widget)

        assert dock is not None
        assert dock.minimumWidth() == 250
        assert dock.minimumHeight() == 150

    def test_create_dock_sets_features(self, ui_manager):
        """Test that dock has correct features enabled."""
        from PySide6.QtWidgets import QDockWidget

        widget = QLabel("Test Widget")
        dock = ui_manager._create_dock("Test Dock", "TestDockObject", widget)

        assert dock is not None
        features = dock.features()
        assert features & QDockWidget.DockWidgetFeature.DockWidgetMovable
        assert features & QDockWidget.DockWidgetFeature.DockWidgetFloatable
        assert features & QDockWidget.DockWidgetFeature.DockWidgetClosable


class TestSetupDocks:
    """Tests for setup_docks functionality."""

    def test_setup_docks_with_all_widgets(self, ui_manager, main_window):
        """Test that setup_docks creates all docks when all widgets provided."""
        widgets = {
            "unified_list": QLabel("List"),
            "event_editor": QLabel("Event"),
            "entity_editor": QLabel("Entity"),
            "timeline": QLabel("Timeline"),
            "longform_editor": QLabel("Longform"),
            "map_widget": QLabel("Map"),
            "ai_search_panel": QLabel("AI Search"),
            "graph_widget": QLabel("Graph"),
        }

        ui_manager.setup_docks(widgets)

        # Check that all critical docks were created
        assert "list" in ui_manager.docks
        assert "event" in ui_manager.docks
        assert "entity" in ui_manager.docks
        assert "timeline" in ui_manager.docks

    def test_setup_docks_with_missing_critical_widget(self, ui_manager, main_window):
        """Test that setup_docks raises error when critical widget missing."""
        widgets = {
            "unified_list": QLabel("List"),
            "event_editor": QLabel("Event"),
            # Missing entity_editor (critical)
            "timeline": QLabel("Timeline"),
        }

        with pytest.raises(RuntimeError, match="Critical docks missing"):
            ui_manager.setup_docks(widgets)

    def test_setup_docks_with_none_widget(self, ui_manager, main_window):
        """Test that setup_docks handles None widgets gracefully."""
        widgets = {
            "unified_list": QLabel("List"),
            "event_editor": QLabel("Event"),
            "entity_editor": None,  # None widget
            "timeline": QLabel("Timeline"),
        }

        with pytest.raises(RuntimeError, match="Critical docks missing"):
            ui_manager.setup_docks(widgets)

    def test_setup_docks_with_optional_widgets_missing(self, ui_manager, main_window):
        """Test that setup_docks succeeds when only optional widgets missing."""
        widgets = {
            "unified_list": QLabel("List"),
            "event_editor": QLabel("Event"),
            "entity_editor": QLabel("Entity"),
            "timeline": QLabel("Timeline"),
            # Optional widgets not provided
        }

        ui_manager.setup_docks(widgets)

        # Check that critical docks were created
        assert "list" in ui_manager.docks
        assert "event" in ui_manager.docks
        assert "entity" in ui_manager.docks
        assert "timeline" in ui_manager.docks

        # Check that optional docks were not created
        assert "longform" not in ui_manager.docks
        assert "map" not in ui_manager.docks
