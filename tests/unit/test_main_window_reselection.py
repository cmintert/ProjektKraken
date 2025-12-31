import pytest
from unittest.mock import MagicMock, patch
from src.app.main import MainWindow


@pytest.fixture
def mock_main_window():
    """Creates a partial mock of MainWindow for logic testing."""
    # We patch MainWindow during import or construction to avoid full init
    with patch("src.app.main.MainWindow.__init__", return_value=None):
        window = MainWindow()
        # Initialize attributes used in _on_item_selected
        window.event_editor = MagicMock()
        window.entity_editor = MagicMock()
        window.ui_manager = MagicMock()
        window.load_event_details = MagicMock()
        window.load_entity_details = MagicMock()
        window.check_unsaved_changes = MagicMock(return_value=True)
        window._last_selected_id = None
        window._last_selected_type = None
        return window


def test_event_reselection_skipped(mock_main_window):
    """Test that selecting the same event again skips reload."""
    # Setup state: Event "1" is already selected
    mock_main_window._last_selected_id = "1"
    mock_main_window._last_selected_type = "event"

    # Action: Select "1" again
    mock_main_window._on_item_selected("event", "1")

    # Assert: logic skipped
    mock_main_window.check_unsaved_changes.assert_not_called()
    mock_main_window.load_event_details.assert_not_called()


def test_entity_reselection_skipped(mock_main_window):
    """Test that selecting the same entity again skips reload."""
    # Setup state: Entity "2" is already selected
    mock_main_window._last_selected_id = "2"
    mock_main_window._last_selected_type = "entity"

    # Action: Select "2" again
    mock_main_window._on_item_selected("entity", "2")

    # Assert: logic skipped
    mock_main_window.check_unsaved_changes.assert_not_called()
    mock_main_window.load_entity_details.assert_not_called()


def test_different_item_reloads(mock_main_window):
    """Test that selecting a different item strictly reloads."""
    # Setup state: Event "1" is selected
    mock_main_window._last_selected_id = "1"
    mock_main_window._last_selected_type = "event"

    # Action: Select Event "2"
    mock_main_window._on_item_selected("event", "2")

    # Assert: Reload happens
    mock_main_window.check_unsaved_changes.assert_called_once_with(
        mock_main_window.event_editor
    )
    mock_main_window.load_event_details.assert_called_once_with("2")


def test_switch_type_reloads(mock_main_window):
    """Test that switching type (even if ID coincidentally same) reloads."""
    # Setup state: Event "1" is selected
    mock_main_window._last_selected_id = "1"
    mock_main_window._last_selected_type = "event"

    # Action: Select Entity "1"
    mock_main_window._on_item_selected("entity", "1")

    # Assert: Reload happens
    mock_main_window.check_unsaved_changes.assert_called_once_with(
        mock_main_window.entity_editor
    )
    mock_main_window.load_entity_details.assert_called_once_with("1")
