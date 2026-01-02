"""
Unit tests for MainWindow session persistence.
"""

from unittest.mock import MagicMock, patch

import PySide6.QtCore
import pytest
from PySide6.QtWidgets import QMessageBox

from src.app.constants import (
    SETTINGS_LAST_ITEM_ID_KEY,
    SETTINGS_LAST_ITEM_TYPE_KEY,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
)
from src.app.main import MainWindow


@pytest.fixture
def mock_settings():
    """Mock QSettings to prevent real persistence usage."""
    with patch("src.app.main_window.QSettings") as MockSettings:
        storage = {}

        def mock_init(*args):
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
            return mock

        MockSettings.side_effect = mock_init

        # Also patch QtCore.QSettings for the test functions themselves
        with patch("PySide6.QtCore.QSettings", new=MockSettings):
            yield


@pytest.fixture
def main_window(qapp, qtbot, mock_settings):
    """Fixture to create a MainWindow instance."""
    # Patch UIManager and DataHandler to avoid complex init
    with (
        patch("src.app.main_window.UIManager"),
        patch("src.app.main_window.DataHandler"),
        patch("src.app.main_window.ConnectionManager"),
        patch("src.app.main_window.QMessageBox.question", return_value=QMessageBox.Discard),
        patch("src.app.main_window.QMessageBox.warning", return_value=QMessageBox.Discard),
    ):
        window = MainWindow()
        qtbot.addWidget(window)

        # Mock UI components accessed in tests
        window.ui_manager = MagicMock()
        window.ui_manager.docks = {"event": MagicMock(), "entity": MagicMock()}
        window.unified_list = MagicMock()
        window.event_editor = MagicMock()
        window.event_editor.has_unsaved_changes.return_value = False
        window.entity_editor = MagicMock()
        window.entity_editor.has_unsaved_changes.return_value = False

        # Mock load methods to prevent actual DB calls
        window.load_event_details = MagicMock()
        window.load_entity_details = MagicMock()

        yield window


def test_on_item_selected_saves_settings(main_window):
    """Test that selecting an item saves its ID and type to QSettings."""
    test_id = "test-uuid-123"
    test_type = "event"

    # Mock check_unsaved_changes to return True (proceed)
    main_window.check_unsaved_changes = MagicMock(return_value=True)

    # Clear settings first
    settings = PySide6.QtCore.QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    settings.remove(SETTINGS_LAST_ITEM_ID_KEY)
    settings.remove(SETTINGS_LAST_ITEM_TYPE_KEY)

    # Trigger selection
    main_window._on_item_selected(test_type, test_id)

    # Verify settings updated
    assert settings.value(SETTINGS_LAST_ITEM_ID_KEY) == test_id
    assert settings.value(SETTINGS_LAST_ITEM_TYPE_KEY) == test_type

    # Verify attributes updated
    assert main_window._last_selected_id == test_id
    assert main_window._last_selected_type == test_type


def test_restore_last_selection_event(main_window):
    """Test restoring an event selection."""
    test_id = "event-uuid-456"
    test_type = "event"

    # Setup settings
    settings = PySide6.QtCore.QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    settings.setValue(SETTINGS_LAST_ITEM_ID_KEY, test_id)
    settings.setValue(SETTINGS_LAST_ITEM_TYPE_KEY, test_type)

    # Trigger restore
    main_window._restore_last_selection()

    # Verify actions
    main_window.load_event_details.assert_called_with(test_id)
    main_window.ui_manager.docks["event"].raise_.assert_called_once()
    main_window.unified_list.select_item.assert_called_with(test_type, test_id)
    main_window.load_entity_details.assert_not_called()


def test_restore_last_selection_entity(main_window):
    """Test restoring an entity selection."""
    test_id = "entity-uuid-789"
    test_type = "entity"

    # Setup settings
    settings = PySide6.QtCore.QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    settings.setValue(SETTINGS_LAST_ITEM_ID_KEY, test_id)
    settings.setValue(SETTINGS_LAST_ITEM_TYPE_KEY, test_type)

    # Trigger restore
    main_window._restore_last_selection()

    # Verify actions
    main_window.load_entity_details.assert_called_with(test_id)
    main_window.ui_manager.docks["entity"].raise_.assert_called_once()
    main_window.unified_list.select_item.assert_called_with(test_type, test_id)
    main_window.load_event_details.assert_not_called()


def test_restore_last_selection_none(main_window):
    """Test restore does nothing if no settings exist."""
    # Clear settings
    settings = PySide6.QtCore.QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    settings.remove(SETTINGS_LAST_ITEM_ID_KEY)
    settings.remove(SETTINGS_LAST_ITEM_TYPE_KEY)

    # Trigger restore
    main_window._restore_last_selection()

    # Verify no actions
    main_window.load_event_details.assert_not_called()
    main_window.load_entity_details.assert_not_called()
    main_window.unified_list.select_item.assert_not_called()
