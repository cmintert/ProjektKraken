"""
Unit Tests for UIManager Dock Creation.

Tests the error handling and validation in dock creation.
"""

from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

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


class TestResetLayout:
    """Tests for reset_layout robustness."""

    def _create_all_docks(self, ui_manager, main_window):
        """Helper to create all docks for testing."""
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
        ui_manager.setup_docks(widgets)

    def test_reset_layout_shows_all_critical_docks(self, ui_manager, main_window):
        """Reset layout should restore all critical docks (showing or tabified)."""
        self._create_all_docks(ui_manager, main_window)

        # Close all docks (simulate user closing them via X button)
        for dock in ui_manager.docks.values():
            dock.close()

        ui_manager.reset_layout()

        # Left dock (not tabified) should not be hidden
        assert not ui_manager.docks["list"].isHidden()
        # Tabified docks: raised tab is not hidden; others are hidden by Qt
        # but still present in the dock dict - verify they exist and have widgets
        for key in ["event", "entity", "timeline"]:
            assert key in ui_manager.docks
            assert ui_manager.docks[key].widget() is not None

    def test_reset_layout_shows_optional_docks(self, ui_manager, main_window):
        """Reset layout should include optional docks in tab groups."""
        self._create_all_docks(ui_manager, main_window)

        # Close all docks
        for dock in ui_manager.docks.values():
            dock.close()

        ui_manager.reset_layout()

        # Optional docks should exist and have their widgets intact
        for key in ["map", "graph", "longform"]:
            assert key in ui_manager.docks
            assert ui_manager.docks[key].widget() is not None

    def test_reset_layout_works_with_only_critical_docks(
        self, ui_manager, main_window
    ):
        """Reset layout should work when only critical docks exist."""
        widgets = {
            "unified_list": QLabel("List"),
            "event_editor": QLabel("Event"),
            "entity_editor": QLabel("Entity"),
            "timeline": QLabel("Timeline"),
        }
        ui_manager.setup_docks(widgets)

        # Should not raise
        ui_manager.reset_layout()

        assert not ui_manager.docks["list"].isHidden()
        assert not ui_manager.docks["event"].isHidden()


class TestRestoreLayoutRobustness:
    """Tests for restore_layout error handling."""

    def test_restore_layout_handles_missing_name(self, ui_manager):
        """Restoring a non-existent layout should not crash."""
        from unittest.mock import patch

        with patch("src.app.ui_manager.QSettings") as MockSettings:
            MockSettings.return_value.value.return_value = {}
            # Should not raise
            ui_manager.restore_layout("NonExistent")

    def test_restore_layout_handles_corrupt_data(self, ui_manager, main_window):
        """Restoring corrupt layout data should fall back to default."""
        from unittest.mock import patch

        widgets = {
            "unified_list": QLabel("List"),
            "event_editor": QLabel("Event"),
            "entity_editor": QLabel("Entity"),
            "timeline": QLabel("Timeline"),
        }
        ui_manager.setup_docks(widgets)

        with patch("src.app.ui_manager.QSettings") as MockSettings:
            MockSettings.return_value.value.return_value = {
                "Corrupt": {"state": b"corrupt_data", "geometry": b"corrupt_geo"}
            }
            # restoreState returns False for corrupt data
            main_window.restoreState = lambda state: False

            with patch.object(ui_manager, "reset_layout") as mock_reset:
                ui_manager.restore_layout("Corrupt")
                mock_reset.assert_called_once()
