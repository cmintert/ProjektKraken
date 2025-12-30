from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QSettings

from src.app.constants import (
    SETTINGS_LAYOUTS_KEY,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
)
from src.app.ui_manager import UIManager


@pytest.fixture
def mock_main_window():
    mw = MagicMock()
    mw.saveState.return_value = b"mock_state"
    mw.saveGeometry.return_value = b"mock_geometry"
    return mw


@pytest.fixture
def ui_manager(mock_main_window):
    return UIManager(mock_main_window)


@pytest.fixture
def clean_settings():
    """Ensure settings are clean before and after tests."""
    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    settings.remove(SETTINGS_LAYOUTS_KEY)
    yield
    settings.remove(SETTINGS_LAYOUTS_KEY)


def test_save_layout_stores_data(ui_manager, mock_main_window, clean_settings):
    ui_manager.save_layout("Test Layout")

    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    layouts = settings.value(SETTINGS_LAYOUTS_KEY)

    assert "Test Layout" in layouts
    assert layouts["Test Layout"]["state"] == b"mock_state"
    assert layouts["Test Layout"]["geometry"] == b"mock_geometry"

    # Verify main window methods called
    mock_main_window.saveState.assert_called_once()
    mock_main_window.saveGeometry.assert_called_once()


def test_restore_layout_applies_data(ui_manager, mock_main_window, clean_settings):
    # Setup - save a layout first
    ui_manager.save_layout("Test Layout")

    # Restore
    ui_manager.restore_layout("Test Layout")

    # Verify
    mock_main_window.restoreState.assert_called_with(b"mock_state")
    mock_main_window.restoreGeometry.assert_called_with(b"mock_geometry")


def test_delete_layout_removes_data(ui_manager, clean_settings):
    # Mock message box to return Yes
    with patch("PySide6.QtWidgets.QMessageBox.question") as mock_question:
        from PySide6.QtWidgets import QMessageBox

        mock_question.return_value = QMessageBox.Yes

        ui_manager.save_layout("ToDelete")
        assert "ToDelete" in ui_manager.get_saved_layouts()

        ui_manager.delete_layout("ToDelete")
        assert "ToDelete" not in ui_manager.get_saved_layouts()


def test_get_saved_layouts_returns_sorted_list(ui_manager, clean_settings):
    ui_manager.save_layout("B Layout")
    ui_manager.save_layout("A Layout")

    layouts = ui_manager.get_saved_layouts()
    assert layouts == ["A Layout", "B Layout"]
