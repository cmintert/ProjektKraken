import json
from unittest.mock import MagicMock, patch

import PySide6.QtCore
import pytest

from src.app.constants import (
    SETTINGS_LAYOUTS_KEY,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
)
from src.app.ui_manager import UIManager


@pytest.fixture
def mock_main_window():
    mw = MagicMock()
    mw.workspace.capture_layout.return_value = {
        "layout_version": 2,
        "zones": {"left": {"panels": ["project"]}},
    }
    return mw


@pytest.fixture
def ui_manager(mock_main_window):
    return UIManager(mock_main_window)


@pytest.fixture
def clean_settings():
    """Ensure settings are clean and mocked before and after tests."""
    with patch("src.app.ui_manager.QSettings") as MockSettings:
        # Create a real dict to act as backing store
        storage = {}

        def mock_settings_init(*args):
            mock = MagicMock()

            def setValue(key, value):
                storage[key] = value

            def value(key, default=None):
                return storage.get(key, default)

            def remove(key):
                if key in storage:
                    del storage[key]

            mock.setValue.side_effect = setValue
            mock.value.side_effect = value
            mock.remove.side_effect = remove
            mock.allKeys.side_effect = lambda: list(storage.keys())
            return mock

        MockSettings.side_effect = mock_settings_init

        # Also ensure our test functions that instantiate QSettings see the mock
        with patch("PySide6.QtCore.QSettings", new=MockSettings):
            yield


def test_save_layout_stores_data(ui_manager, mock_main_window, clean_settings):
    ui_manager.save_layout("Test Layout")

    # Access the backing store via a new QSettings (which is mocked)
    settings = PySide6.QtCore.QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    layouts = json.loads(settings.value(SETTINGS_LAYOUTS_KEY))

    assert "Test Layout" in layouts
    assert layouts["Test Layout"]["layout_version"] == 2
    mock_main_window.workspace.capture_layout.assert_called_once()


def test_restore_layout_applies_data(ui_manager, mock_main_window, clean_settings):
    # Setup - save a layout first
    ui_manager.save_layout("Test Layout")

    # Restore
    ui_manager.restore_layout("Test Layout")

    # Verify
    mock_main_window.workspace.apply_layout.assert_called_once_with(
        {
            "layout_version": 2,
            "zones": {"left": {"panels": ["project"]}},
        }
    )
    mock_main_window.restoreGeometry.assert_not_called()


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
