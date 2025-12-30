"""
Unit tests for MainWindow session persistence.
"""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QSettings

from src.app.constants import (
    SETTINGS_LAST_ITEM_ID_KEY,
    SETTINGS_LAST_ITEM_TYPE_KEY,
    WINDOW_SETTINGS_APP,
    WINDOW_SETTINGS_KEY,
)
from src.app.main import MainWindow


@pytest.fixture
def main_window(qapp, qtbot):
    """Fixture to create a MainWindow instance."""
    # Patch UIManager and DataHandler to avoid complex init
    with (
        patch("src.app.main.UIManager"),
        patch("src.app.main.DataHandler"),
        patch("src.app.main.ConnectionManager"),
    ):
        window = MainWindow()
        qtbot.addWidget(window)

        # Mock UI components accessed in tests
        window.ui_manager = MagicMock()
        window.ui_manager.docks = {"event": MagicMock(), "entity": MagicMock()}
        window.unified_list = MagicMock()
        window.event_editor = MagicMock()
        window.entity_editor = MagicMock()

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
    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
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
    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
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
    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
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
    settings = QSettings(WINDOW_SETTINGS_KEY, WINDOW_SETTINGS_APP)
    settings.remove(SETTINGS_LAST_ITEM_ID_KEY)
    settings.remove(SETTINGS_LAST_ITEM_TYPE_KEY)

    # Trigger restore
    main_window._restore_last_selection()

    # Verify no actions
    main_window.load_event_details.assert_not_called()
    main_window.load_entity_details.assert_not_called()
    main_window.unified_list.select_item.assert_not_called()
